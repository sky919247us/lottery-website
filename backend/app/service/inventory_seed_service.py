"""
新款刮刮樂自動鋪貨服務

功能：
  1. seed_new_release_inventory()
     - 上市當天 (issueDate == 今日民國日期) 的新款，
       自動為全台「台灣彩券」店家 (source=台灣彩券, isActive) 各建立一筆庫存 (狀態=充足)。
     - 已存在同款庫存的店家略過，不重複塞。
  2. cleanup_expired_inventory()
     - 刪除所有「最後更新時間超過 30 天」的庫存記錄。
     - 店家手動更新會刷新 updatedAt → 等於續命 30 天；停擺 30 天才會被清掉。
     - 無永久記錄，全表 30 天滾動。

設計重點：避免資料表無限累積。一個月約 2 次上市、每次約 2 款，
同時段最多約 4 款 × 5,469 台彩店 ≈ 2.2 萬筆封頂，過期即清。
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.model.database import Scratchcard
from app.model.merchant_inventory import MerchantInventory
from app.model.retailer import Retailer

# 只對台彩店家鋪貨（運彩店家排除）
TAIWAN_LOTTERY_SOURCE = "台灣彩券"
EXPIRE_DAYS = MerchantInventory.EXPIRE_DAYS  # 30


def _today_roc() -> str:
    """回傳今日的民國年日期字串，格式對齊 scratchcards.issueDate，例如 '115/05/19'。"""
    tw_now = datetime.now(timezone(timedelta(hours=8)))  # 台灣時間 UTC+8
    return f"{tw_now.year - 1911}/{tw_now.month:02d}/{tw_now.day:02d}"


def seed_new_release_inventory(db: Session, target_roc_date: str | None = None) -> dict:
    """為今日上市的新款自動鋪貨到所有台彩店家。

    :param target_roc_date: 指定民國日期 (測試用)，預設今日。
    :return: 統計結果 dict。
    """
    roc_date = target_roc_date or _today_roc()

    # 只取需要欄位 (避免載入不必要欄位, 也避開 schema drift)
    new_cards = (
        db.query(Scratchcard.id, Scratchcard.name, Scratchcard.price)
        .filter(Scratchcard.issueDate == roc_date)
        .all()
    )
    if not new_cards:
        return {"date": roc_date, "newCards": 0, "seeded": 0, "skipped": 0}

    # 取得全台啟用中的台彩店家 id
    retailer_ids = [
        r.id for r in db.query(Retailer.id)
        .filter(Retailer.source == TAIWAN_LOTTERY_SOURCE, Retailer.isActive == True)  # noqa: E712
        .all()
    ]

    now = datetime.utcnow()
    total_seeded = 0
    total_skipped = 0

    for card in new_cards:
        # 已存在同款庫存的店家 → 跳過，不重複塞
        existing_rids = {
            row[0] for row in db.query(MerchantInventory.retailerId)
            .filter(MerchantInventory.scratchcardId == card.id)
            .all()
        }

        rows = []
        for rid in retailer_ids:
            if rid in existing_rids:
                total_skipped += 1
                continue
            rows.append({
                "retailerId": rid,
                "scratchcardId": card.id,
                "itemName": card.name,
                "itemPrice": int(card.price or 0),
                "status": "充足",
                "createdAt": now,
                "updatedAt": now,
            })

        if rows:
            db.bulk_insert_mappings(MerchantInventory, rows)
            total_seeded += len(rows)

    db.commit()
    return {
        "date": roc_date,
        "newCards": len(new_cards),
        "cardNames": [c.name for c in new_cards],
        "retailers": len(retailer_ids),
        "seeded": total_seeded,
        "skipped": total_skipped,
    }


def cleanup_expired_inventory(db: Session) -> int:
    """刪除所有最後更新超過 30 天的庫存記錄（含店家手動設定者，無永久記錄）。

    :return: 刪除筆數。
    """
    cutoff = datetime.utcnow() - timedelta(days=EXPIRE_DAYS)
    deleted = (
        db.query(MerchantInventory)
        .filter(MerchantInventory.updatedAt < cutoff)
        .delete(synchronize_session=False)
    )
    db.commit()
    return deleted
