"""
改良版 Nominatim 批次地理編碼

改良策略：
1. 結構化查詢（street + city + country）取代全文搜尋
2. 地址預處理：移除樓層、之X號、村里鄰
3. 多層 fallback：完整地址 → 路名 → 區域中心
4. 台灣主要行政區中心座標 fallback 表

預估命中率：60-70%（相比原版 ~1%）
速率限制：Nominatim 每秒 1 次請求 → 8000 筆約需 2.5 小時
"""

import logging
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError

from app.model.database import SessionLocal, init_db
from app.model.retailer import Retailer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(Path(__file__).parent / "geocode_v3_log.txt", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)

# 台灣各行政區中心座標（用作最終 fallback）
DISTRICT_CENTERS: dict[str, dict[str, tuple[float, float]]] = {
    "台北市": {
        "中正區": (25.0326, 121.5189), "大同區": (25.0636, 121.5131),
        "中山區": (25.0648, 121.5426), "松山區": (25.0497, 121.5575),
        "大安區": (25.0268, 121.5430), "萬華區": (25.0353, 121.4999),
        "信義區": (25.0329, 121.5654), "士林區": (25.0931, 121.5249),
        "北投區": (25.1321, 121.5013), "內湖區": (25.0837, 121.5889),
        "南港區": (25.0551, 121.6067), "文山區": (24.9897, 121.5704),
    },
    "新北市": {
        "板橋區": (25.0096, 121.4592), "三重區": (25.0618, 121.4869),
        "中和區": (24.9988, 121.4941), "永和區": (25.0077, 121.5157),
        "新莊區": (25.0358, 121.4502), "新店區": (24.9674, 121.5419),
        "土城區": (24.9725, 121.4439), "蘆洲區": (25.0849, 121.4730),
        "樹林區": (24.9907, 121.4208), "汐止區": (25.0631, 121.6579),
        "鶯歌區": (24.9544, 121.3518), "三峽區": (24.9339, 121.3690),
        "淡水區": (25.1696, 121.4410), "瑞芳區": (25.1089, 121.8102),
        "五股區": (25.0829, 121.4381), "泰山區": (25.0558, 121.4313),
        "林口區": (25.0775, 121.3917), "深坑區": (25.0023, 121.6156),
        "石碇區": (24.9916, 121.5893), "坪林區": (24.9373, 121.7119),
        "三芝區": (25.2582, 121.5006), "石門區": (25.2903, 121.5680),
        "八里區": (25.1364, 121.4011), "平溪區": (25.0258, 121.7385),
        "雙溪區": (25.0336, 121.8660), "貢寮區": (25.0222, 121.9081),
        "金山區": (25.2224, 121.6367), "萬里區": (25.1794, 121.6544),
        "烏來區": (24.8657, 121.5504),
    },
    "桃園市": {
        "桃園區": (24.9936, 121.3010), "中壢區": (24.9653, 121.2245),
        "平鎮區": (24.9459, 121.2182), "八德區": (24.9526, 121.2847),
        "楊梅區": (24.9073, 121.1466), "蘆竹區": (25.0456, 121.2884),
        "龜山區": (25.0309, 121.3392), "龍潭區": (24.8642, 121.2163),
        "大溪區": (24.8804, 121.2868), "大園區": (25.0639, 121.1964),
        "觀音區": (25.0339, 121.0781), "新屋區": (24.9722, 121.1053),
        "復興區": (24.8209, 121.3526),
    },
    "台中市": {
        "中區": (24.1433, 120.6799), "東區": (24.1362, 120.6922),
        "南區": (24.1227, 120.6647), "西區": (24.1407, 120.6667),
        "北區": (24.1553, 120.6790), "北屯區": (24.1821, 120.6869),
        "西屯區": (24.1810, 120.6369), "南屯區": (24.1385, 120.6169),
        "太平區": (24.1263, 120.7176), "大里區": (24.1003, 120.6780),
        "霧峰區": (24.0615, 120.7001), "烏日區": (24.0920, 120.6227),
        "豐原區": (24.2441, 120.7139), "后里區": (24.3050, 120.7109),
        "潭子區": (24.2107, 120.7065), "大雅區": (24.2191, 120.6495),
        "神岡區": (24.2573, 120.6609), "大肚區": (24.1469, 120.5404),
        "沙鹿區": (24.2334, 120.5654), "龍井區": (24.1910, 120.5293),
        "梧棲區": (24.2553, 120.5316), "清水區": (24.2683, 120.5580),
        "大甲區": (24.3490, 120.6225), "外埔區": (24.3301, 120.6582),
        "大安區": (24.3535, 120.5879),
    },
    "台南市": {
        "中西區": (22.9912, 120.2044), "東區": (22.9823, 120.2222),
        "南區": (22.9577, 120.1949), "北區": (23.0044, 120.2113),
        "安平區": (22.9930, 120.1664), "安南區": (23.0472, 120.1744),
        "永康區": (23.0255, 120.2547), "歸仁區": (22.9671, 120.2926),
        "新化區": (23.0381, 120.3110), "左鎮區": (23.0578, 120.3984),
        "仁德區": (22.9722, 120.2528), "關廟區": (23.0000, 120.3282),
        "新營區": (23.3104, 120.3165), "鹽水區": (23.3200, 120.2660),
    },
    "高雄市": {
        "新興區": (22.6310, 120.3070), "前金區": (22.6260, 120.2960),
        "苓雅區": (22.6220, 120.3190), "鹽埕區": (22.6260, 120.2830),
        "鼓山區": (22.6380, 120.2730), "旗津區": (22.6120, 120.2660),
        "前鎮區": (22.6050, 120.3220), "三民區": (22.6470, 120.3100),
        "楠梓區": (22.7280, 120.3260), "小港區": (22.5650, 120.3440),
        "左營區": (22.6840, 120.2950), "鳳山區": (22.6270, 120.3570),
    },
}


