"""
早期刮刮樂歷史資料收集腳本（只落地成檔案，不寫入 scratchcard.db）

資料來源：台彩官網兩個歷史頁面背後的同一支 API
  - 本屆（2024/1/1 起）  https://www.taiwanlottery.com/instant/sale     → Type=1
  - 上一屆（2024/1/1 前）https://www.taiwanlottery.com/instant/history  → Type=2
    GET https://api.taiwanlottery.com/TLCAPIWeB/Instant/Result
        ?ScratchName=&Start_ListingDate=&End_ListingDate=&PageNum=1&PageSize=N&Type=1|2

獎金結構另打 News/Detail/{newsId}，解析邏輯沿用 app/service/crawler_service.py。
早期款式（多為 2013 年以前）沒有 newsId，本來就查不到獎金結構。

輸出（backend/data/history/）：
  scratchcards_all.json   全部欄位 + 巢狀 prizes
  scratchcards_all.csv    一款一列（獎金結構以項數表示）
  prizes_all.csv          獎金結構長表（期數 × 獎項）
  _news_cache/*.json      News/Detail 原始回應快取，重跑不會重抓
  _collect_report.json    統計與失敗清單

用法：cd backend && uv run python scripts/collect_history_scratchcards.py
      加 --refresh-news 可忽略快取重抓新聞
"""

from __future__ import annotations

import csv
import json
import re
import sys
import time
from pathlib import Path
from typing import Any

import requests
from bs4 import BeautifulSoup

API_BASE = "https://api.taiwanlottery.com/TLCAPIWeB"
HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Referer": "https://www.taiwanlottery.com/",
}

BASE_DIR = Path(__file__).resolve().parent.parent
OUT_DIR = BASE_DIR / "data" / "history"
NEWS_CACHE_DIR = OUT_DIR / "_news_cache"

# 屆別：Type=1 是本屆（2024/1/1 起發行），Type=2 是上一屆（2024/1/1 前）
TYPES = {1: "本屆(2024/1/1起)", 2: "上一屆(2024/1/1前)"}

MAX_SAFE_INT = 2**63 - 1
REQUEST_GAP = 0.3  # 對台彩 API 客氣一點


# --------------------------------------------------------------------------
# 清單 API
# --------------------------------------------------------------------------
def fetch_list(session: requests.Session, type_code: int) -> list[dict[str, Any]]:
    """抓某一屆的完整清單。PageSize 給大值即可一次取回，仍保留翻頁作保險。"""
    collected: dict[str, dict[str, Any]] = {}
    page = 1
    total_size = None

    while True:
        resp = session.get(
            f"{API_BASE}/Instant/Result",
            params={
                "ScratchName": "",
                "Start_ListingDate": "",
                "End_ListingDate": "",
                "PageNum": page,
                "PageSize": 500,
                "Type": type_code,
            },
            headers=HEADERS,
            timeout=30,
        )
        resp.raise_for_status()
        content = resp.json().get("content") or {}
        rows = content.get("resultList") or []
        if total_size is None:
            total_size = content.get("totalSize")

        if not rows:
            break

        for row in rows:
            vol = str(row.get("gameVol") or "").strip()
            if vol:
                collected[vol] = row

        if total_size is not None and len(collected) >= total_size:
            break
        page += 1
        if page > 50:  # 防呆
            break
        time.sleep(REQUEST_GAP)

    print(f"[list] Type={type_code} totalSize={total_size} collected={len(collected)}")
    return list(collected.values())


