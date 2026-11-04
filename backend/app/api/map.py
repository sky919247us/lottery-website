"""
中獎打卡 API 路由
提供打卡紀錄查詢與新增功能
"""

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.user import add_karma
from app.model.database import Checkin, get_db
from app.model.retailer import Retailer
from app.model.user import KarmaLog, User
from app.schema.scratchcard import CheckinCreate, CheckinResponse
from app.service.auth_service import get_current_user

router = APIRouter(prefix="/api/map", tags=["中獎地圖"])

# 公開頁面只顯示最近幾天的打卡，避免老資料堆積（個人錢包 PnL 紀錄不受影響）
PUBLIC_CHECKIN_WINDOW_DAYS = 7

# 中獎打卡 Karma：每次 +5，每人每天（台灣時間）最多給分 3 次，防止刷分
CHECKIN_KARMA_POINTS = 5
CHECKIN_KARMA_DAILY_LIMIT = 3


def _taiwan_day_start_utc() -> datetime:
    """台灣時間今天 00:00 對應的 UTC naive datetime（與 createdAt 的 utcnow 一致）"""
    now_tw = datetime.utcnow() + timedelta(hours=8)
    return now_tw.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(hours=8)


@router.get("/checkins", response_model=list[CheckinResponse])
def get_checkins(db: Session = Depends(get_db)):
    """取得全台中獎打卡紀錄（公開，只回傳最近 7 天，滾動式更新）"""
    cutoff = datetime.utcnow() - timedelta(days=PUBLIC_CHECKIN_WINDOW_DAYS)
    return (
        db.query(Checkin)
        .filter(Checkin.createdAt >= cutoff)
        .order_by(Checkin.createdAt.desc())
        .limit(200)
        .all()
    )


@router.post("/checkin", response_model=CheckinResponse, status_code=201)
def create_checkin(
    data: CheckinCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """新增一筆中獎回報（需登入；可選填在哪間店買的；checkins 表不存 userId，維持匿名）"""
    if data.retailerId is not None:
        if not db.query(Retailer.id).filter(Retailer.id == data.retailerId).first():
            raise HTTPException(status_code=404, detail="店家不存在")

    checkin = Checkin(
        city=data.city,
        amount=data.amount,
        gameName=data.gameName,
        retailerId=data.retailerId,
    )
    db.add(checkin)
    db.commit()
    db.refresh(checkin)

    today_count = db.query(KarmaLog).filter(
        KarmaLog.userId == user.id,
        KarmaLog.action == "checkin",
        KarmaLog.createdAt >= _taiwan_day_start_utc(),
    ).count()
    if today_count < CHECKIN_KARMA_DAILY_LIMIT:
        add_karma(db, user.id, "checkin", CHECKIN_KARMA_POINTS, "中獎打卡", data.retailerId)

    return checkin


@router.post("/retailer/{retailer_id}/click")
def record_retailer_click(retailer_id: int, db: Session = Depends(get_db)):
    """紀錄店家在地圖上被點擊查看的次數"""
    retailer = db.query(Retailer).filter(Retailer.id == retailer_id).first()
    if not retailer:
        raise HTTPException(status_code=404, detail="店家不存在")
    
    retailer.mapClickCount = (retailer.mapClickCount or 0) + 1
    db.commit()
    return {"status": "ok", "clickCount": retailer.mapClickCount}

