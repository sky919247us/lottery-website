"""
FastAPI 應用程式進入點
註冊路由、CORS、資料庫初始化、APScheduler 每日爬蟲排程
"""

import asyncio
import logging

import os
import sentry_sdk
from datetime import datetime
from sentry_sdk.integrations.fastapi import FastApiIntegration
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api import map, retailer, scratchcard, videos, user, inventory, merchant, festival, auth, rating, admin, upload, payment, store_page, webhooks
from app.middleware.rate_limit import RateLimitMiddleware
from app.model.database import init_db
from app.service.crawler_service import run_crawler, run_preview_crawler
from app.service.scraper_service import sync_jackpot_stores
from app.service.admin_auth_service import init_super_admin
from app.model.database import SessionLocal

import subprocess


# 日誌與監控設定
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# 初始化 Sentry (若環境變數存在)
SENTRY_DSN = os.getenv("SENTRY_DSN_BACKEND")
if SENTRY_DSN:
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[FastApiIntegration()],
        traces_sample_rate=0.2,
        profiles_sample_rate=0.2,
    )
    logger.info("✅ Sentry backend SDK initialized.")

app = FastAPI(
    title="刮刮樂資訊與分析 API",
    description="提供台灣彩券刮刮樂即時資料、獎金結構、中獎打卡等功能",
    version="1.0.0",
)

# CORS 設定
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "https://lottery-website-3lu.pages.dev",
        "https://i168.win",
        "https://www.i168.win",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rate Limiting
app.add_middleware(RateLimitMiddleware)

# 註冊路由
app.include_router(scratchcard.router)
app.include_router(videos.router)
app.include_router(map.router)
app.include_router(retailer.router)
app.include_router(user.router)
app.include_router(inventory.router)
app.include_router(merchant.router)
app.include_router(festival.router)
app.include_router(auth.router)
app.include_router(rating.router)
app.include_router(admin.router)
app.include_router(upload.router)
app.include_router(payment.router)
app.include_router(store_page.router)
app.include_router(webhooks.router)

# 掛載靜態檔案目錄供讀取圖片
import os
if not os.path.exists("uploads"):
    os.makedirs("uploads")
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")



# APScheduler 排程器（背景執行緒）
scheduler = BackgroundScheduler()


def _run_crawler_job():
    """爬蟲排程任務：在背景執行緒中起動 asyncio 事件迴圈執行爬蟲"""
    logger.info("⏰ 排程觸發：開始執行每日爬蟲...")
    try:
        result = asyncio.run(run_crawler())
        logger.info(f"✅ 每日爬蟲完成，共寫入 {result} 筆資料")
    except Exception as e:
        logger.error(f"❌ 每日爬蟲失敗: {e}")

def _run_pro_expiry_reminder():
    """每日掃描 PRO 即將到期的商家，在 7 天前與 1 天前發送 LINE 提醒"""
    from app.model.merchant import MerchantClaim
    from app.model.retailer import Retailer
    from app.model.user import User
    from app.service.line_notify import notify_pro_expiring
    from datetime import datetime, timedelta

    db = SessionLocal()
    try:
        now = datetime.utcnow()
        for days_left in [7, 1]:
            target_date = now + timedelta(days=days_left)
            claims = db.query(MerchantClaim).filter(
                MerchantClaim.tier == "pro",
                MerchantClaim.proExpiresAt >= target_date.replace(hour=0, minute=0, second=0),
                MerchantClaim.proExpiresAt < target_date.replace(hour=23, minute=59, second=59),
            ).all()

            for claim in claims:
                user = db.query(User).filter(User.id == claim.userId).first()
                retailer = db.query(Retailer).filter(Retailer.id == claim.retailerId).first()
                if user and user.lineUserId and retailer:
                    expires_str = claim.proExpiresAt.strftime("%Y/%m/%d")
                    notify_pro_expiring(user.lineUserId, retailer.name, days_left, expires_str)
                    logger.info(f"[LINE] PRO 到期提醒已發送: {retailer.name}，剩 {days_left} 天")
    except Exception as e:
        logger.error(f"❌ PRO 到期提醒失敗: {e}")
    finally:
        db.close()


def _run_preview_crawler_job():
    """預告刮刮樂爬蟲排程任務"""
    logger.info("⏰ 排程觸發：開始執行預告刮刮樂爬蟲...")
    try:
        result = asyncio.run(run_preview_crawler())
        logger.info(f"✅ 預告爬蟲完成，共寫入 {result} 筆資料")
    except Exception as e:
        logger.error(f"❌ 預告爬蟲失敗: {e}")


def _run_backup_job():
    """資料庫備份排程任務"""
    logger.info("⏰ 排程觸發：開始執行資料庫備份...")
    try:
        # 呼叫獨立的指令碼
        script_path = os.path.join(os.path.dirname(__file__), "..", "scripts", "backup_db.py")
        subprocess.run(["uv", "run", "python", script_path], check=True)
    except Exception as e:
        logger.error(f"❌ 資料庫備份失敗: {e}")



