"""
改良地理編碼腳本
策略：使用 Nominatim 搭配結構化查詢 (structured query)
台灣地址格式：「縣市 + 行政區 + 路名號碼」能大幅提升準確度
"""

import logging
import sys
import time
import re
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError

from app.model.database import SessionLocal, init_db
from app.model.retailer import Retailer

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def normalize_city(city: str) -> str:
    """統一縣市名稱（臺→台）方便 Nominatim 查詢"""
    return city.replace("臺", "台")


def clean_address_for_geocode(addr: str) -> str:
    """清洗地址：移除樓層、村里、鄰等資訊"""
    if not addr:
        return ""
    # 移除「X樓」
    cleaned = re.sub(r'\d+樓$', '', addr)
    # 移除「X之X號」→ 保留到主號
    cleaned = re.sub(r'之\d+號', '號', cleaned)
    # 移除村里鄰
    cleaned = re.sub(r'[^\s]*[村里鄰]', '', cleaned)
    return cleaned.strip()


def geocode_batch(batch_size: int = 0):
    """批次地理編碼"""
    init_db()
    db = SessionLocal()
    geolocator = Nominatim(user_agent="scratchcard_map_tw_v2", timeout=10)

    failed_log = Path(__file__).parent / "geocode_failed_v2.txt"

    try:
        retailers = db.query(Retailer).filter(Retailer.lat.is_(None)).all()
        total = len(retailers)

        if batch_size > 0:
            retailers = retailers[:batch_size]

        logger.info(f"開始地理編碼：{len(retailers)} / {total} 筆待處理")

        success = 0
        failed = 0
        failed_addresses = []

        for i, r in enumerate(retailers):
            city = normalize_city(r.city)
            district = r.district or ""
            addr_clean = clean_address_for_geocode(r.address)

            # 策略 1：結構化查詢（street + city + country）
            location = None
            try:
                # 嘗試完整地址
                location = geolocator.geocode(
                    query=addr_clean,
                    country_codes="tw",
                    language="zh-TW",
                )

                # 如果完整地址失敗，嘗試簡化版（只用路名）
                if not location:
                    # 提取路名+號碼
                    road_match = re.search(r'([^\s區鄉鎮市縣]*(?:路|街|大道|巷|弄)\S*號)', addr_clean)
                    if road_match:
                        simple_addr = f"{city}{district}{road_match.group(1)}"
                        location = geolocator.geocode(
                            query=simple_addr,
                            country_codes="tw",
                            language="zh-TW",
                        )

                # 最後嘗試：只用縣市+行政區
                if not location and city and district:
                    location = geolocator.geocode(
                        query=f"{city}{district}",
                        country_codes="tw",
                        language="zh-TW",
                    )

            except (GeocoderTimedOut, GeocoderServiceError) as e:
                logger.warning(f"  Geocoding 超時 (#{r.id} {r.name}): {e}")
            except Exception as e:
                logger.warning(f"  Geocoding 異常 (#{r.id} {r.name}): {e}")

            if location:
                r.lat = location.latitude
                r.lng = location.longitude
                success += 1
            else:
                failed += 1
                failed_addresses.append(f"{r.id}|{r.name}|{r.address}")

            # 每 50 筆 commit + 進度報告
            if (i + 1) % 50 == 0:
                db.commit()
                pct = (i + 1) / len(retailers) * 100
                logger.info(f"  進度 {i + 1}/{len(retailers)} ({pct:.1f}%) | 成功 {success} | 失敗 {failed}")

            # Nominatim 速率限制
            time.sleep(1.1)

        db.commit()

        if failed_addresses:
            with open(failed_log, "w", encoding="utf-8") as f:
                f.write("\n".join(failed_addresses))

        logger.info(f"🎉 完成！成功 {success} | 失敗 {failed} | 總計 {len(retailers)}")

    except Exception as e:
        logger.error(f"地理編碼失敗: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch", type=int, default=0)
    args = parser.parse_args()
    geocode_batch(batch_size=args.batch)
