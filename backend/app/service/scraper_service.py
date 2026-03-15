"""
頭獎店家同步服務

從台彩官方 CDN 下載頭獎店家 CSV，使用 Upsert 邏輯寫入 JackpotStore 表，
再聚合計算各經銷商的 jackpotCount。

CSV 來源：https://cdn.taiwanlottery.com.tw/app/FilesForDownload/Download/JackpotLocation/5th/Jackpot_stores.csv
每日 00:00 更新，我們的排程每日 02:00 爬取。

Upsert 策略：
- Unique Key: (gameType, period, storeName)
- 不存在 → Insert
- 已存在但內容有變 → Update
"""

import csv
import logging
import re
import time
from io import StringIO

import requests
from sqlalchemy.orm import Session
from sqlalchemy.exc import OperationalError, IntegrityError
from tenacity import retry, stop_after_attempt, wait_exponential

from app.model.database import SessionLocal
from app.model.retailer import Retailer
from app.model.jackpot_store import JackpotStore

logger = logging.getLogger(__name__)

# 台彩第五屆頭獎商店 CSV（CDN 版本，每日 00:00 更新）
LOTTERY_JACKPOT_CSV_URL = "https://cdn.taiwanlottery.com.tw/app/FilesForDownload/Download/JackpotLocation/5th/Jackpot_stores.csv"


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
    logger.info(f"正在連線台彩 CDN 下載頭獎 CSV: {LOTTERY_JACKPOT_CSV_URL}")
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


def _db_retry(func, max_attempts: int = 5, wait_seconds: float = 2.0):
    """SQLite database is locked 自動重試包裝"""
    for attempt in range(max_attempts):
        try:
            return func()
        except OperationalError as oe:
            if "database is locked" in str(oe) and attempt < max_attempts - 1:
                logger.warning(f"資料庫鎖定中，等待 {wait_seconds} 秒重試... ({attempt+1}/{max_attempts})")
                time.sleep(wait_seconds)
            else:
                raise


def sync_jackpot_stores():
    """
    同步台彩頭獎店家資料（Upsert 版本）

    流程：
    1. 下載 CSV
    2. 逐行解析，使用 (gameType, period, storeName) 做 Upsert 寫入 JackpotStore 表
    3. 從 JackpotStore 聚合計算各經銷商的 jackpotCount，更新 Retailer 表
    """
    logger.info("開始執行同步台彩頭獎店家資料 (sync_jackpot_stores) — Upsert 版本")

    # === 第一步：下載並解析 CSV ===
    try:
        csv_text = download_jackpot_csv()
    except Exception as e:
        logger.error(f"無法從台彩 CDN 下載 CSV (已重試 3 次): {e}")
        return

    csv_file = StringIO(csv_text)
    reader = csv.DictReader(csv_file)

    # 解析所有 CSV 行
    csv_rows = []
    for row in reader:
        game_type = row.get('遊戲別', '').strip()
        period = row.get('期別', '').strip()
        draw_date = row.get('開獎日期', '').strip()
        store_name = row.get('售出頭獎商店名稱', '').strip()
        store_address = row.get('售出頭獎商店地址', '').strip()

        if not game_type or not period or not store_name:
            continue

        csv_rows.append({
            'gameType': game_type,
            'period': period,
            'drawDate': draw_date,
            'storeName': store_name,
            'storeAddress': store_address,
        })

    logger.info(f"成功解析 CSV，共有 {len(csv_rows)} 筆頭獎紀錄。")

    # === 第二步：Upsert 寫入 JackpotStore 表 ===
    inserted = 0
    updated = 0
    skipped = 0

    db: Session = SessionLocal()
    try:
        for row_data in csv_rows:
            try:
                # 查詢是否已存在（依 Unique Key）
                existing = db.query(JackpotStore).filter(
                    JackpotStore.gameType == row_data['gameType'],
                    JackpotStore.period == row_data['period'],
                    JackpotStore.storeName == row_data['storeName'],
                ).first()

                if existing:
                    # 檢查是否有變更
                    changed = False
                    if existing.drawDate != row_data['drawDate']:
                        existing.drawDate = row_data['drawDate']
                        changed = True
                    if existing.storeAddress != row_data['storeAddress']:
                        existing.storeAddress = row_data['storeAddress']
                        changed = True

                    if changed:
                        updated += 1
                    else:
                        skipped += 1
                else:
                    # 新增
                    new_record = JackpotStore(
                        gameType=row_data['gameType'],
                        period=row_data['period'],
                        drawDate=row_data['drawDate'],
                        storeName=row_data['storeName'],
                        storeAddress=row_data['storeAddress'],
                    )
                    db.add(new_record)
                    db.flush()  # 立即嘗試寫入以捕獲衝突
                    inserted += 1

            except IntegrityError:
                # Unique Key 衝突（race condition），回滾此筆後跳過
                db.rollback()
                skipped += 1
            except OperationalError as oe:
                if "database is locked" in str(oe):
                    db.rollback()
                    logger.warning("資料庫鎖定中，等待 2 秒重試...")
                    time.sleep(2)
                else:
                    raise

            # 每 100 筆 commit 一次
            if (inserted + updated + skipped) % 100 == 0 and (inserted + updated + skipped) > 0:
                db.commit()

        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Upsert 頭獎資料失敗: {e}", exc_info=True)
    finally:
        db.close()

    logger.info(f"JackpotStore Upsert 完成：新增 {inserted} 筆、更新 {updated} 筆、跳過 {skipped} 筆")

    # === 第三步：從 JackpotStore 聚合計算各經銷商的 jackpotCount ===
    _update_retailer_jackpot_counts()

    logger.info("同步台彩頭獎店家資料完成。")


