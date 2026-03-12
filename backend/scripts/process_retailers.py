import csv
import math
import sqlite3
import os
import re

# TWD97 -> WGS84 參數
A = 6378137.0
F = 1 / 298.257222101
B = A * (1 - F)
E2 = 2 * F - F ** 2
E_PRIME2 = E2 / (1 - E2)
K0 = 0.9999
LON0 = 121.0
FALSE_EASTING = 250000
FALSE_NORTHING = 0

def twd97_to_wgs84(x: float, y: float):
    x -= FALSE_EASTING
    y -= FALSE_NORTHING
    m = y / K0
    mu = m / (A * (1 - E2 / 4 - 3 * E2 ** 2 / 64 - 5 * E2 ** 3 / 256))
    e1 = (1 - math.sqrt(1 - E2)) / (1 + math.sqrt(1 - E2))
    phi1 = mu + (3 * e1 / 2 - 27 * e1 ** 3 / 32) * math.sin(2 * mu) \
         + (21 * e1 ** 2 / 16 - 55 * e1 ** 4 / 32) * math.sin(4 * mu) \
         + (151 * e1 ** 3 / 96) * math.sin(6 * mu) \
         + (1097 * e1 ** 4 / 512) * math.sin(8 * mu)
    n1 = A / math.sqrt(1 - E2 * math.sin(phi1) ** 2)
    t1 = math.tan(phi1) ** 2
    c1 = E_PRIME2 * math.cos(phi1) ** 2
    r1 = A * (1 - E2) / (1 - E2 * math.sin(phi1) ** 2) ** 1.5
    d = x / (n1 * K0)
    lat = phi1 - (n1 * math.tan(phi1) / r1) * (
        d ** 2 / 2 - (5 + 3 * t1 + 10 * c1 - 4 * c1 ** 2 - 9 * E_PRIME2) * d ** 4 / 24
        + (61 + 90 * t1 + 298 * c1 + 45 * t1 ** 2 - 252 * E_PRIME2 - 3 * c1 ** 2) * d ** 6 / 720
    )
    lon = math.radians(LON0) + (
        d - (1 + 2 * t1 + c1) * d ** 3 / 6
        + (5 - 2 * c1 + 28 * t1 - 3 * c1 ** 2 + 8 * E_PRIME2 + 24 * t1 ** 2) * d ** 5 / 120
    ) / math.cos(phi1)
    return math.degrees(lat), math.degrees(lon)

def extreact_city_dist(address):
    # 簡易擷取縣市(3字)與區(一般為前3字後面的字到'區'或'鄉'或'鎮'或'市')
    city = address[:3]
    m = re.match(r'^.{3}(.*?)[區鄉鎮市]', address)
    district = ""
    if m:
        district = m.group(1) + address[m.end()-1]
    return city, district

def main():
    tgos_csv = r"d:\刮刮樂網站\Address_Finish(3).csv"
    tc_csv = r"d:\刮刮樂網站\台彩.csv"
    sc_csv = r"d:\刮刮樂網站\運彩.csv"
    db_path = r"d:\刮刮樂網站\backend\scratchcard.db"

    # 1. 讀取 TGOS 座標字典 {address: (lat, lng)}
    print("讀取 TGOS 座標資料...")
    coords_dict = {}
    with open(tgos_csv, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            addr = row.get('Address', '').strip()
            raw_x = row.get('Response_X', '').strip()
            raw_y = row.get('Response_Y', '').strip()
            if not addr or not raw_x or not raw_y:
                continue
            if ';' in raw_x:
                raw_x = raw_x.split(';')[0]
                raw_y = raw_y.split(';')[0]
            try:
                lng = float(raw_x)
                lat = float(raw_y)
                # 基本檢查
                if 21.5 < lat < 26.5 and 119.0 < lng < 122.5:
                    coords_dict[addr] = (round(lat, 7), round(lng, 7))
            except Exception as e:
                pass

    print(f"成功載入 {len(coords_dict)} 筆 TGOS 座標。")

    # 連線 DB
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # 紀錄既有資料以便做 soft delete 或 merge
    cursor.execute("SELECT id, name, address, source FROM retailers")
    existing = {f"{r[1]}_{r[2]}_{r[3]}": r[0] for r in cursor.fetchall()}
    processed = set()
    
    inserts = 0
    updates = 0
    missing_coords = 0

    def process_row(name, address, source, default_city="", default_dist=""):
        nonlocal inserts, updates, missing_coords
        lat, lng = coords_dict.get(address, (None, None))
        
        if lat is None:
            # 嘗試模糊比對忽略樓層或特殊符號
            clean_addr = address.split('樓')[0].split('-')[0]
            for tg_addr, tg_coords in coords_dict.items():
                if clean_addr in tg_addr or tg_addr in clean_addr:
                    lat, lng = tg_coords
                    break
                    
        if lat is None:
            missing_coords += 1

        city, dist = default_city, default_dist
        if not city:
            city, dist = extreact_city_dist(address)

        key = f"{name}_{address}_{source}"
        processed.add(key)
        
        if key in existing:
            # Update
            cursor.execute("""
                UPDATE retailers 
                SET lat=?, lng=?, city=?, district=?, isActive=1
                WHERE id=?
            """, (lat, lng, city, dist, existing[key]))
            updates += 1
        else:
            # Insert
            cursor.execute("""
                INSERT INTO retailers (name, address, city, district, source, lat, lng, isActive)
                VALUES (?, ?, ?, ?, ?, ?, ?, 1)
            """, (name, address, city, dist, source, lat, lng))
            inserts += 1

    # 首先全部標記為未營業，等等有處理到的再標回 1，這樣被撤銷的店就會在地圖上消失
    cursor.execute("UPDATE retailers SET isActive=0")

    # 2. 處理台彩
    print("處理台彩資料...")
    with open(tc_csv, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        # 台彩欄位: 地址, 投注站名稱, Google 地圖連結
        for row in reader:
            name = row.get('投注站名稱', '').strip()
            address = row.get('地址', '').strip()
            if name and address:
                process_row(name, address, "台灣彩券")

    # 3. 處理運彩
    print("處理運彩資料...")
    with open(sc_csv, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        # 運彩欄位: 縣市, 行政區, 地址, 投注站名稱, Google 地圖連結
        for row in reader:
            name = row.get('投注站名稱', '').strip()
            address = row.get('地址', '').strip()
            city = row.get('縣市', '').strip()
            dist = row.get('行政區', '').strip()
            if name and address:
                process_row(name, address, "台灣運彩", city, dist)

    conn.commit()

    # 統計
    cursor.execute("SELECT COUNT(*) FROM retailers WHERE isActive=1")
    active_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM retailers WHERE isActive=0")
    inactive_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM retailers WHERE isActive=1 AND lat IS NOT NULL")
    coords_count = cursor.fetchone()[0]

    conn.close()

    print("=== 更新完成 ===")
    print(f"新增店家: {inserts} 筆")
    print(f"更新店家: {updates} 筆")
    print(f"缺乏座標: {missing_coords} 筆")
    print(f"營業中店家總數: {active_count} 筆 (含座標: {coords_count} 筆)")
    print(f"已歇業/未在名單內: {inactive_count} 筆")

if __name__ == "__main__":
    main()
