"""
店家公開頁 API 路由
每間店（不分 PRO）都有的公開資料：頭獎紀錄、評分評論、玩家中獎回報、庫存
"""

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.cache import get_cache, set_cache
from app.model.database import Checkin, get_db
from app.model.jackpot_store import JackpotStore
from app.model.merchant_inventory import MerchantInventory
from app.model.rating import RetailerRating
from app.model.retailer import Retailer
from app.model.user import InventoryReport, User
from app.service.tier_service import is_retailer_pro

router = APIRouter(prefix="/api/stores", tags=["店家公開頁"])

CACHE_TTL = 600
WIN_REPORT_WINDOW_DAYS = 90
INVENTORY_REPORT_WINDOW_DAYS = 7
RECENT_LIMIT = 10

# 可被搜尋引擎收錄的門檻：沒內容的店不進 sitemap，避免大量薄頁
INDEXABLE_MIN_WIN_REPORTS = 3

FACILITY_FIELDS = {
    "hasAC": "冷氣", "hasToilet": "廁所", "hasSeats": "座位", "hasWifi": "Wi-Fi",
    "hasAccessibility": "無障礙空間", "hasEPay": "電子支付", "hasStrategy": "提供攻略",
    "hasNumberPick": "挑號服務", "hasScratchBoard": "專業刮板", "hasMagnifier": "放大鏡",
    "hasReadingGlasses": "老花眼鏡", "hasNewspaper": "明牌報紙", "hasSportTV": "運彩轉播",
}


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


def _rating_section(db: Session, retailer_id: int) -> dict:
    ratings = (
        db.query(RetailerRating)
        .filter(RetailerRating.retailerId == retailer_id)
        .order_by(RetailerRating.createdAt.desc())
        .all()
    )
    if not ratings:
        return {"avgRating": 0.0, "totalCount": 0, "distribution": {}, "serviceTagStats": {}, "recent": []}

    total_weight = sum(r.karmaWeight or 0 for r in ratings)
    weighted_sum = sum(r.rating * (r.karmaWeight or 0) for r in ratings)
    distribution: dict[str, int] = {}
    service_stats: dict[str, int] = {}
    for r in ratings:
        distribution[str(r.rating)] = distribution.get(str(r.rating), 0) + 1
        for tag in (r.serviceTags or "").split(","):
            tag = tag.strip()
            if tag:
                service_stats[tag] = service_stats.get(tag, 0) + 1

    recent = ratings[:RECENT_LIMIT]
    users = {
        u.id: u for u in db.query(User).filter(User.id.in_({r.userId for r in recent})).all()
    }
    # 公開頁不回傳 userId／大頭貼，只給暱稱與等級
    recent_items = []
    for r in recent:
        u = users.get(r.userId)
        recent_items.append({
            "rating": r.rating,
            "serviceTags": [t for t in (r.serviceTags or "").split(",") if t],
            "comment": r.comment or "",
            "userName": (u.customNickname or u.displayName or "匿名") if u else "匿名",
            "userLevel": u.karmaLevel if u else 1,
            "isGpsVerified": bool(r.isGpsVerified),
            "createdAt": _iso(r.createdAt),
        })

    return {
        "avgRating": round(weighted_sum / total_weight, 1) if total_weight > 0 else 0.0,
        "totalCount": len(ratings),
        "distribution": distribution,
        "serviceTagStats": service_stats,
        "recent": recent_items,
    }


def _win_report_section(db: Session, retailer_id: int) -> dict:
    cutoff = datetime.utcnow() - timedelta(days=WIN_REPORT_WINDOW_DAYS)
    base = db.query(Checkin).filter(Checkin.retailerId == retailer_id, Checkin.createdAt >= cutoff)
    count, total = (
        db.query(func.count(Checkin.id), func.coalesce(func.sum(Checkin.amount), 0))
        .filter(Checkin.retailerId == retailer_id, Checkin.createdAt >= cutoff)
        .one()
    )
    recent = base.order_by(Checkin.createdAt.desc()).limit(RECENT_LIMIT).all()
    return {
        "windowDays": WIN_REPORT_WINDOW_DAYS,
        "count": int(count or 0),
        "totalAmount": int(total or 0),
        "recent": [
            {"amount": c.amount, "gameName": c.gameName or "", "createdAt": _iso(c.createdAt)}
            for c in recent
        ],
    }


