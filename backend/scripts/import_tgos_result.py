"""
匯入 TGOS 批次比對結果，更新經銷商座標
TGOS 回傳 CSV 格式：id,Address,Response_Address,Response_X,Response_Y
X = 經度(lng), Y = 緯度(lat)（EPSG:4326 WGS84）
"""

import csv
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.model.database import SessionLocal, init_db
from app.model.retailer import Retailer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


def import_result(csv_path: str):
    """
    匯入 TGOS 批次比對結果 CSV
    Args:
        csv_path: TGOS 比對結果 CSV 檔案路徑
    """
    init_db()
    db = SessionLocal()

    csv_file = Path(csv_path)
    if not csv_file.exists():
        logger.error(f"❌ 檔案不存在: {csv_path}")
        return

    try:
        success = 0
        failed = 0
        skipped = 0

        with open(csv_file, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)

            for row in reader:
                retailer_id = row.get("id", "").strip()
                resp_x = row.get("Response_X", "").strip()
                resp_y = row.get("Response_Y", "").strip()

                if not retailer_id:
                    skipped += 1
                    continue

                # 檢查是否有回傳座標
                if not resp_x or not resp_y:
                    failed += 1
                    continue

                try:
                    rid = int(retailer_id)
                    lng = float(resp_x)  # X = 經度
                    lat = float(resp_y)  # Y = 緯度

                    # 基本座標合理性檢查（台灣範圍）
                    if not (21.0 <= lat <= 26.5 and 119.0 <= lng <= 123.0):
                        logger.warning(
                            f"  ⚠️ ID={rid} 座標超出台灣範圍: ({lat}, {lng})，跳過"
                        )
                        failed += 1
                        continue

                    retailer = db.query(Retailer).filter(Retailer.id == rid).first()
                    if retailer:
                        retailer.lat = lat
                        retailer.lng = lng
                        success += 1
                    else:
                        logger.warning(f"  ⚠️ ID={rid} 在資料庫中找不到")
                        skipped += 1

                except (ValueError, TypeError) as e:
                    logger.warning(f"  ⚠️ 資料格式錯誤 ID={retailer_id}: {e}")
                    failed += 1

                # 每 500 筆 commit
                if (success + failed) % 500 == 0 and success > 0:
                    db.commit()
                    logger.info(f"  📊 已處理 {success + failed} 筆...")

        db.commit()
        logger.info(
            f"🎉 匯入完成！ ✅ 成功 {success} | ❌ 失敗 {failed} | ⏭️ 跳過 {skipped}"
        )

        # 統計剩餘未 geocoding 的數量
        remaining = db.query(Retailer).filter(Retailer.lat.is_(None)).count()
        total = db.query(Retailer).count()
        logger.info(f"📊 座標完成率：{total - remaining}/{total}（剩餘 {remaining} 筆）")

    except Exception as e:
        logger.error(f"❌ 匯入失敗: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="匯入 TGOS 批次比對結果")
    parser.add_argument("csv_file", help="TGOS 比對結果 CSV 檔案路徑")
    args = parser.parse_args()

    import_result(args.csv_file)
