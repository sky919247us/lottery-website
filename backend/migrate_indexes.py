"""一次性腳本：為 retailer 表加索引"""
import sqlite3

conn = sqlite3.connect("scratchcard.db")
cursor = conn.cursor()

indexes = [
    "CREATE INDEX IF NOT EXISTS ix_retailers_city ON retailers(city)",
    "CREATE INDEX IF NOT EXISTS ix_retailers_source ON retailers(source)",
    "CREATE INDEX IF NOT EXISTS ix_retailers_isActive ON retailers(isActive)",
    "CREATE INDEX IF NOT EXISTS ix_retailers_lat ON retailers(lat)",
    "CREATE INDEX IF NOT EXISTS ix_retailers_lng ON retailers(lng)",
    "CREATE INDEX IF NOT EXISTS ix_retailers_isClaimed ON retailers(isClaimed)",
    "CREATE INDEX IF NOT EXISTS ix_retailers_merchantTier ON retailers(merchantTier)",
    "CREATE INDEX IF NOT EXISTS ix_retailers_city_active ON retailers(city, isActive)",
]

for sql in indexes:
    print(f"執行: {sql}")
    cursor.execute(sql)

conn.commit()
conn.close()
print("索引建立完成！")
