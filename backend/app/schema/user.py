"""
使用者 & Karma & 庫存回報 Pydantic Schema
"""

from datetime import datetime

from pydantic import BaseModel


class UserResponse(BaseModel):
    """使用者回應"""
    id: int
    lineUserId: str = ""
    displayName: str = ""
    pictureUrl: str = ""
    customNickname: str = ""
    karmaPoints: int = 0
    karmaLevel: int = 1
    levelTitle: str = ""
    levelWeight: int = 1
    nextLevelPoints: int = 100
    isBanned: int = 0

    model_config = {"from_attributes": True}


class KarmaLogResponse(BaseModel):
    """Karma 紀錄回應"""
    id: int
    action: str
    points: int
    description: str
    retailerId: int | None = None
    createdAt: datetime

    model_config = {"from_attributes": True}


class InventoryReportCreate(BaseModel):
    """庫存回報請求"""
    retailerId: int
    userId: int
    item: str  # 2000元 / 1000元 / 500元
    status: str  # 充足 / 少量 / 完售
    lat: float | None = None
    lng: float | None = None


class InventoryReportResponse(BaseModel):
    """庫存回報回應"""
    id: int
    retailerId: int
    userId: int
    item: str
    status: str
    distance: float | None = None
    confidence: float = 0
    createdAt: datetime

    model_config = {"from_attributes": True}


class InventoryStatusResponse(BaseModel):
    """某店家的最新庫存狀態"""
    retailerId: int
    items: list[dict]  # [{item, status, confidence, updatedAt}]


class MerchantClaimCreate(BaseModel):
    """店家認領請求"""
    retailerId: int
    userId: int
    contactName: str = ""
    contactPhone: str = ""
    licenseUrl: str = ""
    idCardUrl: str = ""


class MerchantClaimResponse(BaseModel):
    """認領回應"""
    id: int
    retailerId: int
    userId: int
    status: str
    tier: str
    createdAt: datetime

    model_config = {"from_attributes": True}


class MerchantAnnouncementCreate(BaseModel):
    """臨時公告請求"""
    content: str


class RetailerTagsUpdate(BaseModel):
    """更新設施標籤"""
    hasAC: bool = False
    hasToilet: bool = False
    hasSeats: bool = False
    hasWifi: bool = False
    hasAccessibility: bool = False
    hasEPay: bool = False
    hasStrategy: bool = False
    hasNumberPick: bool = False
    hasScratchBoard: bool = False
    hasMagnifier: bool = False
    hasNewspaper: bool = False
    hasSportTV: bool = False
