import csv
import logging
import re
import time
from io import StringIO
from unidecode import unidecode
import requests
from sqlalchemy.orm import Session
from sqlalchemy.exc import OperationalError
from tenacity import retry, stop_after_attempt, wait_exponential

from app.model.database import SessionLocal
from app.model.retailer import Retailer

logger = logging.getLogger(__name__)

# 台彩第五屆頭獎商店明細 CSV 網址
# 根據台彩官網按鈕：`<a href="history/store/daily_cash" download="第5屆頭獎商店明細 (每日00:00更新).csv">`
# 決定完整網址為 https://www.taiwanlottery.com/lotto/history/store/daily_cash
LOTTERY_JACKPOT_CSV_URL = "https://www.taiwanlottery.com/lotto/history/store/daily_cash"


def normalize_string(s: str) -> str:
    """標準化字串：全形轉半形、移除全部空白、轉小寫"""
    if not s:
        return ""
    # 取代全形與全形空白
    s = s.replace('　', '').replace(' ', '')
    
    # 建立全形對半形的轉換表
    full_chars = "０１２３４５６７８９ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺａｂｃｄｅｆｇｈｉｊｋｌｍｎｏｐｑｒｓｔｕｖｗｘｙｚ－"
    half_chars = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz-"
    trans_table = str.maketrans(full_chars, half_chars)
    
    s = s.translate(trans_table).lower()
    
    # 常見字眼統一
    s = s.replace('台', '臺')
    return s

def extract_core_address(s: str) -> str:
    """提取核心地址，去掉縣市、鄉鎮市區、村里、以及樓層"""
    s = normalize_string(s)
    # 移除「xx市」「xx縣」「xx區」「xx鎮」「xx鄉」
    s = re.sub(r'^.*?(市|縣)(.*?(區|鎮|鄉|市))?', '', s)
    # 移除「xx村」「xx里」
    s = re.sub(r'[^號路街段]+?(村|里)', '', s)
    # 移除所有「xx鄰」
    s = re.sub(r'\d+鄰', '', s)
    # 移除最後的「一樓」「1樓」「1f」
    s = re.sub(r'(一樓|1樓|1f)$', '', s)
    # 去除多餘字符
    s = s.replace('(', '').replace(')', '').replace('（', '').replace('）', '')
    return s


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10), reraise=True)
def download_jackpot_csv() -> str:
    """下載台彩頭獎 CSV，包含重試機制"""
    logger.info("正在連線台彩官網下載 CSV...")
    response = requests.get(LOTTERY_JACKPOT_CSV_URL, timeout=15)
    response.raise_for_status()
    
    # 強制使用 utf-8-sig 解碼
    try:
        csv_text = response.content.decode('utf-8-sig')
    except UnicodeDecodeError:
        csv_text = response.content.decode('big5', errors='ignore')
        
    if "<!DOCTYPE html>" in csv_text:
        raise ValueError("下載到的是 HTML 網頁而非 CSV 檔案 (可能維護中或阻擋爬蟲)")
        
    return csv_text


def sync_jackpot_stores():
    """
    爬取台彩第五屆頭獎商店明細 CSV，計算各店頭獎次數，並更新資料庫
    """
    logger.info("開始執行同步台彩頭獎店家資料 (sync_jackpot_stores)")
    try:
        try:
            csv_text = download_jackpot_csv()
        except Exception as retry_err:
            logger.error(f"無法從台彩官網下載正確的 CSV (已重試 3 次): {retry_err}，嘗試讀取本機備用檔案。")
            with open(r"d:\Downloads\JackpotStores (1).csv", "r", encoding="utf-8-sig") as f:
                csv_text = f.read()

        csv_file = StringIO(csv_text)
        reader = csv.DictReader(csv_file)
        
        # 統計每個地址/店名的頭獎次數
        # Key: (標準化店名, 標準化地址) -> Count
        jackpot_counts = {}
        
        for row in reader:
            # CSV 欄位：遊戲別,期別,開獎日期,售出頭獎商店名稱,售出頭獎商店地址
            store_name = row.get('售出頭獎商店名稱', '').strip()
            store_addr = row.get('售出頭獎商店地址', '').strip()
            
            if not store_name or not store_addr:
                continue
                
            norm_name = normalize_string(store_name)
            # 取得核心地址用於比對
            core_addr = extract_core_address(store_addr)
            
            key = (norm_name, core_addr)
            jackpot_counts[key] = jackpot_counts.get(key, 0) + 1
            
        logger.info(f"成功解析 CSV，共有 {sum(jackpot_counts.values())} 筆頭獎紀錄，分布於 {len(jackpot_counts)} 家商店。")
        
    except Exception as e:
        logger.error(f"下載或解析台彩頭獎 CSV 失敗: {e}", exc_info=True)
        return

    # 第一階段：唯讀查詢所有店家
    db = SessionLocal()
    try:
        all_retailers = db.query(Retailer).all()
        # 建立快速尋找字典
        exact_map = {}
        addr_map = {}
        for r in all_retailers:
            core_a = extract_core_address(r.address)
            exact_map[(normalize_string(r.name), core_a)] = r
            addr_map[core_a] = r
            
        # 決定每家店的新 jackpotCount
        # 僅有從台彩官網比對到的店家才會被加入 updates 字典中，配對不到的將保留原始數值
        updates = {}
        
        match_count = 0
        for (norm_name, core_addr), count in jackpot_counts.items():
            if not core_addr:
                continue

            retailer = exact_map.get((norm_name, core_addr))
            if not retailer:
                retailer = addr_map.get(core_addr)
                
            if retailer:
                updates[retailer.id] = count
                match_count += 1
            else:
                logger.debug(f"找不到對應店家: {norm_name} - {core_addr}")
                
        logger.info(f"準備更新資料庫。成功配對 {match_count}/{len(jackpot_counts)} 家頭獎商店。")
    except Exception as e:
        logger.error(f"查詢店家資料失敗: {e}", exc_info=True)
        return
    finally:
        db.close()

    # 第二階段：分批更新，避開長時間鎖定 Transaction
    # 將所有 ID 分組，每組 200 筆更新
    batch_size = 200
    update_items = list(updates.items())
    
    for i in range(0, len(update_items), batch_size):
        batch = update_items[i:i + batch_size]
        
        db = SessionLocal()
        try:
            for attempt in range(5):
                try:
                    for r_id, count in batch:
                        db.query(Retailer).filter(Retailer.id == r_id).update({"jackpotCount": count})
                    db.commit()
                    break
                except OperationalError as oe:
                    db.rollback()
                    if "database is locked" in str(oe):
                        logger.warning(f"資料庫鎖定中 (Batch {i//batch_size})，等待 2 秒重試... ({attempt+1}/5)")
                        time.sleep(2)
                    else:
                        raise oe
        except Exception as e:
            logger.error(f"更新頭獎資料庫失敗 (Batch {i//batch_size}): {e}", exc_info=True)
        finally:
            db.close()
            
    logger.info("同步台彩頭獎店家資料完成。")

if __name__ == "__main__":
    # 測試腳本
    logging.basicConfig(level=logging.INFO)
    sync_jackpot_stores()
