"""
LINE OAuth 認證 API 路由
"""

import logging

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.model.database import get_db
from app.model.user import User, get_level_info
from app.schema.rating import AuthLineRequest, AuthResponse, ProfileUpdate
from app.service.auth_service import (
    exchange_code_for_token,
    get_line_profile,
    create_jwt,
    find_or_create_user,
    get_current_user,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["認證"])


def _user_to_dict(user: User) -> dict:
    """將 User 物件轉為前端需要的字典"""
    title, weight, _ = get_level_info(user.karmaLevel)
    next_level = min(user.karmaLevel + 1, 10)
    _, _, next_points = get_level_info(next_level)
    return {
        "id": user.id,
        "lineUserId": user.lineUserId,
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


@router.post("/line", response_model=AuthResponse)
async def line_login(data: AuthLineRequest, db: Session = Depends(get_db)):
    """
    LINE 登入：接收授權碼 → 換取 token → 建立/更新使用者 → 回傳 JWT
    """
    logger.info("LINE 登入：開始處理授權碼交換")

    # 1. 用 code 換 access_token
    token_data = await exchange_code_for_token(data.code)
    access_token = token_data.get("access_token")

    # 2. 取得 LINE 使用者資料
    profile = await get_line_profile(access_token)
    line_user_id = profile["userId"]
    display_name = profile.get("displayName", "LINE 使用者")
    picture_url = profile.get("pictureUrl", "")

    # 3. 建立/更新使用者
    user = find_or_create_user(db, line_user_id, display_name, picture_url)

    # 4. 簽發 JWT
    jwt_token = create_jwt(user.id)

    logger.info(f"LINE 登入成功: {display_name} (userId: {user.id})")

    return AuthResponse(
        token=jwt_token,
        user=_user_to_dict(user),
    )


@router.get("/me")
async def get_me(user: User = Depends(get_current_user)):
    """取得當前登入使用者資料"""
    return _user_to_dict(user)


@router.put("/profile")
async def update_profile(
    data: ProfileUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """更新使用者自訂暱稱"""
    user.customNickname = data.customNickname
    db.commit()
    db.refresh(user)
    return _user_to_dict(user)
