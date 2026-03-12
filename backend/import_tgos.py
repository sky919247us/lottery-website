"""
TGOS 座標匯入腳本
將 Address_Finish.csv 中的 TWD97 TM2 座標轉換為 WGS84 並更新 retailers 資料表
"""
import csv
import math
import sqlite3
import sys
import os

# TWD97 TM2 (EPSG:3826) → WGS84 (EPSG:4326) 轉換
# 基於 Transverse Mercator 逆投影公式

# TWD97 橢球體參數 (GRS80)
A = 6378137.0  # 長半軸
F = 1 / 298.257222101  # 扁率
B = A * (1 - F)  # 短半軸
E2 = 2 * F - F ** 2  # 第一偏心率平方
E_PRIME2 = E2 / (1 - E2)  # 第二偏心率平方

# TM2 投影參數
K0 = 0.9999  # 中央經線尺度因子
LON0 = 121.0  # 中央經線（度）
FALSE_EASTING = 250000  # 假東距
FALSE_NORTHING = 0  # 假北距


def twd97_to_wgs84(x: float, y: float) -> tuple[float, float]:
    """
    TWD97 TM2 座標 (E, N) 轉換為 WGS84 經緯度
    回傳 (lat, lng) 以度為單位
    """
    # 移除偏移量
    x -= FALSE_EASTING
    y -= FALSE_NORTHING

    # 計算底點緯度 (footpoint latitude)
    m = y / K0
    mu = m / (A * (1 - E2 / 4 - 3 * E2 ** 2 / 64 - 5 * E2 ** 3 / 256))

    e1 = (1 - math.sqrt(1 - E2)) / (1 + math.sqrt(1 - E2))

    phi1 = mu + (3 * e1 / 2 - 27 * e1 ** 3 / 32) * math.sin(2 * mu) \
         + (21 * e1 ** 2 / 16 - 55 * e1 ** 4 / 32) * math.sin(4 * mu) \
         + (151 * e1 ** 3 / 96) * math.sin(6 * mu) \
         + (1097 * e1 ** 4 / 512) * math.sin(8 * mu)

    # 計算各輔助值
    n1 = A / math.sqrt(1 - E2 * math.sin(phi1) ** 2)
    t1 = math.tan(phi1) ** 2
    c1 = E_PRIME2 * math.cos(phi1) ** 2
    r1 = A * (1 - E2) / (1 - E2 * math.sin(phi1) ** 2) ** 1.5
    d = x / (n1 * K0)

    # 計算緯度
    lat = phi1 - (n1 * math.tan(phi1) / r1) * (
        d ** 2 / 2
        - (5 + 3 * t1 + 10 * c1 - 4 * c1 ** 2 - 9 * E_PRIME2) * d ** 4 / 24
        + (61 + 90 * t1 + 298 * c1 + 45 * t1 ** 2 - 252 * E_PRIME2 - 3 * c1 ** 2) * d ** 6 / 720
    )

    # 計算經度
    lon = math.radians(LON0) + (
        d
        - (1 + 2 * t1 + c1) * d ** 3 / 6
        + (5 - 2 * c1 + 28 * t1 - 3 * c1 ** 2 + 8 * E_PRIME2 + 24 * t1 ** 2) * d ** 5 / 120
    ) / math.cos(phi1)

    return math.degrees(lat), math.degrees(lon)


def main():
    csv_path = os.path.join(os.path.dirname(__file__), '..', 'Address_Finish.csv')
    db_path = os.path.join(os.path.dirname(__file__), 'scratchcard.db')

    if not os.path.exists(csv_path):
        print(f"❌ 找不到 CSV: {csv_path}")
        sys.exit(1)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    updated = 0
    skipped_empty = 0
    skipped_multi = 0
    errors = 0

    with open(csv_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            retailer_id = int(row['id'])
            raw_x = row['Response_X'].strip()
            raw_y = row['Response_Y'].strip()

            # 跳過空座標（找不到地址）
            if not raw_x or not raw_y:
                skipped_empty += 1
                continue

            # 處理多結果（取第一個）
            if ';' in raw_x:
                raw_x = raw_x.split(';')[0]
                raw_y = raw_y.split(';')[0]
                skipped_multi += 1  # 仍然匯入，只是標記

            try:
                x = float(raw_x)
                y = float(raw_y)
                lat, lng = twd97_to_wgs84(x, y)

                # 基本合理性檢查（台灣範圍）
                if not (21.5 < lat < 26.5 and 119.0 < lng < 122.5):
                    print(f"⚠️  ID {retailer_id} 座標異常: lat={lat:.6f}, lng={lng:.6f}")
                    errors += 1
                    continue

                cursor.execute(
                    'UPDATE retailers SET lat = ?, lng = ? WHERE id = ?',
                    (round(lat, 7), round(lng, 7), retailer_id)
                )
                updated += 1

            except (ValueError, ZeroDivisionError) as e:
                print(f"❌ ID {retailer_id} 轉換失敗: {e}")
                errors += 1

    conn.commit()

    # 統計結果
    cursor.execute('SELECT COUNT(*) FROM retailers WHERE lat IS NOT NULL AND lat != 0')
    total_with_coords = cursor.fetchone()[0]
    cursor.execute('SELECT COUNT(*) FROM retailers')
    total = cursor.fetchone()[0]

    conn.close()

    print(f"\n{'='*50}")
    print(f"✅ TGOS 座標匯入完成")
    print(f"{'='*50}")
    print(f"  成功更新: {updated} 筆")
    print(f"  多結果（取第一筆）: {skipped_multi} 筆")
    print(f"  空座標（找不到）: {skipped_empty} 筆")
    print(f"  轉換錯誤/異常: {errors} 筆")
    print(f"  DB 有座標: {total_with_coords} / {total} 筆")
    print(f"  覆蓋率: {total_with_coords/total*100:.1f}%")


if __name__ == '__main__':
    main()
