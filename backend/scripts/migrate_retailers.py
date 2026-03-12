"""
DB Schema Migration — 為 retailers 表新增 Phase 2/3/4 所需欄位
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.model.database import engine
from sqlalchemy import inspect, text

# 需要新增的欄位
NEW_COLUMNS = [
    # Phase 3：設施標籤
    ("hasAC", "BOOLEAN DEFAULT 0"),
    ("hasToilet", "BOOLEAN DEFAULT 0"),
    ("hasSeats", "BOOLEAN DEFAULT 0"),
    ("hasWifi", "BOOLEAN DEFAULT 0"),
    ("hasAccessibility", "BOOLEAN DEFAULT 0"),
    ("hasEPay", "BOOLEAN DEFAULT 0"),
    ("hasStrategy", "BOOLEAN DEFAULT 0"),
    ("hasNumberPick", "BOOLEAN DEFAULT 0"),
    ("hasScratchBoard", "BOOLEAN DEFAULT 0"),
    ("hasMagnifier", "BOOLEAN DEFAULT 0"),
    ("hasNewspaper", "BOOLEAN DEFAULT 0"),
    ("hasSportTV", "BOOLEAN DEFAULT 0"),
    # Phase 3：認領
    ("isClaimed", "BOOLEAN DEFAULT 0"),
    ("merchantTier", "VARCHAR(10) DEFAULT ''"),
    ("announcement", "VARCHAR(200) DEFAULT ''"),
    # Phase 4：熱力圖
    ("jackpotCount", "INTEGER DEFAULT 0"),
]


def migrate():
    """檢查並新增缺少的欄位"""
    inspector = inspect(engine)
    existing = {c["name"] for c in inspector.get_columns("retailers")}

    added = 0
    skipped = 0

    with engine.begin() as conn:
        for col_name, col_type in NEW_COLUMNS:
            if col_name in existing:
                print(f"  ⏭️  {col_name} — 已存在")
                skipped += 1
            else:
                stmt = text(f"ALTER TABLE retailers ADD COLUMN {col_name} {col_type}")
                conn.execute(stmt)
                print(f"  ✅ {col_name} — 已新增 ({col_type})")
                added += 1

    print(f"\n🎉 Migration 完成！新增 {added} 個欄位，跳過 {skipped} 個已存在欄位")


if __name__ == "__main__":
    migrate()