def _inventory_section(db: Session, retailer_id: int) -> dict:
    official = (
        db.query(MerchantInventory)
        .filter(MerchantInventory.retailerId == retailer_id, MerchantInventory.status != "未設定")
        .order_by(MerchantInventory.itemPrice.desc())
        .all()
    )
    cutoff = datetime.utcnow() - timedelta(days=INVENTORY_REPORT_WINDOW_DAYS)
    reports = (
        db.query(InventoryReport)
        .filter(InventoryReport.retailerId == retailer_id, InventoryReport.createdAt >= cutoff)
        .order_by(InventoryReport.createdAt.desc())
        .all()
    )
    # 依品項取信心值最高的一筆（與 /api/inventory/{id} 一致）
    community: dict[str, dict] = {}
    for r in reports:
        if r.item not in community or r.confidence > community[r.item]["confidence"]:
            community[r.item] = {
                "item": r.item, "status": r.status,
                "confidence": r.confidence, "updatedAt": _iso(r.createdAt),
            }
    return {
        "official": [
            {
                "itemName": i.itemName, "itemPrice": i.itemPrice, "status": i.effective_status,
                "scratchcardId": i.scratchcardId, "updatedAt": _iso(i.updatedAt),
            }
            for i in official
        ],
        "community": list(community.values()),
    }


@router.get("/indexable")
def list_indexable_stores(db: Session = Depends(get_db)):
    """
    可被搜尋引擎收錄的店家清單（給 build 時預先產生靜態頁與 sitemap）
    條件：有頭獎紀錄、有評分、近 90 天 ≥3 則玩家中獎回報、或有效 PRO 已認領
    """
    cached = get_cache("stores:indexable", ttl=CACHE_TTL)
    if cached is not None:
        return cached

    lastmod: dict[int, datetime | None] = {}

    def touch(retailer_id: int | None, when: datetime | None):
        if retailer_id is None:
            return
        prev = lastmod.get(retailer_id)
        if retailer_id not in lastmod or (when and (prev is None or when > prev)):
            lastmod[retailer_id] = when

    for r_id, when in (
        db.query(JackpotStore.retailerId, func.max(JackpotStore.updatedAt))
        .filter(JackpotStore.retailerId.isnot(None))
        .group_by(JackpotStore.retailerId)
        .all()
    ):
        touch(r_id, when)

    for r_id, when in (
        db.query(RetailerRating.retailerId, func.max(RetailerRating.createdAt))
        .group_by(RetailerRating.retailerId)
        .all()
    ):
        touch(r_id, when)

    cutoff = datetime.utcnow() - timedelta(days=WIN_REPORT_WINDOW_DAYS)
    for r_id, when in (
        db.query(Checkin.retailerId, func.max(Checkin.createdAt))
        .filter(Checkin.retailerId.isnot(None), Checkin.createdAt >= cutoff)
        .group_by(Checkin.retailerId)
        .having(func.count(Checkin.id) >= INDEXABLE_MIN_WIN_REPORTS)
        .all()
    ):
        touch(r_id, when)

    for r in db.query(Retailer).filter(Retailer.isClaimed == True, Retailer.merchantTier == "pro").all():  # noqa: E712
        if is_retailer_pro(r):
            touch(r.id, r.updatedAt)

    active_ids = {
        r_id for (r_id,) in db.query(Retailer.id).filter(Retailer.id.in_(lastmod.keys()), Retailer.isActive == True).all()  # noqa: E712
    } if lastmod else set()

    result = [
        {"id": r_id, "lastmod": _iso(lastmod[r_id])}
        for r_id in sorted(active_ids)
    ]
    set_cache("stores:indexable", result)
    return result


@router.get("/{retailer_id}/public")
def get_store_public(retailer_id: int, db: Session = Depends(get_db)):
    """店家公開頁資料（每間店都有，不需登入）"""
    cache_key = f"stores:public:{retailer_id}"
    cached = get_cache(cache_key, ttl=CACHE_TTL)
    if cached is not None:
        return cached

    retailer = db.query(Retailer).filter(Retailer.id == retailer_id).first()
    if not retailer:
        raise HTTPException(status_code=404, detail="店家不存在")

    jackpots = (
        db.query(JackpotStore)
        .filter(JackpotStore.retailerId == retailer_id)
        .order_by(JackpotStore.drawDate.desc(), JackpotStore.period.desc())
        .all()
    )

    result = {
        "id": retailer.id,
        "name": retailer.name,
        "address": retailer.address or "",
        "city": retailer.city or "",
        "district": retailer.district or "",
        "source": retailer.source or "",
        "lat": retailer.lat,
        "lng": retailer.lng,
        "isActive": bool(retailer.isActive),
        "isClaimed": bool(retailer.isClaimed),
        "isPro": is_retailer_pro(retailer) and bool(retailer.isClaimed),
        "facilities": [label for field, label in FACILITY_FIELDS.items() if getattr(retailer, field, False)],
        "jackpots": {
            "count": len(jackpots),
            "items": [
                {"gameType": j.gameType, "period": j.period, "drawDate": j.drawDate or ""}
                for j in jackpots
            ],
        },
        "ratings": _rating_section(db, retailer_id),
        "winReports": _win_report_section(db, retailer_id),
        "inventory": _inventory_section(db, retailer_id),
    }
    set_cache(cache_key, result)
    return result
