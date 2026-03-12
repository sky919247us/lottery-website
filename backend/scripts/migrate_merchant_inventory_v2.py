"""
遷移腳本：在 merchant_inventory 資料表加入 scratchcardId 欄位
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "scratchcard.db")


def migrate():
    """在 merchant_inventory 資料表新增 scratchcardId 欄位"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 檢查欄位是否已存在
    cursor.execute("PRAGMA table_info(merchant_inventory)")
    columns = [col[1] for col in cursor.fetchall()]

    if "scratchcardId" not in columns:
        cursor.execute(
            "ALTER TABLE merchant_inventory ADD COLUMN scratchcardId INTEGER REFERENCES scratchcards(id)"
        )
        # 建立索引
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS ix_merchant_inventory_scratchcardId ON merchant_inventory(scratchcardId)"
        )
        conn.commit()
        print("✅ 已新增 scratchcardId 欄位至 merchant_inventory 資料表")
    else:
        print("ℹ️ scratchcardId 欄位已存在，無需遷移")

    conn.close()


if __name__ == "__main__":
    migrate()
