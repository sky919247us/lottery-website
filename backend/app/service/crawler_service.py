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

            # 定位起點（ID 錨點 或 h1 標題）
            anchor = soup.find("a", attrs={"id": target_game_id}) or soup.find(
                "a", attrs={"name": target_game_id}
            )

            # 若無錨點，嘗試用 h1 標題定位（如「遊戲期數：5140」）
            if not anchor:
                for h_tag in soup.find_all(re.compile(r"^h[1-3]$")):
                    h_text = h_tag.get_text(strip=True)
                    if str(target_game_id) in h_text and "遊戲" in h_text:
                        anchor = h_tag
                        break

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
                    # 遇到下一個遊戲期數標題就停止
                    if curr.name in ("h1", "h2", "h3"):
                        h_text = curr.get_text(strip=True)
                        if "遊戲" in h_text and str(target_game_id) not in h_text and re.search(r"\d{4}", h_text):
                            break
            else:
                target_tables = soup.find_all("table")

            if not target_tables:
                return []

            # 解析所有表格
            # 支援兩種 HTML 結構：
            # 1. <li> 列表：每個 <li> 對應一個獎項/數量
            # 2. <br> 分隔：用換行逐行配對
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
                        # 優先用 <li> 結構配對（更精確）
                        prize_lis = col_prize.find_all("li")
                        count_lis = col_count.find_all("li")

                        if prize_lis and count_lis:
                            prize_lines = [li.get_text(strip=True) for li in prize_lis if li.get_text(strip=True)]
                            count_lines = [li.get_text(strip=True) for li in count_lis if li.get_text(strip=True)]
                        else:
                            # fallback: 用換行分隔（對應 <br> 標籤）
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
                            "isPreview": False,
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


def _enrich_prize(prize: dict, total_issued: int, max_prize_amount: int) -> dict:
    """補充 oddsDenominator / isJackpot / prizeLevel 三個分析用欄位。"""
    name = prize.get("prizeName", "") or ""
    amount = prize.get("prizeAmount", 0) or 0
    count = prize.get("totalCount", 0) or 0

    # 中獎機率分母（幾張中一張）
    odds = 0
    if count > 0 and total_issued > 0:
        odds = int(total_issued / count)
    prize["oddsDenominator"] = odds

    # 頭獎/特獎判定：名稱含關鍵字 或 金額等於最高獎金
    is_jackpot = bool(re.search(r"頭獎|特獎", name)) or (
        max_prize_amount > 0 and amount == max_prize_amount
    )
    prize["isJackpot"] = is_jackpot

    # 獎項等級：從名稱抽取「頭獎/貳獎/...」字樣
    level = ""
    m = re.search(r"(頭獎|特獎|[壹貳參肆伍陸柒捌玖拾]+獎|\d+獎)", name)
    if m:
        level = m.group(1)
    prize["prizeLevel"] = level
    return prize


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
            total_issued = data.get("totalIssued", 0) or 0
            max_prize_amount = data.get("maxPrizeAmount", 0) or 0
            for prize in data.get("prizes", []):
                _enrich_prize(prize, total_issued, max_prize_amount)

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
    """完整爬蟲流程：爬取 + 存入 DB + 寫入每日快照"""
    data = await scrape_all_scratchcards()
    if data:
        save_to_database(data)
        # 爬蟲成功後寫入今日快照（時間序列分析基礎）
        try:
            from app.service.snapshot_service import write_daily_snapshots
            write_daily_snapshots()
        except Exception as e:
            logger.warning(f"⚠️ 每日快照寫入失敗（不影響爬蟲結果）: {e}")
    return len(data)


# === 預告刮刮樂爬蟲 ===

INSTANT_HOME_API = "https://api.taiwanlottery.com/TLCAPIWeB/Home/Instant"
INSTANT_DETAIL_API = "https://api.taiwanlottery.com/TLCAPIWeB/Instant/Detail"


