import os
import shutil
import logging
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)

# 設定根目錄與備份目錄
BACKEND_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BACKEND_DIR / "scratchcard.db"
BACKUP_DIR = BACKEND_DIR / "backups"
RETAIN_DAYS = 14

def backup_sqlite():
    """備份 SQLite 資料庫並清理舊備份"""
    if not DB_PATH.exists():
        logger.warning(f"找不到資料庫檔案：{DB_PATH}，略過備份。")
        return

    try:
        # 確保備份資料夾存在
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)

        # 建立新備份 (格式: scratchcard_YYYY-MM-DD_HHMMSS.db)
        timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        backup_filename = f"scratchcard_{timestamp}.db"
        backup_path = BACKUP_DIR / backup_filename

        shutil.copy2(DB_PATH, backup_path)
        logger.info(f"✅ 資料庫備份成功：{backup_path.name}")

        # 清理超過 N 天的舊備份
        cleanup_old_backups()

    except Exception as e:
        logger.error(f"❌ 資料庫備份失敗: {e}", exc_info=True)

def cleanup_old_backups():
    """清理超過 RETAIN_DAYS 天的舊備份檔案"""
    cutoff_date = datetime.now() - timedelta(days=RETAIN_DAYS)
    deleted_count = 0

    for idx, backup_file in enumerate(BACKUP_DIR.glob("scratchcard_*.db")):
        try:
            # 檔案修改時間早於 cutoff_date
            file_mtime = datetime.fromtimestamp(backup_file.stat().st_mtime)
            if file_mtime < cutoff_date:
                backup_file.unlink()
                deleted_count += 1
                logger.debug(f"已刪除過期備份：{backup_file.name}")
        except Exception as e:
            logger.warning(f"無法刪除舊備份 {backup_file.name}: {e}")

    if deleted_count > 0:
        logger.info(f"🧹 已清理 {deleted_count} 個超過 {RETAIN_DAYS} 天的舊備份。")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    backup_sqlite()
