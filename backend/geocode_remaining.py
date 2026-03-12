"""
補齊剩餘無座標的經銷商
使用 Nominatim (OpenStreetMap) 免費 geocoding 服務
遵循 1 秒/次的速率限制
"""
import sqlite3
import time
import urllib.request
import urllib.parse
import json
import sys


def geocode_nominatim(address: str) -> tuple[float, float] | None:
    """
    用 Nominatim 查詢地址座標
    回傳 (lat, lng) 或 None
    """
    # 清理地址（移除台灣地址中常見的干擾字元）
    clean = address.replace('臺', '台').strip()

    params = urllib.parse.urlencode({
        'q': clean,
        'format': 'json',
        'limit': 1,
        'countrycodes': 'tw',
    })
    url = f'https://nominatim.openstreetmap.org/search?{params}'

    req = urllib.request.Request(url, headers={
        'User-Agent': 'ScratchcardWebsite/1.0 (geocoding for lottery retailers)',
    })

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            if data:
                lat = float(data[0]['lat'])
                lon = float(data[0]['lon'])
                # 台灣範圍驗證
                if 21.5 < lat < 26.5 and 119.0 < lon < 122.5:
                    return lat, lon
    except Exception as e:
        print(f'  ⚠️ 請求失敗: {e}')

    return None


def main():
    db_path = 'scratchcard.db'
    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    # 取得無座標的經銷商
    c.execute('SELECT id, address, city, district FROM retailers WHERE lat IS NULL OR lat = 0')
    rows = c.fetchall()
    total = len(rows)
    print(f'📍 需要補齊 {total} 筆經銷商座標')
    print(f'   使用 Nominatim (OSM) geocoding，每秒 1 次請求')
    print()

    updated = 0
    failed = 0

    for i, (rid, address, city, district) in enumerate(rows, 1):
        print(f'[{i}/{total}] ID={rid} {address}', end=' ... ')

        # 嘗試完整地址
        result = geocode_nominatim(address)

        # 如果失敗，嘗試簡化地址（只用縣市+區+路名）
        if not result and city and district:
            # 從地址中提取路名部分
            simplified = f'{city}{district}'
            # 找到路/街/巷 之後的部分去掉門牌號
            for sep in ['路', '街', '巷', '號']:
                idx = address.find(sep)
                if idx >= 0:
                    simplified = address[:idx + 1]
                    break
            if simplified != address:
                result = geocode_nominatim(simplified)

        if result:
            lat, lng = result
            c.execute('UPDATE retailers SET lat = ?, lng = ? WHERE id = ?',
                      (round(lat, 7), round(lng, 7), rid))
            updated += 1
            print(f'✅ ({lat:.5f}, {lng:.5f})')
        else:
            failed += 1
            print('❌ 找不到')

        # 遵守速率限制
        time.sleep(1.1)

    conn.commit()

    # 最終統計
    c.execute('SELECT COUNT(*) FROM retailers WHERE lat IS NOT NULL AND lat != 0')
    total_with = c.fetchone()[0]
    c.execute('SELECT COUNT(*) FROM retailers')
    grand_total = c.fetchone()[0]
    conn.close()

    print(f'\n{"="*50}')
    print(f'✅ Nominatim 補齊完成')
    print(f'{"="*50}')
    print(f'  成功補齊: {updated} 筆')
    print(f'  仍無座標: {failed} 筆')
    print(f'  DB 有座標: {total_with} / {grand_total} ({total_with/grand_total*100:.1f}%)')


if __name__ == '__main__':
    main()
