"""
Admin 後台 Pydantic Schema
"""

from datetime import datetime
from pydantic import BaseModel, Field


class AdminLoginRequest(BaseModel):
    """管理員登入請求"""
    username: str = Field(..., min_length=3, max_length=50, description="帳號")
    password: str = Field(..., min_length=6, max_length=100, description="密碼")


class AdminLoginResponse(BaseModel):
    """管理員登入回應"""
    token: str
    user: dict


class AdminCreateRequest(BaseModel):
    """建立管理員帳號請求（僅超級管理員可用）"""
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6, max_length=100)
    displayName: str = Field(default="", max_length=100)
    role: str = Field(default="ADMIN", description="角色：SUPER_ADMIN / ADMIN / MERCHANT")
    retailerId: int | None = Field(default=None, description="關聯店家 ID（僅 MERCHANT 用）")
    expireAt: datetime | None = Field(default=None, description="帳號過期時間")


class AdminUpdateRequest(BaseModel):
    """更新管理員帳號請求"""
    displayName: str | None = None
    role: str | None = None
    retailerId: int | None = None
    isActive: int | None = None
    expireAt: datetime | None = None


class AdminChangePasswordRequest(BaseModel):
    """修改密碼請求"""
    oldPassword: str = Field(..., min_length=6)
    newPassword: str = Field(..., min_length=6)

class AdminRetailerUpdateRequest(BaseModel):
    """管理員修改彩券行資料"""
    name: str | None = None
    address: str | None = None
    city: str | None = None
    district: str | None = None
    lat: float | None = None
    lng: float | None = None
    isActive: bool | None = None
    isClaimed: bool | None = None
    merchantTier: str | None = None
    announcement: str | None = None
    manualRating: float | None = None
    jackpotCount: int | None = None

class MerchantStoreUpdate(BaseModel):
    """商家修改自己的店舖資訊"""
    announcement: str | None = None
    hasAC: bool | None = None
    hasToilet: bool | None = None
    hasSeats: bool | None = None
    hasWifi: bool | None = None
    hasAccessibility: bool | None = None
    hasEPay: bool | None = None
    hasStrategy: bool | None = None
    hasNumberPick: bool | None = None
    hasScratchBoard: bool | None = None
    hasMagnifier: bool | None = None
    hasReadingGlasses: bool | None = None
    hasNewspaper: bool | None = None
    hasSportTV: bool | None = None


class KarmaAdjustRequest(BaseModel):
    """管理員手動調整使用者 Karma 積分請求"""
    points: int = Field(default=0, description="要增減的積分數值")
    reason: str = Field(default="", description="調整原因")
    set_to: int | None = Field(default=None, description="若指定，則直接將積分設為此值")


class BulkBanRequest(BaseModel):
    userIds: list[int]
    isBanned: bool


class BulkRetailerStatusRequest(BaseModel):
    retailerIds: list[int]
    isActive: bool

