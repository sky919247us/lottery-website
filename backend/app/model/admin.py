"""
管理員帳號模型
支援三種角色：SUPER_ADMIN / ADMIN / MERCHANT
密碼使用 hashlib + salt 進行雜湊儲存
"""

import hashlib
import os
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.model.database import Base


# 角色常數
ROLE_SUPER_ADMIN = "SUPER_ADMIN"
ROLE_ADMIN = "ADMIN"
ROLE_MERCHANT = "MERCHANT"

ALL_ROLES = [ROLE_SUPER_ADMIN, ROLE_ADMIN, ROLE_MERCHANT]


def hash_password(password: str, salt: str | None = None) -> tuple[str, str]:
    """
    使用 SHA-256 + salt 進行密碼雜湊
    回傳 (hashed_password, salt)
    """
    if salt is None:
        salt = os.urandom(32).hex()
    hashed = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        iterations=100_000,
    )
    return hashed.hex(), salt


def verify_password(password: str, hashed: str, salt: str) -> bool:
    """驗證密碼是否正確"""
    check_hash, _ = hash_password(password, salt)
    return check_hash == hashed


class AdminUser(Base):
    """後台管理員帳號"""
    __tablename__ = "admin_users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False, index=True, comment="登入帳號")
    passwordHash = Column(String(128), nullable=False, comment="密碼雜湊值")
    passwordSalt = Column(String(64), nullable=False, comment="密碼鹽值")
    displayName = Column(String(100), default="", comment="顯示名稱")
    role = Column(String(20), nullable=False, default=ROLE_ADMIN, comment="角色：SUPER_ADMIN / ADMIN / MERCHANT")
    retailerId = Column(Integer, ForeignKey("retailers.id"), nullable=True, comment="關聯店家 ID（僅 MERCHANT 角色）")
    isActive = Column(Integer, default=1, comment="是否啟用 (0=停用, 1=啟用)")
    expireAt = Column(DateTime, nullable=True, comment="帳號過期時間 (針對 MERCHANT)")
    lastLoginAt = Column(DateTime, nullable=True, comment="最後登入時間")
    createdAt = Column(DateTime, default=datetime.utcnow)
    updatedAt = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
