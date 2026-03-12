"""查詢賓果彩券行與同地址"""
import sqlite3, os
conn = sqlite3.connect(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'scratchcard.db'))
c = conn.cursor()
c.execute("SELECT id, name, lat, lng FROM retailers WHERE name LIKE '%賓果%'")
for r in c.fetchall():
    print(f"BINGO: id={r[0]} name={r[1]} lat={r[2]} lng={r[3]}")
# 地圖模式顯示 39/39 間 - 列表也是39
# 但地圖只顯示有座標的,看看 displayCount 是否影響
c.execute("SELECT COUNT(*) FROM retailers WHERE (lat IS NULL OR lat = 0) AND city = '台中市' AND district = '北屯區'")
print(f"北屯缺座標: {c.fetchone()[0]}")
c.execute("SELECT COUNT(*) FROM retailers WHERE lat IS NOT NULL AND lat != 0 AND city = '台中市' AND district = '北屯區'")
print(f"北屯有座標: {c.fetchone()[0]}")
conn.close()
