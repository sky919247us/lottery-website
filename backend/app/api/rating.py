"""
店家評分 API 路由
服務品質評分 + 硬體設施群眾回報
"""

import logging
from datetime import datetime, timedelta, timezone
from math import radians, sin, cos, sqrt, atan2

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.model.database import get_db
from app.model.rating import RetailerRating
from app.model.retailer import Retailer
from app.model.user import User, get_level_info
from app.schema.rating import RatingCreate, RatingResponse, RatingSummary
from app.service.auth_service import get_current_user
from app.api.user import add_karma

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ratings", tags=["評分"])

# GPS 驗證距離門檻（公尺）
GPS_VERIFY_DISTANCE = 200

# 每小時最多評分次數
RATE_LIMIT_PER_HOUR = 5

# 硬體設施群眾回報門檻（N 人以上確認就自動標記）
FACILITY_CONSENSUS_THRESHOLD = 1

# 支援的服務品質標籤
SERVICE_TAGS = ["環境乾淨", "店員親切", "品項齊全", "攻略豐富", "交通方便", "願意再訪"]

# 硬體設施標籤 → retailers 表欄位映射
FACILITY_TAG_MAP = {
    "冷氣": "hasAC",
    "廁所": "hasToilet",
    "座位": "hasSeats",
    "Wi-Fi": "hasWifi",
    "無障礙": "hasAccessibility",
    "電子支付": "hasEPay",
    "攻略": "hasStrategy",
    "挑號": "hasNumberPick",
    "刮板": "hasScratchBoard",
    "放大鏡": "hasMagnifier",
    "老花眼鏡": "hasReadingGlasses",
    "報紙": "hasNewspaper",
    "運彩轉播": "hasSportTV",
}


