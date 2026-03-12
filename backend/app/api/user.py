"""
使用者 API 路由
LINE 登入使用者查詢、Karma 查詢
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.model.database import get_db
from app.model.user import User, KarmaLog, calc_karma_level, get_level_info, KARMA_LEVELS
from app.schema.user import UserResponse, KarmaLogResponse

router = APIRouter(prefix="/api/users", tags=["使用者"])


def _enrich_user_response(user: User) -> dict:
    """產生包含等級資訊的使用者回應"""
    title, weight, _ = get_level_info(user.karmaLevel)
    # 計算下一等級所需積分
    next_level = min(user.karmaLevel + 1, 10)
    _, _, next_points = get_level_info(next_level)
    return {
        "id": user.id,
        "lineUserId": user.lineUserId or "",
        "displayName": user.displayName or "",
        "pictureUrl": user.pictureUrl or "",
        "customNickname": user.customNickname or user.displayName or "",
        "karmaPoints": user.karmaPoints,
        "karmaLevel": user.karmaLevel,
        "levelTitle": title,
        "levelWeight": weight,
        "nextLevelPoints": next_points,
        "isBanned": user.isBanned,
    }


@router.get("/{user_id}", response_model=UserResponse)
def get_user(user_id: int, db: Session = Depends(get_db)):
    """取得使用者資訊"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="使用者不存在")
    return _enrich_user_response(user)


@router.get("/{user_id}/karma-logs", response_model=list[KarmaLogResponse])
def get_karma_logs(user_id: int, db: Session = Depends(get_db)):
    """取得 Karma 積分紀錄"""
    logs = db.query(KarmaLog).filter(
        KarmaLog.userId == user_id
    ).order_by(KarmaLog.createdAt.desc()).limit(50).all()
    return logs


def add_karma(db: Session, user_id: int, action: str, points: int,
              description: str = "", retailer_id: int | None = None):
    """內部工具函式：加減 Karma 積分並記錄"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return

    # 記錄
    log = KarmaLog(
        userId=user_id,
        action=action,
        points=points,
        description=description,
        retailerId=retailer_id,
    )
    db.add(log)

    # 更新積分 & 等級
    user.karmaPoints = max(0, user.karmaPoints + points)
    user.karmaLevel = calc_karma_level(user.karmaPoints)
    db.commit()
