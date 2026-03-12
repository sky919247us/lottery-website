"""
LINE OAuth 認證服務
處理 LINE Login 授權碼交換、使用者檔案取得、JWT 簽發與驗證
"""

import os
import logging
from datetime import datetime, timedelta, timezone

import httpx
from jose import jwt, JWTError
from dotenv import load_dotenv
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.model.database import get_db
from app.model.user import User

# 載入環境變數
load_dotenv()

logger = logging.getLogger(__name__)

# LINE OAuth 設定
LINE_CHANNEL_ID = os.getenv("LINE_CHANNEL_ID", "")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET", "")
LINE_REDIRECT_URI = os.getenv("LINE_REDIRECT_URI", "http://localhost:5173/auth/callback")

# JWT 設定
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "fallback-secret-key-change-me")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_DAYS = 30

# FastAPI Bearer Token 依賴
bearer_scheme = HTTPBearer(auto_error=False)


async def exchange_code_for_token(code: str) -> dict:
    """
    用授權碼向 LINE 換取 access_token
    回傳包含 access_token, id_token 等的回應字典
    """
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.line.me/oauth2/v2.1/token",
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": LINE_REDIRECT_URI,
                "client_id": LINE_CHANNEL_ID,
                "client_secret": LINE_CHANNEL_SECRET,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        if response.status_code != 200:
            logger.error(f"LINE token exchange failed: {response.text}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"LINE 授權失敗: {response.text}",
            )
        return response.json()


async def get_line_profile(access_token: str) -> dict:
    """
    用 access_token 取得 LINE 使用者資料
    回傳 {userId, displayName, pictureUrl, statusMessage}
    """
    async with httpx.AsyncClient() as client:
        response = await client.get(
            "https://api.line.me/v2/profile",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if response.status_code != 200:
            logger.error(f"LINE profile fetch failed: {response.text}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="無法取得 LINE 使用者資料",
            )
        return response.json()


def create_jwt(user_id: int) -> str:
    """簽發 JWT Token"""
    expire = datetime.now(timezone.utc) + timedelta(days=JWT_EXPIRE_DAYS)
    payload = {
        "sub": str(user_id),
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def verify_jwt(token: str) -> int:
    """
    驗證 JWT Token，回傳 user_id
    若驗證失敗則拋出 HTTPException
    """
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        user_id = int(payload.get("sub", 0))
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="無效的 Token",
            )
        return user_id
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token 驗證失敗或已過期",
        )


def find_or_create_user(
    db: Session,
    line_user_id: str,
    display_name: str,
    picture_url: str,
) -> User:
    """
    根據 LINE User ID 查找或建立使用者
    回傳 User 物件
    """
    user = db.query(User).filter(User.lineUserId == line_user_id).first()

    if user:
        # 更新 LINE 資料（頭貼、名稱可能會變）
        user.displayName = display_name
        user.pictureUrl = picture_url
        db.commit()
        db.refresh(user)
        return user

    # 建立新使用者
    user = User(
        lineUserId=line_user_id,
        displayName=display_name,
        pictureUrl=picture_url,
        customNickname=display_name,  # 預設用 LINE 名稱
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    logger.info(f"新使用者建立: {display_name} (LINE: {line_user_id})")
    return user


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """
    FastAPI 依賴注入：從 Bearer Token 取得當前登入使用者
    用於需要登入的 API 端點
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="請先登入 LINE",
        )
    user_id = verify_jwt(credentials.credentials)
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="使用者不存在",
        )
    if user.isBanned:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="帳號已被封禁",
        )
    return user


async def get_optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User | None:
    """
    FastAPI 依賴注入：嘗試取得當前登入使用者（可選）
    未登入時回傳 None 而非拋出錯誤
    """
    if not credentials:
        return None
    try:
        user_id = verify_jwt(credentials.credentials)
        return db.query(User).filter(User.id == user_id).first()
    except HTTPException:
        return None