def _haversine(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """計算兩點之間的距離（公尺），使用 Haversine 公式"""
    R = 6371000  # 地球半徑（公尺）
    d_lat = radians(lat2 - lat1)
    d_lng = radians(lng2 - lng1)
    a = sin(d_lat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(d_lng / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return R * c


def _rating_to_response(r: RetailerRating, db: Session) -> dict:
    """將 RetailerRating 物件轉為回應字典"""
    user = db.query(User).filter(User.id == r.userId).first()
    return {
        "id": r.id,
        "retailerId": r.retailerId,
        "userId": r.userId,
        "userName": user.customNickname or user.displayName or "匿名" if user else "匿名",
        "userLevel": user.karmaLevel if user else 1,
        "userPictureUrl": user.pictureUrl or "" if user else "",
        "rating": r.rating,
        "serviceTags": [t for t in r.serviceTags.split(",") if t] if r.serviceTags else [],
        "facilityTags": [t for t in r.facilityTags.split(",") if t] if r.facilityTags else [],
        "comment": r.comment or "",
        "isGpsVerified": r.isGpsVerified,
        "karmaWeight": r.karmaWeight,
        "createdAt": r.createdAt.isoformat(),
    }


def _update_facility_consensus(retailer_id: int, db: Session):
    """
    統計該店家的硬體設施回報，達到門檻就自動更新 retailers 表
    """
    ratings = db.query(RetailerRating).filter(
        RetailerRating.retailerId == retailer_id
    ).all()

    # 統計各設施標籤被回報的次數
    facility_counts: dict[str, int] = {}
    for r in ratings:
        if r.facilityTags:
            for tag in r.facilityTags.split(","):
                tag = tag.strip()
                if tag:
                    facility_counts[tag] = facility_counts.get(tag, 0) + 1

    # 更新 retailer 對應欄位
    retailer = db.query(Retailer).filter(Retailer.id == retailer_id).first()
    if not retailer:
        return

    for tag_name, column_name in FACILITY_TAG_MAP.items():
        if facility_counts.get(tag_name, 0) >= FACILITY_CONSENSUS_THRESHOLD:
            if hasattr(retailer, column_name):
                setattr(retailer, column_name, True)

    db.commit()


@router.post("")
async def create_rating(
    data: RatingCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    新增店家評分（需登入）
    每人每店只能評一次，每小時上限 5 次
    """
    # 1. 頻率限制：每小時上限
    one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
    recent_count = db.query(RetailerRating).filter(
        RetailerRating.userId == user.id,
        RetailerRating.createdAt >= one_hour_ago,
    ).count()
    if recent_count >= RATE_LIMIT_PER_HOUR:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"評分過於頻繁，每小時最多 {RATE_LIMIT_PER_HOUR} 次",
        )

    # 2. 檢查是否已評過
    existing = db.query(RetailerRating).filter(
        RetailerRating.userId == user.id,
        RetailerRating.retailerId == data.retailerId,
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="您已經對此店家評過分了",
        )

    # 3. 確認店家存在
    retailer = db.query(Retailer).filter(Retailer.id == data.retailerId).first()
    if not retailer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="店家不存在",
        )

    # 4. GPS 驗證
    is_gps_verified = False
    if data.lat is not None and data.lng is not None:
        if retailer.lat and retailer.lng:
            distance = _haversine(data.lat, data.lng, retailer.lat, retailer.lng)
            is_gps_verified = distance <= GPS_VERIFY_DISTANCE

    # 5. 取得 Karma 權重
    _, weight, _ = get_level_info(user.karmaLevel)

    # 6. 建立評分
    rating = RetailerRating(
        retailerId=data.retailerId,
        userId=user.id,
        rating=data.rating,
        serviceTags=",".join(data.serviceTags),
        facilityTags=",".join(data.facilityTags),
        comment=data.comment[:200] if data.comment else "",
        isGpsVerified=is_gps_verified,
        karmaWeight=float(weight),
    )
    db.add(rating)
    db.commit()
    db.refresh(rating)

    # 7. 加 Karma 積分（+20）
    add_karma(db, user.id, "rating", 20, f"評分店家 #{data.retailerId}", data.retailerId)

    # 8. 更新硬體設施群眾回報
    if data.facilityTags:
        _update_facility_consensus(data.retailerId, db)

    logger.info(f"使用者 {user.id} 評分店家 {data.retailerId}: {data.rating}星")

    return _rating_to_response(rating, db)


@router.get("/{retailer_id}")
async def get_retailer_ratings(
    retailer_id: int,
    db: Session = Depends(get_db),
):
    """取得某店家的所有評分"""
    ratings = db.query(RetailerRating).filter(
        RetailerRating.retailerId == retailer_id
    ).order_by(RetailerRating.createdAt.desc()).limit(50).all()

    return [_rating_to_response(r, db) for r in ratings]


@router.get("/{retailer_id}/summary")
async def get_rating_summary(
    retailer_id: int,
    db: Session = Depends(get_db),
):
    """取得店家評分摘要（加權平均 + 標籤統計）"""
    ratings = db.query(RetailerRating).filter(
        RetailerRating.retailerId == retailer_id
    ).all()

    if not ratings:
        return RatingSummary(retailerId=retailer_id)

    # 加權平均星等
    total_weight = sum(r.karmaWeight for r in ratings)
    weighted_sum = sum(r.rating * r.karmaWeight for r in ratings)
    avg_rating = round(weighted_sum / total_weight, 1) if total_weight > 0 else 0.0

    # 服務標籤統計
    service_stats: dict[str, int] = {}
    facility_stats: dict[str, int] = {}

    for r in ratings:
        if r.serviceTags:
            for tag in r.serviceTags.split(","):
                tag = tag.strip()
                if tag:
                    service_stats[tag] = service_stats.get(tag, 0) + 1
        if r.facilityTags:
            for tag in r.facilityTags.split(","):
                tag = tag.strip()
                if tag:
                    facility_stats[tag] = facility_stats.get(tag, 0) + 1

    return RatingSummary(
        retailerId=retailer_id,
        avgRating=avg_rating,
        totalCount=len(ratings),
        serviceTagStats=service_stats,
        facilityTagStats=facility_stats,
    )
