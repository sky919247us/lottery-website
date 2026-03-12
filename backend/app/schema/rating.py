"""
評分 Pydantic Schema
"""

from datetime import datetime

from pydantic import BaseModel, Field


class RatingCreate(BaseModel):
    """新增評分請求"""
    retailerId: int
    rating: int = Field(..., ge=1, le=5, description="星等 1~5")
    serviceTags: list[str] = Field(default=[], description="服務品質標籤")
    facilityTags: list[str] = Field(default=[], description="硬體設施標籤")
    comment: str = Field(default="", max_length=200, description="文字評論")
    lat: float | None = None
    lng: float | None = None


class RatingResponse(BaseModel):
    """評分回應"""
    id: int
    retailerId: int
    userId: int
    userName: str = ""
    userLevel: int = 1
    userPictureUrl: str = ""
    rating: int
    serviceTags: list[str] = []
    facilityTags: list[str] = []
    comment: str = ""
    isGpsVerified: bool = False
    karmaWeight: float = 1.0
    createdAt: datetime

    model_config = {"from_attributes": True}


class RatingSummary(BaseModel):
    """店家評分摘要"""
    retailerId: int
    avgRating: float = 0.0
    totalCount: int = 0
    serviceTagStats: dict[str, int] = {}
    facilityTagStats: dict[str, int] = {}


class AuthLineRequest(BaseModel):
    """LINE 登入請求"""
    code: str


class AuthResponse(BaseModel):
    """登入回應"""
    token: str
    user: dict


class ProfileUpdate(BaseModel):
    """更新暱稱"""
    customNickname: str = Field(..., min_length=1, max_length=50)
