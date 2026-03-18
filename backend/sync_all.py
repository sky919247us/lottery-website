import asyncio
import logging
import sys
import os

# 設定路徑以便匯入 app
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.api.cache import clear_cache
from app.service.crawler_service import run_crawler
from scripts.import_retailers import import_retailers

# 設定日誌
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("sync_all.log", encoding="utf-8")
    ]
)
logger = logging.getLogger("sync_all")

async def main():
    logger.info("============== 啟動全系統資料同步 ==============")
    
    # 1. 執行刮刮樂爬蟲
    try:
        logger.info("Step 1: 正在執行刮刮樂爬蟲 (官網資料)...")
        count = await run_crawler()
        logger.info(f"Step 1 完成：共更新 {count} 筆刮刮樂資料。")
    except Exception as e:
        logger.error(f"Step 1 失敗: {e}")

    # 2. 執行經銷商匯入 (Excel)
    try:
        logger.info("Step 2: 正在匯入經銷商資料 (Excel)...")
        import_retailers()
        logger.info("Step 2 完成。")
    except Exception as e:
        logger.error(f"Step 2 失敗: {e}")

    # 清除 API 快取，確保下次請求取得最新資料
    clear_cache()
    logger.info("已清除 API 快取。")

    logger.info("============== 同步程序全部結束 ==============")

if __name__ == "__main__":
    asyncio.run(main())
