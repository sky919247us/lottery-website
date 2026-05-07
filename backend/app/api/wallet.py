"""
我的錢包 API — LINE 用戶個人盈虧紀錄 + opt-in 同步全台熱區
"""

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.model.database import get_db, Checkin
from app.model.pnl_record import PnLRecord
from app.model.user import User
from app.service.auth_service import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/wallet", tags=["我的錢包"])


# ============== Schema ==============

class PnLRecordOut(BaseModel):
    id: int
    gameName: str
    scratchcardId: Optional[int]
    retailerId: Optional[int]
    spent: int
    won: int
    city: Optional[str]
    sharedToPublic: bool
    createdAt: str

    model_config = {"from_attributes": True}


class PnLRecordCreate(BaseModel):
    gameName: str = ""
    scratchcardId: Optional[int] = None
    retailerId: Optional[int] = None
    spent: int = 0
    won: int = 0
    city: Optional[str] = None
    sharedToPublic: bool = False


class UserPreferences(BaseModel):
    lastCheckinCity: Optional[str] = None


# ============== Endpoints ==============

@router.get("/records")
def list_records(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """取得個人錢包紀錄 (依時間倒序)"""
    rows = (
        db.query(PnLRecord)
        .filter(PnLRecord.userId == user.id)
        .order_by(PnLRecord.createdAt.desc())
        .all()
    )
    return [
        {
            "id": r.id,
            "gameName": r.gameName or "",
            "scratchcardId": r.scratchcardId,
            "retailerId": r.retailerId,
            "spent": r.spent,
            "won": r.won,
            "city": r.city,
            "sharedToPublic": bool(r.sharedToPublic),
            "createdAt": r.createdAt.isoformat() if r.createdAt else "",
        }
        for r in rows
    ]


@router.post("/records", status_code=201)
def create_record(
    data: PnLRecordCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """新增一筆錢包紀錄. 若 sharedToPublic=True 且 won>0 同時寫入 checkins (匿名)"""
    record = PnLRecord(
        userId=user.id,
        gameName=data.gameName or "",
        scratchcardId=data.scratchcardId,
        retailerId=data.retailerId,
        spent=max(0, int(data.spent)),
        won=max(0, int(data.won)),
        city=(data.city or "").strip() or None,
        sharedToPublic=bool(data.sharedToPublic),
    )

    # 同步到全台熱區 (匿名: checkins 表不存 user 資訊)
    if data.sharedToPublic and record.city and record.won > 0:
        checkin = Checkin(
            city=record.city,
            amount=record.won,
            gameName=record.gameName or "",
        )
        db.add(checkin)
        db.flush()
        record.checkinId = checkin.id

    # 同時更新使用者預設縣市
    if record.city:
        user.lastCheckinCity = record.city

    db.add(record)
    db.commit()
    db.refresh(record)
    return {
        "id": record.id,
        "gameName": record.gameName,
        "scratchcardId": record.scratchcardId,
        "retailerId": record.retailerId,
        "spent": record.spent,
        "won": record.won,
        "city": record.city,
        "sharedToPublic": bool(record.sharedToPublic),
        "createdAt": record.createdAt.isoformat() if record.createdAt else "",
    }


@router.delete("/records/{record_id}")
def delete_record(
    record_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """刪除錢包紀錄. 若曾同步到熱區則一併刪除 checkin"""
    record = db.query(PnLRecord).filter(
        PnLRecord.id == record_id, PnLRecord.userId == user.id
    ).first()
    if not record:
        raise HTTPException(status_code=404, detail="紀錄不存在")

    if record.checkinId:
        db.query(Checkin).filter(Checkin.id == record.checkinId).delete()

    db.delete(record)
    db.commit()
    return {"status": "ok"}


# ============== 用戶偏好 ==============

@router.get("/preferences")
def get_preferences(user: User = Depends(get_current_user)):
    return {"lastCheckinCity": user.lastCheckinCity}


@router.put("/preferences")
def update_preferences(
    data: UserPreferences,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if data.lastCheckinCity is not None:
        user.lastCheckinCity = data.lastCheckinCity.strip() or None
    db.commit()
    return {"lastCheckinCity": user.lastCheckinCity}


# ============== 商家頁面: 該店中獎人數 ==============

@router.get("/retailer/{retailer_id}/winners")
def retailer_winner_count(retailer_id: int, db: Session = Depends(get_db)):
    """取得某店家累積中獎打卡人數 (錢包同步 + 直接打卡)"""
    # 從 PnL 紀錄統計 (有綁定店家且分享公開的)
    pnl_count = (
        db.query(PnLRecord)
        .filter(
            PnLRecord.retailerId == retailer_id,
            PnLRecord.sharedToPublic == True,
            PnLRecord.won > 0,
        )
        .count()
    )
    return {"retailerId": retailer_id, "winnerCount": pnl_count}
