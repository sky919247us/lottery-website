"""
Fallback Geocoding：對仍缺座標的經銷商，使用所屬縣市中心座標+隨機偏移
"""
import sqlite3
import random
import os

DB_PATH = os.path.join(os.path.dirname(__file__), 'scratchcard.db')

# 各縣市近似中心座標
CITY_CENTERS = {
    '金門縣': (24.4493, 118.3767),
    '連江縣': (26.1505, 119.9337),
    '苗栗縣': (24.5602, 120.8214),
    '台東縣': (22.7583, 121.1444),
    '花蓮縣': (23.9872, 121.6016),
    '屏東縣': (22.6756, 120.4942),
    '南投縣': (23.9600, 120.9718),
    '彰化縣': (24.0752, 120.5161),
    '雲林縣': (23.7092, 120.4313),
    '嘉義縣': (23.4518, 120.2555),
    '宜蘭縣': (24.7570, 121.7533),
    '新竹縣': (24.8271, 121.0177),
    '新竹市': (24.8138, 120.9675),
    '基隆市': (25.1276, 121.7392),
    '台北市': (25.0330, 121.5654),
    '新北市': (25.0170, 121.4628),
    '桃園市': (24.9936, 121.3010),
    '台中市': (24.1477, 120.6736),
    '台南市': (22.9998, 120.2269),
    '高雄市': (22.6273, 120.3014),
    '澎湖縣': (23.5711, 119.5793),
}


def main():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute('SELECT id, name, address, city FROM retailers WHERE lat IS NULL OR lat = 0')
    rows = c.fetchall()
    print(f"找到 {len(rows)} 筆缺座標")

    updated = 0
    for rid, name, addr, city in rows:
        if city in CITY_CENTERS:
            lat, lng = CITY_CENTERS[city]
            # 加小偏移避免重疊
            lat += random.uniform(-0.008, 0.008)
            lng += random.uniform(-0.008, 0.008)
            c.execute('UPDATE retailers SET lat = ?, lng = ? WHERE id = ?',
                      (round(lat, 7), round(lng, 7), rid))
            updated += 1
            print(f"  OK: {name} ({city}) -> ({lat:.5f}, {lng:.5f})")
        else:
            print(f"  SKIP: {name} city={city}")

    conn.commit()

    c.execute('SELECT COUNT(*) FROM retailers WHERE lat IS NOT NULL AND lat != 0')
    has = c.fetchone()[0]
    c.execute('SELECT COUNT(*) FROM retailers')
    total = c.fetchone()[0]
    conn.close()

    print(f"\nDone! Updated={updated} Coverage={has}/{total} ({has/total*100:.1f}%)")


if __name__ == "__main__":
    main()
