"""
建立 merchant_inventory 資料表
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "scratchcard.db")


def migrate():
    """建立 merchant_inventory 資料表"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS merchant_inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            "retailerId" INTEGER NOT NULL,
            "itemName" VARCHAR(50) NOT NULL,
            "itemPrice" INTEGER DEFAULT 0,
            status VARCHAR(10) NOT NULL DEFAULT '未設定',
            "updatedAt" DATETIME DEFAULT CURRENT_TIMESTAMP,
            "createdAt" DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY ("retailerId") REFERENCES retailers(id)
        )
    """)

    # 建立索引加速查詢
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS ix_merchant_inventory_retailerId
        ON merchant_inventory ("retailerId")
    """)

    conn.commit()
    print(f"✅ merchant_inventory 資料表建立完成")
    conn.close()


if __name__ == "__main__":
    migrate()
