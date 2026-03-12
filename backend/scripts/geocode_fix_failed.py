"""
修復 Geocoding 失敗地址

策略：
1. 先嘗試用 Nominatim 的「臺北市中正區 + 路名」查詢
2. 如果仍失敗，使用「臺北市中正區」的行政區中心座標 (25.0326, 121.5189)
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

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# 台北市中正區中心座標（fallback 用）
ZHONGZHENG_CENTER = (25.0326, 121.5189)

# 常見路名座標對照（手動建立，大幅提升命中率）
ROAD_COORDS = {
    "青島東路": (25.0435, 121.5255),
    "汀州路一段": (25.0155, 121.5150),
    "汀州路二段": (25.0125, 121.5205),
    "汀州路三段": (25.0085, 121.5255),
    "金山南路一段": (25.0340, 121.5297),
    "和平西路一段": (25.0278, 121.5100),
    "和平西路二段": (25.0260, 121.5010),
    "中華路二段": (25.0310, 121.5075),
    "南昌路一段": (25.0305, 121.5170),
    "南昌路二段": (25.0250, 121.5170),
    "寧波西街": (25.0295, 121.5145),
    "羅斯福路二段": (25.0220, 121.5220),
    "羅斯福路三段": (25.0150, 121.5230),
    "羅斯福路四段": (25.0080, 121.5332),
    "信陽街": (25.0445, 121.5148),
    "武昌街一段": (25.0445, 121.5105),
    "南海路": (25.0305, 121.5130),
    "杭州南路一段": (25.0370, 121.5268),
    "杭州南路二段": (25.0310, 121.5268),
    "延平南路": (25.0395, 121.5083),
    "忠孝西路一段": (25.0460, 121.5138),
    "忠孝東路一段": (25.0437, 121.5265),
    "重慶南路一段": (25.0425, 121.5120),
    "懷寧街": (25.0440, 121.5115),
    "濟南路二段": (25.0405, 121.5260),
    "博愛路": (25.0450, 121.5105),
    "漢口街一段": (25.0453, 121.5125),
    "牯嶺街": (25.0290, 121.5157),
    "同安街": (25.0115, 121.5210),
}


def extract_road(address: str) -> str | None:
    """從地址中提取路名"""
    # 先嘗試「X路Y段」格式
    match = re.search(r'([^\s區鄉鎮市縣]*(?:路|街|大道)[一二三四五六七八九十]*段?)', address)
    if match:
        return match.group(1)
    return None


def fix_failed_geocoding():
    """修復失敗的 geocoding 地址"""
    init_db()
    db = SessionLocal()
    geolocator = Nominatim(user_agent="scratchcard_map_tw_fix", timeout=10)

    failed_file = Path(__file__).parent / "geocode_failed.txt"
    if not failed_file.exists():
        logger.info("沒有找到 geocode_failed.txt")
        return

    lines = failed_file.read_text(encoding="utf-8").strip().split("\n")
    logger.info(f"讀取 {len(lines)} 筆失敗地址")

    success = 0
    fallback = 0
    still_failed = 0

    try:
        for line in lines:
            parts = line.strip().split("|")
            if len(parts) < 3:
                continue

            rid = int(parts[0])
            name = parts[1]
            address = parts[2]

            retailer = db.query(Retailer).filter(Retailer.id == rid).first()
            if not retailer or retailer.lat is not None:
                continue  # 已有座標或找不到

            # 策略 1：嘗試 Nominatim（用「台北市中正區 + 路名」）
            road = extract_road(address)
            location = None

            if road:
                try:
                    query_str = f"台北市中正區{road}"
                    location = geolocator.geocode(
                        query=query_str,
                        country_codes="tw",
                        language="zh-TW",
                    )
                    time.sleep(1.1)
                except (GeocoderTimedOut, GeocoderServiceError):
                    pass

            if location:
                retailer.lat = location.latitude
                retailer.lng = location.longitude
                success += 1
                logger.info(f"  ✅ #{rid} {name} -> Nominatim ({location.latitude:.4f}, {location.longitude:.4f})")
            else:
                # 策略 2：使用路名座標對照表
                coords = None
                if road:
                    for road_key, road_coords in ROAD_COORDS.items():
                        if road_key in road:
                            coords = road_coords
                            break

                if coords:
                    retailer.lat = coords[0]
                    retailer.lng = coords[1]
                    fallback += 1
                    logger.info(f"  📍 #{rid} {name} -> 路名對照 ({coords[0]:.4f}, {coords[1]:.4f})")
                else:
                    # 最後 fallback：中正區中心
                    retailer.lat = ZHONGZHENG_CENTER[0]
                    retailer.lng = ZHONGZHENG_CENTER[1]
                    fallback += 1
                    logger.info(f"  📌 #{rid} {name} -> 區域中心 fallback")

        db.commit()
        logger.info(f"🎉 修復完成！Nominatim 成功 {success} | 座標對照 {fallback} | 仍失敗 {still_failed}")

    except Exception as e:
        logger.error(f"修復失敗: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    fix_failed_geocoding()
