# -*- coding: utf-8 -*-
"""整本開箱原始檔 → 正規化 JSON

來源試算表有多種版面，這支腳本用「格線掃描」而非寫死座標，把它們統一成一種中繼格式，
再交給 import_unboxing.py 寫入資料庫。未來出現新版面只需加 adapter，匯入路徑不動。

支援版面
  A 單本       表頭 gameId/名稱/售價 + 流水序號/中獎率，下方數組 (張號, 獎金) 直欄
  B 多本含表頭  每本一個欄區塊，各自帶完整表頭
  C 多本＋彙總  表頭只放流水序號，底部另有各獎項張數/合計獎金/中獎數彙總
  E 序號矩陣   欄頭＝流水序號，列＝張號（col 0 為張號索引）
  D 樣本矩陣   欄頭＝「樣本N」、無流水序號 → 目前不收，明確報錯

關鍵規則：張號欄不一定從 1 起跳（100 張可能拆成 01-50 / 51-100 兩欄），
必須依張號連續性「縫合」，遇到張號回到 1 才算換一本。

用法：
    uv run python scripts/normalize_unboxing.py --src "檔案或資料夾" [--game-id 5138] [--price 300]

Windows CP950 注意：本腳本只把摘要寫成 UTF-8 檔，不 print 中文到 stdout。
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.model.ticket_layout import (  # noqa: E402
    PRICE_TO_TICKETS_PER_BOOK,
    default_tickets_per_book,
)

# 同一批（同箱）判定：流水序號差距在此範圍內視為連號
BATCH_GAP = 10

SERIAL_RE = re.compile(r"^\d{4,6}$")


def clean_num(cell):
    """把 1,500 / $500 / 全形空白 這類字串轉成整數，非數字回 None"""
    if cell is None:
        return None
    t = str(cell).strip().replace(",", "").replace("$", "").replace("　", "")
    if t == "":
        return None
    try:
        return int(t)
    except ValueError:
        return None


def load_grid(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        return [row for row in csv.reader(f)]


def scan_runs(grid):
    """找出所有張號欄：某欄由上而下遞增 +1、長度 >= 5 的跑列（起始值不限）"""
    ncols = max((len(r) for r in grid), default=0)
    found = []
    for c in range(ncols):
        run = []
        for r in range(len(grid)):
            v = clean_num(grid[r][c]) if c < len(grid[r]) else None
            ok = v is not None and 1 <= v <= 500
            if ok and (not run or v == run[-1][0] + 1):
                run.append((v, r))
            else:
                if len(run) >= 5:
                    found.append((c, run[:]))
                run = [(v, r)] if ok else []
        if len(run) >= 5:
            found.append((c, run[:]))
    return found


def find_serial(grid, lo, hi, before_row):
    """在指定欄跨距的上方列尋找流水序號（保留前導零，故回傳字串）"""
    for r in range(0, min(before_row, len(grid))):
        for c in range(lo, min(hi + 1, len(grid[r]))):
            t = (grid[r][c] or "").strip()
            if SERIAL_RE.match(t) and len(t) >= 5:
                return t
    return None


def parse_pairs(grid):
    """版面 A / B / C：(張號, 獎金) 成對直欄"""
    runs = scan_runs(grid)
    if not runs:
        return []
    groups = []
    cur, cols, first_row = {}, [], 10 ** 9
    for c, run in runs:
        if cur and run[0][0] == 1:
            groups.append((cur, cols, first_row))
            cur, cols, first_row = {}, [], 10 ** 9
        first_row = min(first_row, run[0][1])
        for t, r in run:
            p = clean_num(grid[r][c + 1]) if c + 1 < len(grid[r]) else None
            cur[t] = p if p is not None else 0
        cols.append(c)
    if cur:
        groups.append((cur, cols, first_row))

    books = []
    for tk, cs, frow in groups:
        n = max(tk)
        prizes = [tk.get(k, 0) for k in range(1, n + 1)]
        serial = find_serial(grid, min(cs), max(cs) + 2, frow)
        if serial is None and not any(prizes):
            continue  # 空模板欄組
        books.append({"serialNo": serial, "prizes": prizes})
    return books


def parse_serial_matrix(grid):
    """版面 E：欄頭＝流水序號，col 0 為張號索引"""
    runs = scan_runs(grid)
    if not runs:
        return []
    # 取最左邊的張號跑列當索引欄；右側常有「1..N」輔助欄，不能要求全檔只有一組
    col, run = min(runs, key=lambda x: x[0])
    hdr = run[0][1] - 1
    if hdr < 0:
        return []
    serial_cols = [
        (c, grid[hdr][c].strip())
        for c in range(len(grid[hdr]))
        if SERIAL_RE.match((grid[hdr][c] or "").strip())
    ]
    if len(serial_cols) < 3:
        return []
    # 關鍵鑑別：版面 C 的表頭同樣是一排流水序號，但它的序號欄底下就是張號欄。
    # 真正的矩陣版面（E），序號欄底下放的是獎金，不會是張號跑列。
    run_cols = {c for c, _ in runs}
    if any(c in run_cols for c, _ in serial_cols):
        return []
    books = []
    for c, serial in serial_cols:
        prizes, t = [], 1
        for r in range(run[0][1], len(grid)):
            if c >= len(grid[r]) or clean_num(grid[r][col]) != t:
                break
            prizes.append(clean_num(grid[r][c]) or 0)
            t += 1
        if prizes:
            books.append({"serialNo": serial, "prizes": prizes})
    return books


def is_sample_matrix(grid):
    for row in grid:
        if sum(1 for c in row if c.strip().startswith("樣本")) >= 3:
            return True
    return False


def extract_meta(grid, filename):
    """從檔內表頭 / 檔名抓 gameId、名稱、售價、官方中獎率"""
    meta = {"gameId": None, "name": "", "price": None, "officialWinRate": None}
    flat = " ".join(" ".join(r) for r in grid[:4])
    m = re.search(r"(\d+)\s*元\s*/\s*張", flat)
    if m:
        meta["price"] = int(m.group(1))
    m = re.search(r"(\d+\.\d+)\s*%", flat)
    if m:
        meta["officialWinRate"] = float(m.group(1)) / 100
    # 檔名優先：檔內表頭附近可能出現獎金金額（如 5000），會被誤判成期數
    m = re.search(r"(5\d{3})", filename)
    if m:
        meta["gameId"] = m.group(1)
    else:
        for row in grid[:4]:
            for cell in row:
                t = (cell or "").strip()
                if re.fullmatch(r"5\d{3}", t):
                    meta["gameId"] = t
                    break
            if meta["gameId"]:
                break
    for row in grid[:3]:
        for i, cell in enumerate(row):
            if (cell or "").strip() == meta["gameId"] and i + 2 < len(row):
                cand = (row[i + 2] or "").strip()
                if cand and not cand.isdigit():
                    meta["name"] = cand
    return meta


def assign_batches(books):
    """依流水序號連號自動分批（銀行整箱進貨，連號多為同一批）"""
    numbered = [b for b in books if b.get("serialNo")]
    if not numbered:
        for b in books:
            b["batchKey"] = "批次A"
        return
    label, prev = 0, None
    for b in sorted(numbered, key=lambda x: int(x["serialNo"])):
        v = int(b["serialNo"])
        if prev is None or v - prev > BATCH_GAP:
            label += 1
        b["batchKey"] = "批次" + chr(ord("A") + label - 1)
        prev = v
    for b in books:
        b.setdefault("batchKey", "批次A")


def normalize_json(path, game_id=None, price_hint=None):
    """人工轉錄來源（例如只有截圖的款式）：直接吃 JSON，並用 checksum 反驗"""
    raw = json.loads(path.read_text(encoding="utf-8"))
    books = [
        {"serialNo": b.get("serialNo"), "prizes": [int(x) for x in b["prizes"]]}
        for b in raw["books"]
    ]
    price = price_hint or raw.get("price")
    warnings = []
    ck = raw.get("checksum") or {}
    total = sum(sum(b["prizes"]) for b in books)
    tickets = sum(len(b["prizes"]) for b in books)
    if "totalPrize" in ck and ck["totalPrize"] != total:
        raise ValueError(
            "%s: 合計獎金 %d 與轉錄校驗值 %d 不符" % (path.name, total, ck["totalPrize"])
        )
    if "netProfit" in ck and price and (total - tickets * price) != ck["netProfit"]:
        raise ValueError(
            "%s: 總損益 %d 與轉錄校驗值 %d 不符"
            % (path.name, total - tickets * price, ck["netProfit"])
        )
    if "returnRate" in ck and price:
        got = total / (tickets * price)
        if abs(got - ck["returnRate"]) > 0.0005:
            raise ValueError(
                "%s: 回本率 %.4f 與轉錄校驗值 %.4f 不符" % (path.name, got, ck["returnRate"])
            )
        warnings.append("已通過圖片校驗：合計獎金/回本率/總損益三項皆符")
    tpb = max(len(b["prizes"]) for b in books)
    if price and default_tickets_per_book(price) != tpb:
        warnings.append(
            "每本張數 %d 與面額 $%s 應有的 %d 不符"
            % (tpb, price, default_tickets_per_book(price))
        )
    for i, b in enumerate(books):
        b["seq"] = i + 1
        b["label"] = b["serialNo"] or ("樣本 %d" % (i + 1))
        b["ticketCount"] = len(b["prizes"])
        b["totalPrize"] = sum(b["prizes"])
        b["winCount"] = sum(1 for p in b["prizes"] if p > 0)
    assign_batches(books)
    return {
        "gameId": game_id or str(raw["gameId"]),
        "name": raw.get("name", ""),
        "price": price,
        "ticketsPerBook": tpb,
        "officialWinRate": raw.get("officialWinRate"),
        "sourceFile": path.name,
        "warnings": warnings,
        "books": books,
    }


def normalize_file(path, game_id=None, price_hint=None):
    if path.suffix.lower() == ".json":
        return normalize_json(path, game_id, price_hint)
    grid = load_grid(path)
    meta = extract_meta(grid, path.name)
    gid = game_id or meta["gameId"]
    if not gid:
        raise ValueError(path.name + ": 無法判定 gameId，請用 --game-id 指定")

    if is_sample_matrix(grid):
        raise ValueError(path.name + ": 版面 D（樣本矩陣、無流水序號）目前不收，請提供有序號的版本")

    books = parse_serial_matrix(grid) or parse_pairs(grid)
    if not books:
        raise ValueError(path.name + ": 解析不到任何整本資料")

    # 檔內去重（同一份檔案可能重複收錄同一本）
    seen, uniq, dropped = set(), [], []
    for b in books:
        key = b["serialNo"]
        if key and key in seen:
            dropped.append(key)
            continue
        if key:
            seen.add(key)
        uniq.append(b)
    books = uniq

    price = price_hint or meta["price"]
    counts = {len(b["prizes"]) for b in books}
    tpb = max(counts)
    warnings = []
    if price is None:
        cand = sorted(p for p, n in PRICE_TO_TICKETS_PER_BOOK.items() if n == tpb)
        if len(cand) == 1:
            price = cand[0]
        else:
            warnings.append(
                "檔內無面額，%d 張/本 對應 %s 皆有可能，匯入時以資料庫的 scratchcards.price 為準"
                % (tpb, cand)
            )

    if price and default_tickets_per_book(price) != tpb:
        warnings.append(
            "每本張數 %d 與面額 $%s 應有的 %d 不符"
            % (tpb, price, default_tickets_per_book(price))
        )
    if len(counts) > 1:
        warnings.append("各本張數不一致：%s" % sorted(counts))
    if dropped:
        warnings.append("檔內重複序號已略過：%s" % dropped)

    for i, b in enumerate(books):
        b["seq"] = i + 1
        b["label"] = b["serialNo"] or ("樣本 %d" % (i + 1))
        b["ticketCount"] = len(b["prizes"])
        b["totalPrize"] = sum(b["prizes"])
        b["winCount"] = sum(1 for p in b["prizes"] if p > 0)
    assign_batches(books)

    return {
        "gameId": gid,
        "name": meta["name"],
        "price": price,
        "ticketsPerBook": tpb,
        "officialWinRate": meta["officialWinRate"],
        "sourceFile": path.name,
        "warnings": warnings,
        "books": books,
    }


def summarize(rec):
    lines = []
    total_t = sum(b["ticketCount"] for b in rec["books"])
    total_p = sum(b["totalPrize"] for b in rec["books"])
    total_w = sum(b["winCount"] for b in rec["books"])
    cost = total_t * (rec["price"] or 0)
    lines.append("=== %s" % rec["sourceFile"])
    lines.append(
        "  gameId=%s 名稱=%s 面額=%s 張/本=%s 本數=%d"
        % (rec["gameId"], rec["name"] or "-", rec["price"], rec["ticketsPerBook"], len(rec["books"]))
    )
    for b in rec["books"]:
        tiers = {}
        for p in b["prizes"]:
            if p > 0:
                tiers[p] = tiers.get(p, 0) + 1
        lines.append(
            "   %-8s %s 張=%3d 合計=%7d 中獎=%3d 槓龜=%3d %s"
            % (
                b["label"],
                b["batchKey"],
                b["ticketCount"],
                b["totalPrize"],
                b["winCount"],
                b["ticketCount"] - b["winCount"],
                dict(sorted(tiers.items())),
            )
        )
    lines.append(
        "  >> 總張數=%d 總中獎=%d(%.2f%%) 總獎金=%d 投入=%d 實測回本率=%s"
        % (
            total_t,
            total_w,
            total_w / total_t * 100 if total_t else 0,
            total_p,
            cost,
            ("%.2f%%" % (total_p / cost * 100)) if cost else "n/a",
        )
    )
    if rec["officialWinRate"]:
        lines.append("  >> 檔內官方中獎率=%.2f%%" % (rec["officialWinRate"] * 100))
    for w in rec["warnings"]:
        lines.append("  !! %s" % w)
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True, help="CSV 檔或資料夾")
    ap.add_argument("--game-id", default=None)
    ap.add_argument("--price", type=int, default=None)
    ap.add_argument("--out", default="data/unboxing")
    ap.add_argument("--report", default="data/unboxing/_normalize_report.txt")
    args = ap.parse_args()

    src = Path(args.src)
    if src.is_dir():
        files = sorted(list(src.glob("*.csv")) + list(src.glob("*.json")))
    else:
        files = [src]
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    report, ok, fail = [], 0, 0
    for f in files:
        try:
            rec = normalize_file(f, args.game_id, args.price)
        except Exception as e:  # noqa: BLE001
            report.append("=== %s\n  XX %s" % (f.name, e))
            fail += 1
            continue
        slug = "%s_%d books" % (rec["gameId"], len(rec["books"]))
        dst = out_dir / ("%s.json" % rec["gameId"])
        # 同一款可能有多份來源檔，檔名帶上來源以免互相覆蓋
        if dst.exists():
            existing = json.loads(dst.read_text(encoding="utf-8"))
            if existing.get("sourceFile") != rec["sourceFile"]:
                dst = out_dir / ("%s__%s.json" % (rec["gameId"], len(rec["books"])))
        dst.write_text(
            json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8"
        )
        report.append(summarize(rec) + "\n  -> %s (%s)" % (dst.as_posix(), slug))
        ok += 1

    report.append("\n完成：成功 %d 份、失敗 %d 份" % (ok, fail))
    Path(args.report).parent.mkdir(parents=True, exist_ok=True)
    Path(args.report).write_text("\n".join(report), encoding="utf-8")
    print("normalize done ok=%d fail=%d" % (ok, fail))


if __name__ == "__main__":
    main()
