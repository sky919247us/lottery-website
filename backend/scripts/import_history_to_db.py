"""
把 backend/data/history/scratchcards_all.json 匯入資料庫。

策略（依使用者決定）：
  - **只補缺的**：資料庫已存在的 gameId 一律跳過，不覆蓋任何既有欄位
  - 上一屆（期數 1–4647，2024/1/1 前發行）寫入時標記 isHistory=True，
    列表 API 預設不會回傳，正式站外觀不變
  - 本屆（期數 5001–）標記 isHistory=False，跟現有資料同一池

連線走 DATABASE_URL（本機沒設就是 sqlite:///./scratchcard.db，正式站是 PostgreSQL）。

用法：
    cd backend && uv run python scripts/import_history_to_db.py            # dry-run，只報告
    cd backend && uv run python scripts/import_history_to_db.py --commit   # 實際寫入

寫入前務必先備份資料庫（正式站見 scripts/backup_db.py）。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.model.database import (  # noqa: E402
    DATABASE_URL,
    PrizeStructure,
    Scratchcard,
    SessionLocal,
)

DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "history" / "scratchcards_all.json"

# 上一屆最後一期；<= 此期數者視為歷史款
LAST_TERM_MAX_VOL = 4647


def fmt_money(value: int | None) -> str:
    """2000000 → '$2,000,000'（對齊既有 maxPrize 欄位的寫法）"""
    if not value:
        return ""
    return f"${int(value):,}"


def to_row(rec: dict) -> dict:
    """把收集到的紀錄轉成 Scratchcard 欄位。日期一律用民國格式，與既有資料一致。"""
    vol = int(rec["gameId"]) if rec["gameId"].isdigit() else 0
    sales_rate = rec.get("salesRate") or "-"  # 在售中的款台彩不給銷售率，既有資料寫 "-"
    sales_rate_value = rec.get("salesRateValue") or 0.0
    unclaimed = rec.get("grandPrizeUnclaimed") or 0

    return {
        "gameId": rec["gameId"],
        "name": rec["name"],
        "price": rec.get("price") or 0,
        "maxPrize": fmt_money(rec.get("maxPrizeAmount")),
        "maxPrizeAmount": rec.get("maxPrizeAmount") or 0,
        "issueDate": rec.get("issueDateROC") or "",
        "endDate": rec.get("endDateROC") or "",
        "redeemDeadline": rec.get("redeemDeadlineROC") or "",
        "totalIssued": rec.get("totalIssued") or 0,
        "salesRate": sales_rate,
        "salesRateValue": sales_rate_value,
        "grandPrizeCount": rec.get("grandPrizeCount") or 0,
        "grandPrizeUnclaimed": unclaimed,
        "overallWinRate": "",  # 列表/詳情 API 會用獎金結構動態算，不預存
        "isHighWinRate": sales_rate_value >= 80.0 and unclaimed >= 1,
        "isPreview": False,
        "isHistory": vol <= LAST_TERM_MAX_VOL,
        "prizeInfoUrl": rec.get("prizeInfoUrl") or "",
        "imageUrl": rec.get("imageUrl") or "",
    }


def main() -> int:
    commit = "--commit" in sys.argv

    records = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    print(f"[data] {DATA_FILE.name}: {len(records)} 筆")
    print(f"[db]   {DATABASE_URL.split('://')[0]}")

    db = SessionLocal()
    try:
        existing_ids = {gid for (gid,) in db.query(Scratchcard.gameId).all()}
        print(f"[db]   已有 {len(existing_ids)} 筆")

        to_insert = [r for r in records if r["gameId"] not in existing_ids]
        skipped = len(records) - len(to_insert)

        n_hist = sum(1 for r in to_insert if int(r["gameId"]) <= LAST_TERM_MAX_VOL)
        n_curr = len(to_insert) - n_hist
        n_prizes = sum(len(r["prizes"]) for r in to_insert)

        print(f"[plan] 新增 {len(to_insert)} 筆（歷史款 {n_hist} / 本屆 {n_curr}）")
        print(f"[plan] 跳過 {skipped} 筆（已存在，不覆蓋）")
        print(f"[plan] 附帶獎金結構 {n_prizes} 列")

        if n_curr:
            curr_ids = sorted(
                (r["gameId"] for r in to_insert if int(r["gameId"]) > LAST_TERM_MAX_VOL),
                reverse=True,
            )
            print(f"[plan] 本屆新增期數：{', '.join(curr_ids)}")

        if not commit:
            print("[dry-run] 未寫入任何資料。確認無誤後加 --commit 執行。")
            return 0

        inserted = 0
        for rec in to_insert:
            card = Scratchcard(**to_row(rec))
            db.add(card)
            db.flush()  # 取得 card.id
            for prize in rec["prizes"]:
                db.add(
                    PrizeStructure(
                        scratchcardId=card.id,
                        prizeName=prize["prizeName"],
                        prizeAmount=prize["prizeAmount"],
                        totalCount=prize["totalCount"],
                    )
                )
            inserted += 1
            if inserted % 200 == 0:
                db.commit()
                print(f"[write] {inserted}/{len(to_insert)}")

        db.commit()

        total = db.query(Scratchcard).count()
        hist = db.query(Scratchcard).filter(Scratchcard.isHistory.is_(True)).count()
        print(f"[done] 新增 {inserted} 筆；資料庫現有 {total} 筆（其中歷史款 {hist} 筆）")
        return 0
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