def _update_retailer_jackpot_counts():
    """
    從 JackpotStore 表聚合計算頭獎次數，並更新 Retailer.jackpotCount

    比對邏輯：
    1. 精確比對：標準化店名 + 核心地址
    2. 寬鬆比對：僅核心地址
    """
    logger.info("開始從 JackpotStore 聚合計算 Retailer.jackpotCount...")

    db: Session = SessionLocal()
    try:
        # 取得所有頭獎紀錄
        all_jackpots = db.query(JackpotStore).all()

        # 統計每個 (標準化店名, 核心地址) 的頭獎次數
        jackpot_counts: dict[tuple[str, str], int] = {}
        for jp in all_jackpots:
            norm_name = normalize_string(jp.storeName)
            core_addr = extract_core_address(jp.storeAddress)
            key = (norm_name, core_addr)
            jackpot_counts[key] = jackpot_counts.get(key, 0) + 1

        logger.info(f"頭獎統計：{sum(jackpot_counts.values())} 筆紀錄，分布於 {len(jackpot_counts)} 家商店。")

        # 取得所有經銷商，建立快速查詢字典
        all_retailers = db.query(Retailer).all()
        exact_map: dict[tuple[str, str], Retailer] = {}
        addr_map: dict[str, Retailer] = {}
        for r in all_retailers:
            core_a = extract_core_address(r.address)
            exact_map[(normalize_string(r.name), core_a)] = r
            addr_map[core_a] = r

        # 比對並收集需要更新的經銷商
        updates: dict[int, int] = {}
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

        logger.info(f"成功配對 {match_count}/{len(jackpot_counts)} 家頭獎商店。")
    except Exception as e:
        logger.error(f"查詢店家資料失敗: {e}", exc_info=True)
        return
    finally:
        db.close()

    # 分批更新 Retailer.jackpotCount，避免長時間鎖定
    batch_size = 200
    update_items = list(updates.items())

    for i in range(0, len(update_items), batch_size):
        batch = update_items[i:i + batch_size]
        db = SessionLocal()
        try:
            def do_update():
                for r_id, count in batch:
                    db.query(Retailer).filter(Retailer.id == r_id).update({"jackpotCount": count})
                db.commit()

            _db_retry(do_update)
        except Exception as e:
            db.rollback()
            logger.error(f"更新 Retailer.jackpotCount 失敗 (Batch {i//batch_size}): {e}", exc_info=True)
        finally:
            db.close()

    logger.info(f"Retailer.jackpotCount 更新完成，共更新 {len(updates)} 筆。")


if __name__ == "__main__":
    # 測試腳本
    logging.basicConfig(level=logging.INFO)
    sync_jackpot_stores()
