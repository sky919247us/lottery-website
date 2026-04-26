"""
收藏與停售提醒 API
所有端點皆使用 get_current_user，未綁定 LINE 帳號（即未登入）會回 401。

停售提醒邏輯：
  - 解析 scratchcard.endDate（民國年格式 "115/05/30"）
  - 若距今 ≤ DEFAULT_REMIND_DAYS 天，回傳 alert=True
  - 兌獎截止日期同樣處理為 redeemAlert
"""

from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.model.database import Scratchcard, get_db
from app.model.favorite import Favorite
from app.model.user import User
from app.service.auth_service import get_current_user

router = APIRouter(prefix="/api/favorites", tags=["收藏"])

DEFAULT_REMIND_DAYS = 14  # 距停售/兌獎截止 14 天內視為要提醒


class FavoriteItem(BaseModel):
    id: int
    scratchcardId: int
    gameId: str
    name: str
    price: int
    imageUrl: str
    salesRate: str
    salesRateValue: float
    endDate: str
    redeemDeadline: str
    isPreview: bool
    daysToEnd: Optional[int]
    daysToRedeemDeadline: Optional[int]
    endingSoon: bool
    redeemingSoon: bool

    model_config = {"from_attributes": True}


class FavoriteCreate(BaseModel):
    scratchcardId: int


def _roc_to_date(s: str) -> Optional[date]:
    """民國年 'YYY/MM/DD' → datetime.date"""
    if not s:
        return None
    try:
        parts = s.replace("-", "/").split("/")
        if len(parts) != 3:
            return None
        y = int(parts[0])
        if y < 1911:
            y += 1911
        return date(y, int(parts[1]), int(parts[2]))
    except (ValueError, IndexError):
        return None


def _days_until(d: Optional[date]) -> Optional[int]:
    if not d:
        return None
    return (d - date.today()).days


def _to_item(fav: Favorite, card: Scratchcard) -> FavoriteItem:
    end_d = _roc_to_date(card.endDate or "")
    redeem_d = _roc_to_date(card.redeemDeadline or "")
    d_end = _days_until(end_d)
    d_redeem = _days_until(redeem_d)
    return FavoriteItem(
        id=fav.id,
        scratchcardId=card.id,
        gameId=card.gameId,
        name=card.name,
        price=card.price,
        imageUrl=card.imageUrl or "",
        salesRate=card.salesRate or "",
        salesRateValue=card.salesRateValue or 0.0,
        endDate=card.endDate or "",
        redeemDeadline=card.redeemDeadline or "",
        isPreview=bool(card.isPreview),
        daysToEnd=d_end,
        daysToRedeemDeadline=d_redeem,
        endingSoon=(d_end is not None and 0 <= d_end <= DEFAULT_REMIND_DAYS),
        redeemingSoon=(d_redeem is not None and 0 <= d_redeem <= DEFAULT_REMIND_DAYS),
    )


@router.get("", response_model=list[FavoriteItem])
def list_favorites(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """取得登入者的收藏清單（含停售提醒旗標）。需 LINE 綁定。"""
    favs = db.query(Favorite).filter(Favorite.userId == user.id).order_by(Favorite.createdAt.desc()).all()
    if not favs:
        return []
    card_ids = [f.scratchcardId for f in favs]
    cards = {c.id: c for c in db.query(Scratchcard).filter(Scratchcard.id.in_(card_ids)).all()}
    return [_to_item(f, cards[f.scratchcardId]) for f in favs if f.scratchcardId in cards]


@router.post("", response_model=FavoriteItem)
def add_favorite(
    payload: FavoriteCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """加入收藏。需 LINE 綁定。"""
    card = db.query(Scratchcard).filter(Scratchcard.id == payload.scratchcardId).first()
    if not card:
        raise HTTPException(status_code=404, detail="找不到刮刮樂")

    existing = db.query(Favorite).filter(
        Favorite.userId == user.id,
        Favorite.scratchcardId == payload.scratchcardId,
    ).first()
    if existing:
        return _to_item(existing, card)

    fav = Favorite(userId=user.id, scratchcardId=payload.scratchcardId)
    db.add(fav)
    db.commit()
    db.refresh(fav)
    return _to_item(fav, card)


@router.delete("/{scratchcard_id}")
def remove_favorite(
    scratchcard_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """移除收藏。需 LINE 綁定。"""
    fav = db.query(Favorite).filter(
        Favorite.userId == user.id,
        Favorite.scratchcardId == scratchcard_id,
    ).first()
    if not fav:
        raise HTTPException(status_code=404, detail="未收藏此款式")
    db.delete(fav)
    db.commit()
    return {"ok": True}


@router.get("/check/{scratchcard_id}")
def check_favorite(
    scratchcard_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """查詢登入者是否已收藏指定款式。需 LINE 綁定。"""
    exists = db.query(Favorite).filter(
        Favorite.userId == user.id,
        Favorite.scratchcardId == scratchcard_id,
    ).first() is not None
    return {"favorited": exists}
