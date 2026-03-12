"""
Admin 後台認證服務
處理管理員登入、JWT 簽發、角色權限驗證
"""

import os
import logging
from datetime import datetime, timedelta, timezone

from jose import jwt, JWTError
from dotenv import load_dotenv
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.model.database import get_db
from app.model.admin import (
    AdminUser,
    ROLE_SUPER_ADMIN,
    ROLE_ADMIN,
    ROLE_MERCHANT,
    hash_password,
    verify_password,
)

load_dotenv()

logger = logging.getLogger(__name__)

# JWT 設定（管理員使用獨立的 secret）
ADMIN_JWT_SECRET = os.getenv("ADMIN_JWT_SECRET", "admin-fallback-secret-change-me")
ADMIN_JWT_ALGORITHM = "HS256"
ADMIN_JWT_EXPIRE_HOURS = 8  # 管理員 Token 有效期較短（安全考量）

# Bearer Token 依賴（獨立）
admin_bearer_scheme = HTTPBearer(auto_error=False)


def create_admin_jwt(admin_id: int, role: str) -> str:
    """簽發管理員 JWT Token（包含角色資訊）"""
    expire = datetime.now(timezone.utc) + timedelta(hours=ADMIN_JWT_EXPIRE_HOURS)
    payload = {
        "sub": str(admin_id),
        "role": role,
        "type": "admin",
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, ADMIN_JWT_SECRET, algorithm=ADMIN_JWT_ALGORITHM)


def verify_admin_jwt(token: str) -> dict:
    """
    驗證管理員 JWT Token
    回傳 {"admin_id": int, "role": str}
    """
    try:
        payload = jwt.decode(token, ADMIN_JWT_SECRET, algorithms=[ADMIN_JWT_ALGORITHM])
        admin_id = int(payload.get("sub", 0))
        role = payload.get("role", "")
        token_type = payload.get("type", "")
        if not admin_id or token_type != "admin":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="無效的管理員 Token",
            )
        return {"admin_id": admin_id, "role": role}
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="管理員 Token 驗證失敗或已過期",
        )


async def get_current_admin(
    credentials: HTTPAuthorizationCredentials | None = Depends(admin_bearer_scheme),
    db: Session = Depends(get_db),
) -> AdminUser:
    """
    FastAPI 依賴注入：從 Bearer Token 取得當前管理員
    用於所有後台 API 端點
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="請先登入管理後台",
        )
    token_data = verify_admin_jwt(credentials.credentials)
    admin = db.query(AdminUser).filter(AdminUser.id == token_data["admin_id"]).first()
    if not admin:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="管理員帳號不存在",
        )
    if not admin.isActive:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="帳號已被停用",
        )
    return admin


def require_role(*allowed_roles: str):
    """
    角色權限裝飾器
    用法：Depends(require_role(ROLE_SUPER_ADMIN, ROLE_ADMIN))
    """
    async def role_checker(
        admin: AdminUser = Depends(get_current_admin),
    ) -> AdminUser:
        if admin.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"權限不足：需要 {', '.join(allowed_roles)} 角色",
            )
        return admin
    return role_checker


def init_super_admin(db: Session) -> None:
    """
    初始化超級管理員帳號
    僅在資料庫中沒有任何管理員時自動建立
    """
    existing = db.query(AdminUser).first()
    if existing:
        return

    # 從環境變數讀取或使用預設值
    default_username = os.getenv("ADMIN_DEFAULT_USERNAME", "admin")
    default_password = os.getenv("ADMIN_DEFAULT_PASSWORD", "admin123456")

    hashed, salt = hash_password(default_password)
    super_admin = AdminUser(
        username=default_username,
        passwordHash=hashed,
        passwordSalt=salt,
        displayName="超級管理員",
        role=ROLE_SUPER_ADMIN,
    )
    db.add(super_admin)
    db.commit()
    logger.info(f"✅ 已建立預設超級管理員帳號: {default_username}")
