"""
TGOS WGS84 座標匯入腳本
將 'Address_Finish - Address_Finish.csv' 中的 WGS84 經緯度寫入 retailers 資料表
CSV 欄位: id, Address, Response_Address, Response_X(經度), Response_Y(緯度)
使用地址比對方式更新資料庫中的經銷商座標
"""
import csv
import sqlite3
import sys
import os

# 台灣合理範圍
LAT_MIN, LAT_MAX = 21.5, 26.5
LNG_MIN, LNG_MAX = 119.0, 122.5


def normalize_address(addr: str) -> str:
    """統一地址格式：臺→台，移除多餘空白"""
    return addr.strip().replace("臺", "台")


def main():
    # 路徑設定
    script_dir = os.path.dirname(os.path.abspath(__file__))
    csv_path = os.path.join(script_dir, '..', 'Address_Finish - Address_Finish.csv')
    db_path = os.path.join(script_dir, 'scratchcard.db')

    if not os.path.exists(csv_path):
        print(f"❌ 找不到 CSV: {csv_path}")
        sys.exit(1)

    if not os.path.exists(db_path):
        print(f"❌ 找不到資料庫: {db_path}")
        sys.exit(1)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # 建立地址 → retailer id 的對照表
    cursor.execute('SELECT id, address FROM retailers')
    addr_to_ids: dict[str, list[int]] = {}
    for rid, addr in cursor.fetchall():
        norm = normalize_address(addr)
        if norm not in addr_to_ids:
            addr_to_ids[norm] = []
        addr_to_ids[norm].append(rid)

    updated = 0
    skipped_no_coords = 0
    skipped_out_of_range = 0
    no_match = 0

    with open(csv_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        total = 0
        for row in reader:
            total += 1
            raw_x = row.get('Response_X', '').strip()
            raw_y = row.get('Response_Y', '').strip()
            csv_addr = row.get('Address', '').strip()

            # 跳過空座標
            if not raw_x or not raw_y:
                skipped_no_coords += 1
                continue

            try:
                lng = float(raw_x)
                lat = float(raw_y)
            except ValueError:
                skipped_no_coords += 1
                continue

            # 合理性檢查
            if not (LAT_MIN < lat < LAT_MAX and LNG_MIN < lng < LNG_MAX):
                skipped_out_of_range += 1
                continue

            # 用地址配對
            norm_csv_addr = normalize_address(csv_addr)
            matched_ids = addr_to_ids.get(norm_csv_addr, [])

            if not matched_ids:
                no_match += 1
                continue

            # 更新所有配對到的 retailer
            for rid in matched_ids:
                cursor.execute(
                    'UPDATE retailers SET lat = ?, lng = ? WHERE id = ?',
                    (round(lat, 7), round(lng, 7), rid)
                )
                updated += 1

    conn.commit()

    # 統計
    cursor.execute('SELECT COUNT(*) FROM retailers WHERE lat IS NOT NULL AND lat != 0')
    total_with_coords = cursor.fetchone()[0]
    cursor.execute('SELECT COUNT(*) FROM retailers')
    total_retailers = cursor.fetchone()[0]

    conn.close()

    print(f"\n{'='*50}")
    print(f"[OK] TGOS WGS84 座標匯入完成")
    print(f"{'='*50}")
    print(f"  CSV 總筆數: {total}")
    print(f"  成功更新: {updated}")
    print(f"  無座標（跳過）: {skipped_no_coords}")
    print(f"  座標超出範圍: {skipped_out_of_range}")
    print(f"  地址無法配對: {no_match}")
    print(f"  DB 有座標: {total_with_coords} / {total_retailers}")
    print(f"  覆蓋率: {total_with_coords/total_retailers*100:.1f}%")


if __name__ == '__main__':
    main()
