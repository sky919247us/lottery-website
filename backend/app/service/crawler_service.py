"""
刮刮樂爬蟲服務
參考 https://github.com/101angus/lottery-scraper/
使用 Playwright 爬取台灣彩券官網 + API 取得獎金結構
"""

import asyncio
import logging
import re
from typing import Any

import aiohttp
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
from sqlalchemy.orm import Session

from app.model.database import PrizeStructure, Scratchcard, SessionLocal

logger = logging.getLogger(__name__)

# 台灣彩券相關 URL
TAIWAN_LOTTERY_URL = "https://www.taiwanlottery.com/instant/sale/"
API_BASE_URL = "https://api.taiwanlottery.com/TLCAPIWeB/News/Detail/"

# 需要從卡片文字中解析的欄位
DETAIL_KEYS = [
    "售價", "發行日", "下市日", "兌獎截止日", "發行張數",
    "銷售率", "頭獎張數", "最高獎金張數", "頭獎未兌領張數",
    "最高獎金未兌領張數", "最高獎金",
]

# NOTE: SQLite INTEGER 上限 2^63-1，超過此值會 OverflowError
MAX_SAFE_INT = 2**63 - 1


async def fetch_prize_via_api(
    session: aiohttp.ClientSession,
    news_url: str,
    target_game_id: str,
) -> list[dict[str, Any]]:
    """
    透過 API 取得新聞內容，解析該刮刮樂的所有獎金結構。
    回傳格式：[{"prizeName": "...", "prizeAmount": 0, "totalCount": 0}, ...]
    """
    if not news_url:
        return []

    try:
        # 從 URL 解析新聞 ID
        clean_url = news_url.split("#")[0]
        news_id = clean_url.rstrip("/").split("/")[-1]
        api_url = f"{API_BASE_URL}{news_id}"

        headers = {
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://www.taiwanlottery.com/",
        }

        async with session.get(api_url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
            if resp.status != 200:
                return []
            data = await resp.json()

            # 解析 HTML 內容
            raw_html = ""
            if isinstance(data, dict) and "content" in data:
                if isinstance(data["content"], str):
                    raw_html = data["content"]
                elif isinstance(data["content"], dict):
                    raw_html = data["content"].get("content", "")

            if not raw_html:
                return []

            soup = BeautifulSoup(raw_html, "html.parser")

            # 定位起點（ID 錨點）
            anchor = soup.find("a", attrs={"id": target_game_id}) or soup.find(
                "a", attrs={"name": target_game_id}
            )
            target_tables = []

            if anchor:
                curr = anchor
                while True:
                    curr = curr.find_next()
                    if not curr:
                        break
                    if curr.name == "table":
                        target_tables.append(curr)
                    # 遇到下一個 ID 錨點就停止
                    if curr.name == "a" and (curr.get("id") or curr.get("name")):
                        aid = curr.get("id") or curr.get("name")
                        if str(aid) != str(target_game_id) and re.match(r"^\d+$", str(aid)):
                            break
            else:
                target_tables = soup.find_all("table")

            if not target_tables:
                return []

            # 解析所有表格
            # NOTE: 每個 <td> 可能包含多個獎項，以 <br> 分隔
            # 使用 get_text(separator="\n") 將 <br> 轉為換行再逐行配對
            prizes = []
            for table in target_tables:
                # 跳過統計表（class 含 summy）
                if "summy" in str(table.get("class", [])):
                    continue

                rows = table.find_all("tr")
                for row in rows:
                    cols = row.find_all(["td", "th"])
                    if len(cols) < 2:
                        continue

                    # 準備配對組（支援 4 欄位）
                    pairs = []
                    if len(cols) >= 4:
                        pairs.append((cols[0], cols[1]))
                        pairs.append((cols[2], cols[3]))
                    else:
                        pairs.append((cols[0], cols[1]))

                    for col_prize, col_count in pairs:
                        # 用換行分隔取得每一行（對應 <br> 標籤）
                        prize_lines = [
                            line.strip() for line in col_prize.get_text(separator="\n").split("\n")
                            if line.strip()
                        ]
                        count_lines = [
                            line.strip() for line in col_count.get_text(separator="\n").split("\n")
                            if line.strip()
                        ]

                        if not prize_lines or not count_lines:
                            continue

                        # 跳過表頭
                        first_p = prize_lines[0]
                        first_c = count_lines[0]
                        if "獎項" in first_p or "金額" in first_p or "張數" in first_c:
                            continue

                        # 逐行配對：獎項名稱 ↔ 張數
                        for idx, p_text in enumerate(prize_lines):
                            if not p_text:
                                continue

                            # 驗證獎項格式
                            is_valid = (
                                "NT" in p_text or "$" in p_text or "元" in p_text
                            ) or re.search(r"[頭壹貳參肆伍陸柒捌玖\d]+獎", p_text)

                            if not is_valid:
                                continue

                            # 解析獎金金額
                            amount = 0
                            amount_match = re.search(r"[\d][\d,]*", p_text)
                            if amount_match:
                                try:
                                    amount = int(amount_match.group().replace(",", ""))
                                except ValueError:
                                    pass

                            # 取得對應張數（若張數行數不足則用 0）
                            count = 0
                            if idx < len(count_lines):
                                c_text = count_lines[idx].replace(",", "")
                                count_match = re.search(r"\d+", c_text)
                                if count_match:
                                    try:
                                        count = int(count_match.group())
                                    except ValueError:
                                        pass

                            prizes.append({
                                "prizeName": p_text,
                                "prizeAmount": min(amount, MAX_SAFE_INT),
                                "totalCount": min(count, MAX_SAFE_INT),
                            })

            return prizes

    except Exception as e:
        logger.warning(f"解析獎金結構失敗: {e}")
        return []



def parse_money(money_str: str) -> int:
    """解析金額字串為整數，並限制不超過 SQLite INTEGER 上限"""
    try:
        clean = re.sub(r"[^\d]", "", str(money_str))
        value = int(clean) if clean else 0
        return min(value, MAX_SAFE_INT)
    except (ValueError, TypeError):
        return 0


def calculate_high_win_rate(details: dict, sales_rate_value: float) -> bool:
    """
    計算「紅色警戒」高勝率預警
    條件：銷售率 >= 80% 且頭獎未兌領 >= 1
    """
    unclaimed = details.get("頭獎未兌領張數", details.get("最高獎金未兌領張數", "0"))
    unclaimed_count = parse_money(str(unclaimed))
    return sales_rate_value >= 80.0 and unclaimed_count >= 1


async def scrape_all_scratchcards() -> list[dict[str, Any]]:
    """
    主爬蟲函式：使用 Playwright 爬取所有在售刮刮樂資料
    回傳解析後的列表
    """
    logger.info("🚀 啟動爬蟲程式...")
    results = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        logger.info("🌐 連線至台灣彩券官網...")
        try:
            await page.goto(TAIWAN_LOTTERY_URL, timeout=60000)
            await page.wait_for_selector(".list .card", timeout=30000)
        except Exception as e:
            logger.error(f"⚠️ 網站載入失敗: {e}")
            await browser.close()
            return []

        seen_ids: set[str] = set()

        async with aiohttp.ClientSession() as http_session:
            page_num = 1
            while True:
                logger.info(f"📄 正在處理第 {page_num} 頁...")
                cards = await page.locator(".list .card").all()
                logger.info(f"    - 發現 {len(cards)} 款刮刮樂")

                new_data_on_page = False

                for card in cards:
                    try:
                        # 取得 ID
                        lottery_id = ""
                        spans = await card.locator("span").all()
                        for s in spans:
                            txt = await s.text_content()
                            if txt and txt.strip().isdigit() and len(txt.strip()) >= 3:
                                lottery_id = txt.strip()
                                break

                        if not lottery_id or lottery_id in seen_ids:
                            continue
                        seen_ids.add(lottery_id)
                        new_data_on_page = True

                        # 取得名稱
                        game_name = "未命名"
                        if await card.locator("h2").count() > 0:
                            game_name = (await card.locator("h2").first.text_content()) or "未命名"

                        # 取得詳細資訊
                        details: dict[str, str] = {}
                        full_text = await card.inner_text()
                        text_lines = full_text.split("\n")

                        for line in text_lines:
                            line = line.strip()
                            for key in DETAIL_KEYS:
                                if key in line:
                                    val = line.replace(key, "").strip()
                                    if not val:
                                        idx = text_lines.index(line)
                                        if idx + 1 < len(text_lines):
                                            val = text_lines[idx + 1].strip()
                                    if key not in details or len(val) > len(details.get(key, "")):
                                        details[key] = val

                        # 取得獎金結構連結
                        link = ""
                        links = await card.locator("a").all()
                        for a in links:
                            href = await a.get_attribute("href")
                            if href and ("news" in href or "prize" in href):
                                link = href
                                break

                        # 透過 API 取得獎金結構
                        prize_list = []
                        if link:
                            prize_list = await fetch_prize_via_api(http_session, link, lottery_id)

                        # 解析欄位
                        sales_rate_str = details.get("銷售率", "0%")
                        sales_rate_value = 0.0
                        rate_match = re.search(r"[\d.]+", sales_rate_str)
                        if rate_match:
                            try:
                                sales_rate_value = float(rate_match.group())
                            except ValueError:
                                pass

                        # 取得圖片 URL
                        image_url = ""
                        img = await card.locator("img").first.get_attribute("src")
                        if img:
                            if img.startswith("/"):
                                image_url = f"https://www.taiwanlottery.com{img}"
                            else:
                                image_url = img

                        row = {
                            "gameId": lottery_id,
                            "name": game_name.strip(),
                            "price": parse_money(details.get("售價", "0")),
                            "maxPrize": details.get("最高獎金", ""),
                            "maxPrizeAmount": parse_money(details.get("最高獎金", "0")),
                            "issueDate": details.get("發行日", ""),
                            "endDate": details.get("下市日", ""),
                            "redeemDeadline": details.get("兌獎截止日", ""),
                            "totalIssued": parse_money(details.get("發行張數", "0")),
                            "salesRate": sales_rate_str,
                            "salesRateValue": sales_rate_value,
                            "grandPrizeCount": parse_money(
                                details.get("頭獎張數", details.get("最高獎金張數", "0"))
                            ),
                            "grandPrizeUnclaimed": parse_money(
                                details.get("頭獎未兌領張數", details.get("最高獎金未兌領張數", "0"))
                            ),
                            "overallWinRate": "",
                            "isHighWinRate": calculate_high_win_rate(details, sales_rate_value),
                            "prizeInfoUrl": link,
                            "imageUrl": image_url,
                            "prizes": prize_list,
                        }
                        results.append(row)
                        logger.info(f"    ✅ {lottery_id} - {game_name.strip()}")

                    except Exception as e:
                        logger.warning(f"    ⚠️ 解析卡片失敗: {e}")
                        continue

                # 翻頁判斷
                if not new_data_on_page and page_num > 1:
                    logger.info("🔚 已無新資料，停止翻頁")
                    break

                next_btn = page.locator("button.btn-next")
                if await next_btn.count() > 0 and not await next_btn.is_disabled():
                    await next_btn.click()
                    await page.wait_for_load_state("networkidle")
                    await asyncio.sleep(2)
                    page_num += 1
                else:
                    logger.info("🔚 已達最後一頁")
                    break

        await browser.close()

    logger.info(f"🎉 爬蟲完成，共取得 {len(results)} 款刮刮樂")
    return results


def save_to_database(data_list: list[dict[str, Any]]) -> int:
    """
    將爬蟲結果存入 SQLite 資料庫
    使用 upsert 邏輯（依 gameId 更新或新增）
    回傳寫入筆數
    """
    db: Session = SessionLocal()
    count = 0

    try:
        for data in data_list:
            # 查詢是否已存在
            existing = db.query(Scratchcard).filter(Scratchcard.gameId == data["gameId"]).first()

            if existing:
                # 更新既有資料
                for key, value in data.items():
                    if key != "prizes" and hasattr(existing, key):
                        setattr(existing, key, value)

                # 刪除舊獎金結構，重新寫入
                db.query(PrizeStructure).filter(PrizeStructure.scratchcardId == existing.id).delete()
                for prize in data.get("prizes", []):
                    db.add(PrizeStructure(scratchcardId=existing.id, **prize))
            else:
                # 新增
                prizes_data = data.pop("prizes", [])
                scratchcard = Scratchcard(**data)
                db.add(scratchcard)
                db.flush()  # 取得 auto-generated ID

                for prize in prizes_data:
                    db.add(PrizeStructure(scratchcardId=scratchcard.id, **prize))

            count += 1

        db.commit()
        logger.info(f"💾 成功寫入 {count} 筆資料至資料庫")

    except Exception as e:
        db.rollback()
        logger.error(f"❌ 資料庫寫入失敗: {e}")
        raise
    finally:
        db.close()

    return count


async def run_crawler():
    """完整爬蟲流程：爬取 + 存入 DB"""
    data = await scrape_all_scratchcards()
    if data:
        save_to_database(data)
    return len(data)
