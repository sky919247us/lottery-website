# -*- coding: utf-8 -*-
"""正規化 JSON → 資料庫（整本開箱 / 大樣本統計）

只吃 normalize_unboxing.py 產出的中繼格式，職責單純：對照資料庫核實、去重、寫入。
預設 dry-run，加 --commit 才真的寫。

用法：
    uv run python scripts/import_unboxing.py --src data/unboxing            # 預覽
    uv run python scripts/import_unboxing.py --src data/unboxing --commit   # 寫入

去重規則：以 (gameId, serialNo) 為鍵。同一本可能同時出現在「3本」與「9本」兩份檔案裡，
重複者略過並在報告列出，避免樣本灌水。

Windows CP950 注意：摘要寫成 UTF-8 檔，不 print 中文到 stdout。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.model.database import Scratchcard, SessionLocal, init_db  # noqa: E402
from app.model.ticket_layout import default_tickets_per_book  # noqa: E402
from app.model.unboxing import UnboxingBook, UnboxingSession  # noqa: E402


_HISTORY_CACHE = None


def history_lookup(game_id):
    """資料庫還沒收錄該期時，退而查專案既有的歷史款總表

    backend/data/history/scratchcards_all.json 收錄 1111 款，含期數／名稱／面額／發行量。
    這是本機 DB 落後於正式站時的可靠備援，避免為了面額去猜。
    """
    global _HISTORY_CACHE
    if _HISTORY_CACHE is None:
        f = Path(__file__).resolve().parent.parent / "data" / "history" / "scratchcards_all.json"
        rows = []
        if f.exists():
            data = json.loads(f.read_text(encoding="utf-8"))
            rows = data if isinstance(data, list) else data.get("items", [])
        _HISTORY_CACHE = {str(r.get("gameId")): r for r in rows}
    return _HISTORY_CACHE.get(str(game_id))


def load_records(src: Path):
    if src.is_dir():
        files = sorted(f for f in src.glob("*.json") if not f.name.startswith("_"))
    else:
        files = [src]
    out = []
    for f in files:
        rec = json.loads(f.read_text(encoding="utf-8"))
        if "books" in rec and "gameId" in rec:
            out.append(rec)
    return out


def process(rec, db, existing_serials, commit, lines):
    gid = str(rec["gameId"])
    card = db.query(Scratchcard).filter(Scratchcard.gameId == gid).first()
    lines.append("=== %s（%s）" % (gid, rec.get("sourceFile") or "-"))

    hist = None
    if card is None:
        hist = history_lookup(gid)
        if hist:
            lines.append(
                "  ~ 資料庫查無此期數，改用歷史款總表：%s $%s"
                % (hist.get("name"), hist.get("price"))
            )
        else:
            lines.append("  !! 資料庫與歷史款總表皆查無此期數，面額需另行指定")
    price = (
        (card.price if card else None)
        or (hist.get("price") if hist else None)
        or rec.get("price")
    )
    name = (
        (card.name if card else "")
        or (hist.get("name") if hist else "")
        or rec.get("name")
        or ""
    )

    if not price:
        lines.append("  XX 無法判定面額，略過此檔（請用 --price 指定或先讓爬蟲補上期數）")
        return 0, 0

    tpb = rec["ticketsPerBook"]
    if default_tickets_per_book(price) != tpb:
        lines.append(
            "  !! 每本張數 %d 與面額 $%d 應有的 %d 不符，請確認來源檔"
            % (tpb, price, default_tickets_per_book(price))
        )

    # 同一份來源檔視為同一個場次，重跑時就地更新
    session = (
        db.query(UnboxingSession)
        .filter(
            UnboxingSession.gameId == gid,
            UnboxingSession.sourceFile == (rec.get("sourceFile") or ""),
        )
        .first()
    )
    if session is None:
        session = UnboxingSession(
            gameId=gid,
            sourceFile=rec.get("sourceFile") or "",
            title="%s %d本開箱" % (name or gid, len(rec["books"])),
        )
        if commit:
            db.add(session)
            db.flush()
        lines.append("  + 新增場次：%s" % session.title)
    else:
        lines.append("  ~ 沿用既有場次 id=%s" % session.id)

    session.ticketsPerBook = tpb
    session.isPublished = True
    session.gameName = name
    session.price = price

    added, skipped = 0, []
    for b in rec["books"]:
        serial = b.get("serialNo") or ""
        key = (gid, serial)
        if serial and key in existing_serials:
            skipped.append(serial)
            continue
        if serial:
            existing_serials.add(key)
        added += 1
        if commit:
            db.add(
                UnboxingBook(
                    session=session,
                    gameId=gid,
                    serialNo=serial,
                    label=b.get("label") or serial or "樣本",
                    batchKey=b.get("batchKey") or "",
                    seq=b.get("seq") or 0,
                    ticketCount=b["ticketCount"],
                    prizes=b["prizes"],
                    totalPrize=b["totalPrize"],
                    winCount=b["winCount"],
                )
            )
    session.bookCount = added

    tickets = sum(b["ticketCount"] for b in rec["books"] if (b.get("serialNo") or "") not in [s for s in skipped])
    total = sum(b["totalPrize"] for b in rec["books"] if (b.get("serialNo") or "") not in [s for s in skipped])
    wins = sum(b["winCount"] for b in rec["books"] if (b.get("serialNo") or "") not in [s for s in skipped])
    cost = tickets * price
    lines.append(
        "  本數=%d 張數=%d 面額=$%d 投入=%d 回收=%d 實測回本率=%s 實測中獎率=%s"
        % (
            added,
            tickets,
            price,
            cost,
            total,
            ("%.2f%%" % (total / cost * 100)) if cost else "n/a",
            ("%.2f%%" % (wins / tickets * 100)) if tickets else "n/a",
        )
    )
    if skipped:
        lines.append("  ~ 已存在於其他場次而略過的序號（%d 本）：%s" % (len(skipped), skipped))
    for w in rec.get("warnings", []):
        lines.append("  !! %s" % w)
    return added, len(skipped)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default="data/unboxing", help="正規化 JSON 檔或資料夾")
    ap.add_argument("--commit", action="store_true", help="真的寫入資料庫")
    ap.add_argument("--report", default="data/unboxing/_import_report.txt")
    args = ap.parse_args()

    init_db()
    db = SessionLocal()
    lines = ["模式：%s" % ("COMMIT（會寫入）" if args.commit else "DRY-RUN（不寫入）"), ""]
    try:
        existing = {
            (b.gameId, b.serialNo)
            for b in db.query(UnboxingBook.gameId, UnboxingBook.serialNo).all()
            if b.serialNo
        }
        recs = load_records(Path(args.src))
        # 按期數排序匯入，報告好讀
        recs.sort(key=lambda r: str(r["gameId"]))
        tot_add = tot_skip = 0
        for rec in recs:
            a, s = process(rec, db, existing, args.commit, lines)
            tot_add += a
            tot_skip += s
        if args.commit:
            db.commit()
            lines.append("")
            lines.append("已寫入資料庫。")
        else:
            db.rollback()
            lines.append("")
            lines.append("DRY-RUN 結束，未寫入。確認無誤後加 --commit。")
        lines.append("合計：新增 %d 本、去重略過 %d 本" % (tot_add, tot_skip))
    finally:
        db.close()

    Path(args.report).parent.mkdir(parents=True, exist_ok=True)
    Path(args.report).write_text("\n".join(lines), encoding="utf-8")
    print("import done added=%d skipped=%d commit=%s" % (tot_add, tot_skip, args.commit))


if __name__ == "__main__":
    main()
