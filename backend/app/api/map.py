"""
中獎打卡 API 路由
提供打卡紀錄查詢與新增功能
"""

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.model.database import Checkin, get_db
from app.schema.scratchcard import CheckinCreate, CheckinResponse

router = APIRouter(prefix="/api/map", tags=["中獎地圖"])

# 公開頁面只顯示最近幾天的打卡，避免老資料堆積（個人錢包 PnL 紀錄不受影響）
PUBLIC_CHECKIN_WINDOW_DAYS = 7


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
    db: Session = Depends(get_db),
):
    """新增一筆中獎回報"""
    checkin = Checkin(
        city=data.city,
        amount=data.amount,
        gameName=data.gameName,
    )
    db.add(checkin)
    db.commit()
    db.refresh(checkin)
    return checkin


from app.model.retailer import Retailer
from fastapi import HTTPException

@router.post("/retailer/{retailer_id}/click")
def record_retailer_click(retailer_id: int, db: Session = Depends(get_db)):
    """紀錄店家在地圖上被點擊查看的次數"""
    retailer = db.query(Retailer).filter(Retailer.id == retailer_id).first()
    if not retailer:
        raise HTTPException(status_code=404, detail="店家不存在")
    
    retailer.mapClickCount = (retailer.mapClickCount or 0) + 1
    db.commit()
    return {"status": "ok", "clickCount": retailer.mapClickCount}