# --------------------------------------------------------------------------
# 獎金結構（News/Detail）
# --------------------------------------------------------------------------
def fetch_news_html(session: requests.Session, news_id: str, refresh: bool = False) -> str:
    """取得新聞 HTML，落地快取到 _news_cache/{newsId}.json。"""
    cache_file = NEWS_CACHE_DIR / f"{news_id}.json"
    if cache_file.exists() and not refresh:
        try:
            return json.loads(cache_file.read_text(encoding="utf-8")).get("html", "")
        except Exception:
            pass

    try:
        resp = session.get(
            f"{API_BASE}/News/Detail/{news_id}", headers=HEADERS, timeout=30
        )
        if resp.status_code != 200:
            return ""
        data = resp.json()
    except Exception as exc:
        print(f"[news] fetch failed {news_id}: {exc}")
        return ""

    html = ""
    content = data.get("content")
    if isinstance(content, str):
        html = content
    elif isinstance(content, dict):
        html = content.get("content", "") or ""

    cache_file.write_text(
        json.dumps(
            {
                "newsId": news_id,
                "newsTitle": (content or {}).get("newsTitle", "")
                if isinstance(content, dict)
                else "",
                "announceDate": (content or {}).get("announceDate", "")
                if isinstance(content, dict)
                else "",
                "html": html,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    time.sleep(REQUEST_GAP)
    return html


def parse_prizes(raw_html: str, target_game_id: str) -> list[dict[str, Any]]:
    """
    從新聞 HTML 解析指定期數的獎金結構。
    解析規則對齊 app/service/crawler_service.fetch_prize_via_api，
    確保跟現有 prize_structures 的資料長相一致。
    """
    if not raw_html:
        return []

    soup = BeautifulSoup(raw_html, "html.parser")

    # 期數在錨點/標題裡可能有沒有前導零兩種寫法（0146 vs 146），兩種都試
    variants = {str(target_game_id), str(target_game_id).lstrip("0").zfill(4), str(target_game_id).lstrip("0")}

    # 定位起點：ID 錨點 → h1~h3 標題
    anchor = None
    for variant in variants:
        anchor = soup.find("a", attrs={"id": variant}) or soup.find("a", attrs={"name": variant})
        if anchor:
            break
    if not anchor:
        for h_tag in soup.find_all(re.compile(r"^h[1-3]$")):
            vol_match = re.search(r"遊戲期數[：:]\s*(\d+)", h_tag.get_text(strip=True))
            if vol_match and vol_match.group(1).lstrip("0") == str(target_game_id).lstrip("0"):
                anchor = h_tag
                break

    target_tables = []
    if anchor:
        curr = anchor
        while True:
            curr = curr.find_next()
            if not curr:
                break
            if curr.name == "table":
                target_tables.append(curr)
            if curr.name == "a" and (curr.get("id") or curr.get("name")):
                aid = curr.get("id") or curr.get("name")
                if str(aid) != str(target_game_id) and re.match(r"^\d+$", str(aid)):
                    break
            if curr.name in ("h1", "h2", "h3"):
                # 只認「遊戲期數：XXXX」當作下一款的分界。
                # 不能用「含遊戲 + 有 4 位數字」判斷，否則遊戲主題本身帶年份的款式
                # （迎向2022 / 歡慶2016 / 2021賺翻天）會在自己的標題就被切斷。
                vol_match = re.search(r"遊戲期數[：:]\s*(\d+)", curr.get_text(strip=True))
                if vol_match and vol_match.group(1).lstrip("0") != str(target_game_id).lstrip("0"):
                    break
    else:
        # 沒有錨點時只在「整篇新聞只講一款」的情況下才敢全抓
        headings = [
            h.get_text(strip=True)
            for h in soup.find_all(re.compile(r"^h[1-3]$"))
            if "遊戲" in h.get_text(strip=True)
        ]
        if len(headings) > 1:
            return []
        target_tables = soup.find_all("table")

    if not target_tables:
        return []

    prizes: list[dict[str, Any]] = []
    for table in target_tables:
        if "summy" in str(table.get("class", [])):
            continue

        for row in table.find_all("tr"):
            cols = row.find_all(["td", "th"])
            if len(cols) < 2:
                continue

            pairs = []
            if len(cols) >= 4:
                pairs.append((cols[0], cols[1]))
                pairs.append((cols[2], cols[3]))
            else:
                pairs.append((cols[0], cols[1]))

            for col_prize, col_count in pairs:
                prize_lis = col_prize.find_all("li")
                count_lis = col_count.find_all("li")

                if prize_lis and count_lis:
                    prize_lines = [
                        li.get_text(strip=True) for li in prize_lis if li.get_text(strip=True)
                    ]
                    count_lines = [
                        li.get_text(strip=True) for li in count_lis if li.get_text(strip=True)
                    ]
                else:
                    prize_lines = [
                        line.strip()
                        for line in col_prize.get_text(separator="\n").split("\n")
                        if line.strip()
                    ]
                    count_lines = [
                        line.strip()
                        for line in col_count.get_text(separator="\n").split("\n")
                        if line.strip()
                    ]

                if not prize_lines or not count_lines:
                    continue

                first_p, first_c = prize_lines[0], count_lines[0]
                if "獎項" in first_p or "金額" in first_p or "張數" in first_c:
                    continue

                for idx, p_text in enumerate(prize_lines):
                    if not p_text:
                        continue

                    is_valid = ("NT" in p_text or "$" in p_text or "元" in p_text) or re.search(
                        r"[頭壹貳參肆伍陸柒捌玖\d]+獎", p_text
                    )
                    if not is_valid:
                        continue

                    amount = 0
                    amount_match = re.search(r"[\d][\d,]*", p_text)
                    if amount_match:
                        try:
                            amount = int(amount_match.group().replace(",", ""))
                        except ValueError:
                            pass

                    count = 0
                    if idx < len(count_lines):
                        c_text = count_lines[idx].replace(",", "")
                        count_match = re.search(r"\d+", c_text)
                        if count_match:
                            try:
                                count = int(count_match.group())
                            except ValueError:
                                pass

                    prizes.append(
                        {
                            "prizeName": p_text,
                            "prizeAmount": min(amount, MAX_SAFE_INT),
                            "totalCount": min(count, MAX_SAFE_INT),
                        }
                    )

    return prizes


def build_news_index(news_html: dict[str, str]) -> dict[str, list[str]]:
    """
    掃全部已抓的公告，建立「期數 → newsId 清單」反查索引。

    清單 API 少數幾筆的 newsId 掛錯（例：4413/4417 的 newsId 指向的公告
    內容其實是 4409/4410），主 newsId 解析不到時改用這個索引找正確的公告。
    """
    index: dict[str, list[str]] = {}
    for news_id, html in news_html.items():
        if not html:
            continue
        soup = BeautifulSoup(html, "html.parser")
        vols: set[str] = set()
        for a in soup.find_all("a"):
            aid = a.get("id") or a.get("name")
            if aid and re.fullmatch(r"\d+", str(aid)):
                vols.add(str(aid).lstrip("0"))
        for h_tag in soup.find_all(re.compile(r"^h[1-3]$")):
            m = re.search(r"遊戲期數[：:]\s*(\d+)", h_tag.get_text(strip=True))
            if m:
                vols.add(m.group(1).lstrip("0"))
        for vol in vols:
            index.setdefault(vol, []).append(news_id)
    return index


# --------------------------------------------------------------------------
# 欄位整理
# --------------------------------------------------------------------------
def iso_date(value: str | None) -> str:
    """'2023-11-01T00:00:00' → '2023-11-01'；空值回空字串。"""
    if not value:
        return ""
    return str(value).split("T")[0]


def roc_date(iso: str) -> str:
    """'2023-11-01' → '112/11/01'（對齊官網顯示）。"""
    if not iso or len(iso) < 10:
        return ""
    try:
        y, m, d = iso.split("-")
        return f"{int(y) - 1911}/{m}/{d}"
    except Exception:
        return ""


def sales_rate_value(text: str | None) -> float | None:
    if not text:
        return None
    match = re.search(r"[\d.]+", str(text))
    if not match:
        return None
    try:
        return float(match.group())
    except ValueError:
        return None


def build_record(row: dict[str, Any], type_code: int, prizes: list[dict[str, Any]]) -> dict[str, Any]:
    issue = iso_date(row.get("listingDate"))
    end = iso_date(row.get("downDate"))
    deadline = iso_date(row.get("exchangeLastDate"))

    return {
        "gameId": str(row.get("gameVol") or "").strip(),          # 遊戲期數
        "name": row.get("scratchName") or "",                      # 遊戲主題
        "term": TYPES[type_code],                                  # 屆別
        "termType": type_code,
        "price": row.get("money"),                                 # 售價
        "maxPrizeAmount": row.get("firstPrize"),                   # 最高獎金
        "issueDate": issue,                                        # 發行日
        "endDate": end,                                            # 下市日
        "redeemDeadline": deadline,                                # 兌獎截止日
        "issueDateROC": roc_date(issue),
        "endDateROC": roc_date(end),
        "redeemDeadlineROC": roc_date(deadline),
        "endTime": row.get("endTime") or "",
        "totalIssued": row.get("issuedCount"),                     # 發行張數
        "salesRate": row.get("sales_percent") or "",               # 銷售率
        "salesRateValue": sales_rate_value(row.get("sales_percent")),
        "grandPrizeCount": row.get("total_prize"),                 # 頭獎張數
        "grandPrizeUnclaimed": row.get("remain_prize"),            # 頭獎未兌領張數
        "prizeCount": len(prizes),
        "prizes": prizes,                                          # 獎金結構
        "scratchId": row.get("scratchId") or "",
        "newsId": row.get("newsId") or "",
        "imageUrl": row.get("picPath") or "",
        "prizeInfoUrl": (
            f"https://www.taiwanlottery.com/news/news/{row['newsId']}"
            if row.get("newsId")
            else ""
        ),
    }


# --------------------------------------------------------------------------
# 輸出
# --------------------------------------------------------------------------
CSV_COLUMNS = [
    ("gameId", "遊戲期數"),
    ("name", "遊戲主題"),
    ("term", "屆別"),
    ("prizeCount", "獎金結構項數"),
    ("price", "售價"),
    ("maxPrizeAmount", "最高獎金"),
    ("issueDate", "發行日"),
    ("issueDateROC", "發行日(民國)"),
    ("endDate", "下市日"),
    ("endDateROC", "下市日(民國)"),
    ("redeemDeadline", "兌獎截止日"),
    ("redeemDeadlineROC", "兌獎截止日(民國)"),
    ("totalIssued", "發行張數"),
    ("salesRate", "銷售率"),
    ("grandPrizeCount", "頭獎張數"),
    ("grandPrizeUnclaimed", "頭獎未兌領張數"),
    ("scratchId", "scratchId"),
    ("newsId", "newsId"),
    ("imageUrl", "圖片網址"),
    ("prizeInfoUrl", "獎金結構網址"),
]


def write_outputs(records: list[dict[str, Any]]) -> None:
    (OUT_DIR / "scratchcards_all.json").write_text(
        json.dumps(records, ensure_ascii=False, indent=1), encoding="utf-8"
    )

    # utf-8-sig 讓 Excel 直接開不亂碼
    with (OUT_DIR / "scratchcards_all.csv").open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow([label for _, label in CSV_COLUMNS])
        for rec in records:
            writer.writerow([rec.get(key, "") for key, _ in CSV_COLUMNS])

    with (OUT_DIR / "prizes_all.csv").open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["遊戲期數", "遊戲主題", "獎項名稱", "獎金金額", "張數"])
        for rec in records:
            for prize in rec["prizes"]:
                writer.writerow(
                    [
                        rec["gameId"],
                        rec["name"],
                        prize["prizeName"],
                        prize["prizeAmount"],
                        prize["totalCount"],
                    ]
                )


def main() -> int:
    refresh_news = "--refresh-news" in sys.argv
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    NEWS_CACHE_DIR.mkdir(parents=True, exist_ok=True)

    session = requests.Session()

    raw_rows: list[tuple[int, dict[str, Any]]] = []
    for type_code in (1, 2):
        for row in fetch_list(session, type_code):
            raw_rows.append((type_code, row))

    news_ids = sorted({r.get("newsId") for _, r in raw_rows if r.get("newsId")})
    print(f"[news] unique newsId = {len(news_ids)}")

    news_html: dict[str, str] = {}
    for i, news_id in enumerate(news_ids, 1):
        news_html[news_id] = fetch_news_html(session, news_id, refresh=refresh_news)
        if i % 25 == 0:
            print(f"[news] {i}/{len(news_ids)}")

    news_index = build_news_index(news_html)

    records: list[dict[str, Any]] = []
    no_news: list[str] = []
    parse_failed: list[str] = []
    recovered: list[str] = []

    for type_code, row in raw_rows:
        game_id = str(row.get("gameVol") or "").strip()
        news_id = row.get("newsId") or ""
        prizes: list[dict[str, Any]] = []

        if news_id:
            prizes = parse_prizes(news_html.get(news_id, ""), game_id)

            # 主 newsId 掛錯時，用反查索引找真正刊登這期的公告
            if not prizes:
                for alt_id in news_index.get(game_id.lstrip("0"), []):
                    if alt_id == news_id:
                        continue
                    prizes = parse_prizes(news_html.get(alt_id, ""), game_id)
                    if prizes:
                        row["newsId"] = alt_id
                        recovered.append(game_id)
                        break

            if not prizes:
                parse_failed.append(game_id)
        else:
            no_news.append(game_id)

        records.append(build_record(row, type_code, prizes))

    records.sort(key=lambda r: int(r["gameId"]) if r["gameId"].isdigit() else 0, reverse=True)
    write_outputs(records)

    report = {
        "total": len(records),
        "byTerm": {
            label: sum(1 for r in records if r["term"] == label) for label in TYPES.values()
        },
        "gameIdRange": [
            min(int(r["gameId"]) for r in records if r["gameId"].isdigit()),
            max(int(r["gameId"]) for r in records if r["gameId"].isdigit()),
        ],
        "duplicateGameIds": sorted(
            {r["gameId"] for r in records if [x["gameId"] for x in records].count(r["gameId"]) > 1}
        ),
        "withPrizeStructure": sum(1 for r in records if r["prizeCount"] > 0),
        "recoveredViaNewsIndex": {"count": len(recovered), "gameIds": sorted(recovered)},
        "noNewsId": {"count": len(no_news), "gameIds": sorted(no_news, key=lambda x: -int(x) if x.isdigit() else 0)},
        "hasNewsIdButParseFailed": {
            "count": len(parse_failed),
            "gameIds": sorted(parse_failed, key=lambda x: -int(x) if x.isdigit() else 0),
        },
        "missingFields": {
            label: sum(1 for r in records if r.get(key) in (None, ""))
            for key, label in CSV_COLUMNS
            if key
            in {
                "gameId",
                "name",
                "price",
                "maxPrizeAmount",
                "issueDate",
                "endDate",
                "redeemDeadline",
                "totalIssued",
                "salesRate",
                "grandPrizeCount",
                "grandPrizeUnclaimed",
            }
        },
    }
    (OUT_DIR / "_collect_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8"
    )

    print(
        f"[done] total={report['total']} "
        f"withPrize={report['withPrizeStructure']} "
        f"noNewsId={len(no_news)} recovered={len(recovered)} parseFailed={len(parse_failed)}"
    )
    print(f"[done] output -> {OUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
