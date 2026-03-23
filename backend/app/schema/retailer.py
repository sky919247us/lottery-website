"""
經銷商 Pydantic Schema
含 Phase 3 設施標籤與認領欄位
"""

from pydantic import BaseModel


class RetailerResponse(BaseModel):
    """經銷商回應格式"""
    id: int
    name: str
    address: str
    city: str
    district: str
    source: str
    lat: float | None = None
    lng: float | None = None
    isActive: bool
    # Phase 3：設施標籤
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
    hasReadingGlasses: bool = False
    hasNewspaper: bool = False
    hasSportTV: bool = False
    # Phase 3：認領
    isClaimed: bool = False
    merchantTier: str = ""
    announcement: str = ""
    # Phase 4：熱力圖
    jackpotCount: int = 0

    model_config = {"from_attributes": True}


class RetailerMapMarker(BaseModel):
    """地圖標記用輕量格式 — 只含地圖顯示必要欄位"""
    id: int
    name: str
    lat: float | None = None
    lng: float | None = None
    city: str = ""
    district: str = ""
    source: str = ""
    address: str = ""
    isClaimed: bool = False
    merchantTier: str = ""
    jackpotCount: int = 0

    model_config = {"from_attributes": True}