@app.on_event("startup")
def on_startup():
    """應用程式啟動時初始化資料庫並啟動排程器"""
    logger.info("🚀 初始化資料庫...")
    init_db()
    logger.info("✅ 資料庫就緒")

    # 初始化超級管理員帳號（首次啟動時自動建立）
    db = SessionLocal()
    try:
        init_super_admin(db)
    finally:
        db.close()

    # 每日台灣早上 9:00 (UTC 1:00) 自動執行爬蟲
    scheduler.add_job(
        _run_crawler_job,
        trigger=CronTrigger(hour=1, minute=0),
        id="daily_crawler",
        replace_existing=True,
    )
    # 每天台灣凌晨 3:00 (UTC 19:00) 自動執行頭獎店家同步
    scheduler.add_job(
        sync_jackpot_stores,
        trigger=CronTrigger(hour=19, minute=0),
        id="daily_jackpot_sync",
        replace_existing=True,
    )
    # 每天台灣早上 10:00 (UTC 2:00) 掃描 PRO 到期提醒
    scheduler.add_job(
        _run_pro_expiry_reminder,
        trigger=CronTrigger(hour=2, minute=0),
        id="daily_pro_expiry_reminder",
        replace_existing=True,
    )
    # 每日台灣早上 10:05 (UTC 2:05) 自動執行預告刮刮樂爬蟲
    scheduler.add_job(
        _run_preview_crawler_job,
        trigger=CronTrigger(hour=2, minute=5),
        id="daily_preview_crawler",
        replace_existing=True,
    )
    # 每天台灣凌晨 4:00 (UTC 20:00) 自動執行資料庫備份
    scheduler.add_job(
        _run_backup_job,
        trigger=CronTrigger(hour=20, minute=0),
        id="daily_db_backup",
        replace_existing=True,
    )

    scheduler.start()
    logger.info("⏰ APScheduler 已啟動，每日 09:00 (台灣時間) 自動爬取")


@app.on_event("shutdown")
def on_shutdown():
    """應用程式關閉時停止排程器"""
    scheduler.shutdown(wait=False)
    logger.info("⏰ APScheduler 已停止")


@app.get("/api/health", tags=["系統"])
def health_check():
    """健康檢查端點"""
    return {"status": "ok", "service": "scratchcard-api"}


@app.get("/api/stats/public", tags=["系統"])
def public_stats():
    """公開的資料統計端點 (用於驗證同步結果)"""
    from app.model.database import Scratchcard, Retailer
    db = SessionLocal()
    try:
        scratchcard_count = db.query(Scratchcard).count()
        retailer_count = db.query(Retailer).count()
        return {
            "scratchcards": scratchcard_count,
            "retailers": retailer_count,
            "timestamp": datetime.now().isoformat()
        }
    finally:
        db.close()


def _require_super_admin():
    from app.model.admin import ROLE_SUPER_ADMIN
    from app.service.admin_auth_service import require_role
    return require_role(ROLE_SUPER_ADMIN)


@app.post("/api/admin/crawl", tags=["管理"])
async def trigger_crawl(admin=Depends(_require_super_admin())):
    """手動觸發爬蟲（僅超級管理員）"""
    logger.info("🔧 手動觸發爬蟲...")
    try:
        result = await run_crawler()
        return {"status": "ok", "count": result}
    except Exception as e:
        logger.error(f"❌ 爬蟲失敗: {e}")
        return {"status": "error", "message": str(e)}


@app.post("/api/admin/crawl-preview", tags=["管理"])
async def trigger_preview_crawl():
    """手動觸發預告刮刮樂爬蟲"""
    logger.info("🔧 手動觸發預告爬蟲...")
    try:
        result = await run_preview_crawler()
        return {"status": "ok", "count": result}
    except Exception as e:
        logger.error(f"❌ 預告爬蟲失敗: {e}")
        return {"status": "error", "message": str(e)}


@app.get("/sitemap.xml", tags=["SEO"])
def sitemap_xml():
    """
    動態生成 sitemap.xml
    列出所有靜態頁面 + 每個刮刮樂詳情頁
    """
    from fastapi.responses import Response
    from app.model.database import Scratchcard

    BASE_URL = os.getenv("SITE_URL", "https://scratchcard.tw")
    db = SessionLocal()
    try:
        cards = db.query(Scratchcard.id, Scratchcard.gameId).all()
    finally:
        db.close()

    # 靜態頁面
    static_pages = [
        {"loc": "/", "priority": "1.0", "changefreq": "daily"},
        {"loc": "/map", "priority": "0.9", "changefreq": "daily"},
        {"loc": "/videos", "priority": "0.7", "changefreq": "weekly"},
        {"loc": "/calculator", "priority": "0.7", "changefreq": "monthly"},
        {"loc": "/wallet", "priority": "0.6", "changefreq": "monthly"},
    ]

    urls = ""
    for page in static_pages:
        urls += f"""  <url>
    <loc>{BASE_URL}{page['loc']}</loc>
    <changefreq>{page['changefreq']}</changefreq>
    <priority>{page['priority']}</priority>
  </url>\n"""

    # 刮刮樂詳情頁
    for card_id, _ in cards:
        urls += f"""  <url>
    <loc>{BASE_URL}/detail/{card_id}</loc>
    <changefreq>weekly</changefreq>
    <priority>0.8</priority>
  </url>\n"""

    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
{urls}</urlset>"""

    return Response(content=xml, media_type="application/xml")
