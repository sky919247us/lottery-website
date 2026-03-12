"""
批次 Geocoding 腳本 v2
使用 geopy Nominatim 對缺座標的經銷商進行地址轉座標
改進地址清理策略：移除樓層、之字、簡化非標準格式
"""
import sqlite3
import time
import re
import os
from geopy.geocoders import Nominatim

DB_PATH = os.path.join(os.path.dirname(__file__), 'scratchcard.db')

# 台灣經緯度合理範圍
LAT_MIN, LAT_MAX = 21.5, 26.5
LNG_MIN, LNG_MAX = 119.0, 122.5

geolocator = Nominatim(user_agent="scratchcard-website-v2", timeout=10)


def clean_address(addr: str) -> list[str]:
    """
    清理地址並生成多個候選查詢字串
    回傳由精確到粗略的候選列表
    """
    # 統一用字
    addr = addr.replace("臺", "台").strip()
    
    candidates = []
    
    # 1. 原始地址
    candidates.append(addr)
    
    # 2. 去除樓層資訊（1樓、2F 等）
    no_floor = re.sub(r'\d+[樓F].*$', '', addr).strip()
    if no_floor and no_floor != addr:
        candidates.append(no_floor)
    
    # 3. 只保留到路名+號
    match = re.match(r'(.+?[路街道巷弄]\S*?\d+號)', addr)
    if match:
        candidates.append(match.group(1))
    
    # 4. 只保留到路名（去掉號碼）
    match2 = re.match(r'(.+?[路街道])', addr)
    if match2:
        candidates.append(match2.group(1))
    
    # 5. 加上 "Taiwan" 後綴提升精確度
    candidates = [c + ", Taiwan" for c in candidates]
    
    return candidates


def geocode_with_retry(address: str) -> tuple[float, float] | None:
    """嘗試多種地址格式進行 geocoding"""
    candidates = clean_address(address)
    
    for i, query in enumerate(candidates):
        try:
            location = geolocator.geocode(query)
            if location:
                lat, lng = location.latitude, location.longitude
                if LAT_MIN < lat < LAT_MAX and LNG_MIN < lng < LNG_MAX:
                    if i > 0:
                        print(f"    (使用候選 #{i+1}: {query})")
                    return lat, lng
            time.sleep(1.1)  # Nominatim 速率限制
        except Exception as e:
            print(f"    ⚠️ 查詢失敗: {e}")
            time.sleep(2)
    
    return None


def main():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    c.execute("""
        SELECT id, name, address, city 
        FROM retailers 
        WHERE lat IS NULL OR lat = 0 OR lng IS NULL OR lng = 0
        ORDER BY id
    """)
    missing = c.fetchall()
    
    print(f"🔍 找到 {len(missing)} 筆缺座標的經銷商")
    print("=" * 60)
    
    success = 0
    failed = 0
    failed_list = []
    
    for i, (rid, name, address, city) in enumerate(missing):
        print(f"[{i+1}/{len(missing)}] {name}")
        print(f"    地址: {address}")
        
        result = geocode_with_retry(address)
        
        if result:
            lat, lng = result
            c.execute(
                "UPDATE retailers SET lat = ?, lng = ? WHERE id = ?",
                (round(lat, 7), round(lng, 7), rid)
            )
            print(f"    ✅ {lat:.6f}, {lng:.6f}")
            success += 1
        else:
            print(f"    ❌ 全部候選地址均無法定位")
            failed += 1
            failed_list.append(f"{rid}|{name}|{address}")
        
        time.sleep(1.1)
    
    conn.commit()
    
    # 最終統計
    c.execute('SELECT COUNT(*) FROM retailers WHERE lat IS NOT NULL AND lat != 0')
    total_with = c.fetchone()[0]
    c.execute('SELECT COUNT(*) FROM retailers')
    total = c.fetchone()[0]
    
    conn.close()
    
    print(f"\n{'=' * 60}")
    print(f"✅ 批次 Geocoding v2 完成")
    print(f"{'=' * 60}")
    print(f"  成功: {success} 筆")
    print(f"  失敗: {failed} 筆")
    print(f"  DB 有座標: {total_with} / {total} 筆 ({total_with/total*100:.1f}%)")
    
    if failed_list:
        print(f"\n❌ 無法定位的店家:")
        for item in failed_list:
            print(f"  {item}")


if __name__ == "__main__":
    main()