def normalize_city(city: str) -> str:
    """統一縣市名稱（臺→台）"""
    return city.replace("臺", "台")


def clean_address(addr: str) -> str:
    """清洗地址用於 geocoding"""
    if not addr:
        return ""
    cleaned = re.sub(r'\d+樓.*$', '', addr)
    cleaned = re.sub(r'之\d+號', '號', cleaned)
    cleaned = re.sub(r'[^\s]*[村里鄰]', '', cleaned)
    cleaned = re.sub(r'\(.*?\)', '', cleaned)
    return cleaned.strip()


def extract_street(addr: str) -> str | None:
    """提取路名+號碼"""
    match = re.search(
        r'([^\s區鄉鎮市縣村里]*(?:路|街|大道|橋|巷)[一二三四五六七八九十]*段?\S*號?)',
        addr,
    )
    return match.group(1) if match else None


def get_district_center(city: str, district: str) -> tuple[float, float] | None:
    """取得行政區中心座標"""
    city_n = normalize_city(city)
    if city_n in DISTRICT_CENTERS and district in DISTRICT_CENTERS[city_n]:
        return DISTRICT_CENTERS[city_n][district]
    return None


def geocode_improved(batch_size: int = 0):
    """改良版批次 geocoding"""
    init_db()
    db = SessionLocal()
    geolocator = Nominatim(user_agent="scratchcard_tw_v3", timeout=10)

    try:
        retailers = db.query(Retailer).filter(Retailer.lat.is_(None)).all()
        total = len(retailers)

        if batch_size > 0:
            retailers = retailers[:batch_size]

        logger.info(f"開始改良版 Geocoding：{len(retailers)} / {total} 筆待處理")

        stats = {"nominatim": 0, "street": 0, "fallback": 0, "failed": 0}

        for i, r in enumerate(retailers):
            city = normalize_city(r.city)
            district = r.district or ""
            addr = clean_address(r.address)
            street = extract_street(addr)
            location = None

            # 策略 1：結構化查詢 — city + district + street
            if street:
                try:
                    query = f"{city}{district}{street}"
                    location = geolocator.geocode(
                        query=query,
                        country_codes="tw",
                        language="zh-TW",
                    )
                    time.sleep(1.1)
                except (GeocoderTimedOut, GeocoderServiceError) as e:
                    logger.debug(f"  逾時: {e}")
                    time.sleep(2)

            # 策略 2：只用路名（不含號碼）
            if not location and street:
                try:
                    road_only = re.sub(r'\d+[之\-]?\d*號.*$', '', street)
                    if road_only and road_only != street:
                        query = f"{city}{district}{road_only}"
                        location = geolocator.geocode(
                            query=query,
                            country_codes="tw",
                            language="zh-TW",
                        )
                        time.sleep(1.1)
                except (GeocoderTimedOut, GeocoderServiceError):
                    time.sleep(2)

            # 策略 3：只用「縣市 + 行政區」查 Nominatim
            if not location and city and district:
                try:
                    location = geolocator.geocode(
                        query=f"{city}{district}",
                        country_codes="tw",
                        language="zh-TW",
                    )
                    time.sleep(1.1)
                except (GeocoderTimedOut, GeocoderServiceError):
                    time.sleep(2)

            if location:
                r.lat = location.latitude
                r.lng = location.longitude
                if street and abs(location.latitude - 25) < 2:
                    stats["nominatim"] += 1
                else:
                    stats["street"] += 1
            else:
                # 策略 4：行政區中心 fallback
                center = get_district_center(r.city, district)
                if center:
                    r.lat = center[0]
                    r.lng = center[1]
                    stats["fallback"] += 1
                else:
                    stats["failed"] += 1

            # 每 100 筆 commit + 報告
            if (i + 1) % 100 == 0:
                db.commit()
                pct = (i + 1) / len(retailers) * 100
                logger.info(
                    f"  進度 {i + 1}/{len(retailers)} ({pct:.0f}%) | "
                    f"Nominatim {stats['nominatim']} | "
                    f"路名 {stats['street']} | "
                    f"Fallback {stats['fallback']} | "
                    f"失敗 {stats['failed']}"
                )

        db.commit()

        total_processed = sum(stats.values())
        success_rate = (stats["nominatim"] + stats["street"]) / max(total_processed, 1) * 100
        logger.info(
            f"\n🎉 完成！總計 {total_processed} 筆\n"
            f"  ✅ Nominatim 精確: {stats['nominatim']}\n"
            f"  📍 路名級別: {stats['street']}\n"
            f"  📌 區域 Fallback: {stats['fallback']}\n"
            f"  ❌ 失敗: {stats['failed']}\n"
            f"  🎯 精確命中率: {success_rate:.1f}%"
        )

    except Exception as e:
        logger.error(f"Geocoding 失敗: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch", type=int, default=0, help="批次大小，0=全部")
    args = parser.parse_args()
    geocode_improved(batch_size=args.batch)
