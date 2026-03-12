"""
Pydantic Schema 定義
用於 API 的請求/回應資料驗證與序列化
"""

from datetime import datetime
from pydantic import BaseModel


class PrizeStructureSchema(BaseModel):
    """單一獎項結構"""
    prizeName: str
    prizeAmount: int = 0
    totalCount: int = 0
    perBookDesc: str = ""

    model_config = {"from_attributes": True}


class ScratchcardListItem(BaseModel):
    """首頁列表用的精簡資料"""
    id: int
    gameId: str
    name: str
    price: int = 0
    maxPrize: str = ""
    maxPrizeAmount: int = 0
    salesRate: str = ""
    salesRateValue: float = 0.0
    grandPrizeCount: int = 0
    grandPrizeUnclaimed: int = 0
    isHighWinRate: bool = False
    issueDate: str = ""
    endDate: str = ""
    overallWinRate: str = ""
    imageUrl: str = ""
    redeemDeadline: str = ""

    model_config = {"from_attributes": True}


class ScratchcardDetail(BaseModel):
    """詳情頁完整資料（含獎金結構）"""
    id: int
    gameId: str
    name: str
    price: int = 0
    maxPrize: str = ""
    maxPrizeAmount: int = 0
    issueDate: str = ""
    endDate: str = ""
    redeemDeadline: str = ""
    salesRate: str = ""
    salesRateValue: float = 0.0
    totalIssued: int = 0
    grandPrizeCount: int = 0
    grandPrizeUnclaimed: int = 0
    isHighWinRate: bool = False
    overallWinRate: str = ""
    prizeInfoUrl: str = ""
    imageUrl: str = ""
    prizes: list[PrizeStructureSchema] = []

    model_config = {"from_attributes": True}


class CheckinCreate(BaseModel):
    """新增中獎打卡的請求"""
    city: str
    amount: int
    gameName: str = ""


class CheckinResponse(BaseModel):
    """中獎打卡回應"""
    id: int
    city: str
    amount: int
    gameName: str = ""
    createdAt: datetime

    model_config = {"from_attributes": True}


class YouTubeLinkSchema(BaseModel):
    """YouTube 影片連結"""
    id: int = 0
    title: str = ""
    url: str
    thumbnailUrl: str = ""
    gameId: str = ""

    model_config = {"from_attributes": True}