async def fetch_preview_scratchcards() -> list[dict[str, Any]]:
    """
    透過台灣彩券公開 API 取得預告（即將發售）刮刮樂資料
    不需要 Playwright，直接呼叫 REST API
    """
    logger.info("🔍 開始抓取預告刮刮樂...")
    results = []

    headers = {
        "User-Agent": "Mozilla/5.0",
        "Referer": "https://www.taiwanlottery.com/",
    }

    async with aiohttp.ClientSession() as session:
        # Step 1: 從首頁 API 取得預告列表
        try:
            async with session.get(
                INSTANT_HOME_API, headers=headers,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                if resp.status != 200:
                    logger.warning(f"⚠️ Home/Instant API 回應 {resp.status}")
                    return []
                data = await resp.json()
        except Exception as e:
            logger.error(f"❌ 取得預告列表失敗: {e}")
            return []

        content = data.get("content", {})
        forecast_list = content.get("forecastInstantList", [])

        if not forecast_list:
            logger.info("ℹ️ 目前沒有預告刮刮樂")
            return []

        logger.info(f"📋 發現 {len(forecast_list)} 款預告刮刮樂")

        # Step 2: 逐一取得每款預告的詳細資料
        for item in forecast_list:
            scratch_id = item.get("scratchId", "")
            if not scratch_id:
                continue

            try:
                async with session.get(
                    INSTANT_DETAIL_API,
                    params={"ScratchId": scratch_id},
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    if resp.status != 200:
                        logger.warning(f"⚠️ 取得預告詳情失敗 ({scratch_id}): HTTP {resp.status}")
                        continue
                    detail_data = await resp.json()
            except Exception as e:
                logger.warning(f"⚠️ 取得預告詳情失敗 ({scratch_id}): {e}")
                continue

            detail = detail_data.get("content", {})
            if not detail:
                continue

            # 解析圖片 URL（取第一張，listPic 可能是 list 或逗號分隔字串）
            image_url = ""
            list_pic = detail.get("listPic", "")
            if isinstance(list_pic, list):
                image_url = list_pic[0].strip() if list_pic else ""
            elif isinstance(list_pic, str) and list_pic:
                image_url = list_pic.split(",")[0].strip()
            if not image_url:
                image_url = detail.get("detailPicPath", "") or ""

            # 解析發行日（API 回傳西元格式，轉為民國年）
            listing_date = detail.get("listingDate", "")
            issue_date_roc = ""
            if listing_date:
                try:
                    # 格式可能是 "2026/04/15" 或 "2026-04-15"
                    clean_date = listing_date.replace("-", "/").split("T")[0]
                    parts = clean_date.split("/")
                    if len(parts) == 3:
                        roc_year = int(parts[0]) - 1911
                        issue_date_roc = f"{roc_year}/{parts[1]}/{parts[2]}"
                except (ValueError, IndexError):
                    issue_date_roc = listing_date

            # 解析最高獎金與描述（從 moreDesc 文字中擷取）
            # 預告款的 moreDesc 不含獎金結構表格，只有文字描述如 "頭獎200萬元"
            max_prize_amount = 0
            max_prize_text = ""
            more_desc = detail.get("moreDesc", "")
            web_memo = item.get("webMemo", "")
            desc_text = ""

            if more_desc:
                try:
                    soup = BeautifulSoup(more_desc, "html.parser")
                    desc_text = soup.get_text()
                except Exception:
                    desc_text = more_desc

            # 嘗試從 moreDesc 或 webMemo 解析頭獎金額
            for text_source in [desc_text, web_memo]:
                if max_prize_amount > 0:
                    break
                if not text_source:
                    continue
                # 匹配 "頭獎200萬元" 或 "頭獎2,000,000元" 等格式
                m = re.search(r'頭獎\s*([\d,]+)\s*萬\s*元', text_source)
                if m:
                    try:
                        max_prize_amount = int(m.group(1).replace(",", "")) * 10000
                        max_prize_text = f"NT${max_prize_amount:,}"
                        logger.info(f"    💰 解析到頭獎: {max_prize_amount:,} 元")
                    except ValueError:
                        pass
                if max_prize_amount == 0:
                    # 匹配 "頭獎2,000,000元" 格式
                    m2 = re.search(r'頭獎\s*([\d,]+)\s*元', text_source)
                    if m2:
                        try:
                            max_prize_amount = int(m2.group(1).replace(",", ""))
                            max_prize_text = f"NT${max_prize_amount:,}"
                        except ValueError:
                            pass

            # 預告款通常沒有完整獎金結構表格，僅記錄頭獎
            prize_list = []
            if max_prize_amount > 0:
                prize_list.append({
                    "prizeName": "頭獎",
                    "prizeAmount": min(max_prize_amount, MAX_SAFE_INT),
                    "totalCount": 0,
                })

            # 解析下市日與兌獎截止日
            def _to_roc(date_str: str) -> str:
                if not date_str:
                    return ""
                try:
                    clean = date_str.replace("-", "/").split("T")[0]
                    parts = clean.split("/")
                    if len(parts) == 3:
                        return f"{int(parts[0]) - 1911}/{parts[1]}/{parts[2]}"
                except (ValueError, IndexError):
                    pass
                return ""

            end_date_roc = _to_roc(detail.get("downDate", ""))
            redeem_deadline_roc = _to_roc(detail.get("exchangeLastDate", ""))

            row = {
                "gameId": scratch_id,
                "name": detail.get("scratchName", item.get("scratchName", "未命名")),
                "price": detail.get("money", 0),
                "maxPrize": max_prize_text,
                "maxPrizeAmount": max_prize_amount,
                "issueDate": issue_date_roc,
                "endDate": end_date_roc,
                "redeemDeadline": redeem_deadline_roc,
                "totalIssued": detail.get("issuedCount", 0),
                "salesRate": "",
                "salesRateValue": 0.0,
                "grandPrizeCount": 0,
                "grandPrizeUnclaimed": 0,
                "overallWinRate": f"{detail.get('oddsOfWinning', '')}%" if detail.get("oddsOfWinning") else "",
                "isHighWinRate": False,
                "isPreview": True,
                "prizeInfoUrl": "",
                "imageUrl": image_url,
                "prizes": prize_list,
            }
            results.append(row)
            logger.info(f"    ✅ 預告: {row['name']} (${row['price']}) - 預計 {issue_date_roc}")

    logger.info(f"🎉 預告爬蟲完成，共取得 {len(results)} 款")
    return results


async def run_preview_crawler() -> int:
    """
    預告爬蟲流程：抓取 + 存入 DB
    同時清理已正式上架的舊預告記錄（名稱相同且已有正式版本的預告款）
    """
    data = await fetch_preview_scratchcards()
    if data:
        save_to_database(data)

    # 清理：只刪除已不在台彩預告列表中的舊預告款
    # 注意：不用名稱比對，因為台彩會重複使用相同名稱（不同系列）
    db: Session = SessionLocal()
    try:
        preview_cards = db.query(Scratchcard).filter(Scratchcard.isPreview == True).all()
        current_preview_ids = {d["gameId"] for d in data}

        removed = 0
        for card in preview_cards:
            if card.gameId not in current_preview_ids:
                db.query(PrizeStructure).filter(PrizeStructure.scratchcardId == card.id).delete()
                db.delete(card)
                removed += 1
                logger.info(f"🗑️ 清除舊預告款: {card.name} (gameId={card.gameId})")

        if removed:
            db.commit()
            logger.info(f"🧹 共清除 {removed} 筆過時的預告記錄")
    except Exception as e:
        db.rollback()
        logger.error(f"❌ 清理預告記錄失敗: {e}")
    finally:
        db.close()

    return len(data)
