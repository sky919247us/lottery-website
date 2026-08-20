"""大樣本統計（整本開箱）Pydantic Schema"""
from pydantic import BaseModel


class UnboxingSummary(BaseModel):
    """全站累計"""

    gameCount: int = 0
    sessionCount: int = 0
    bookCount: int = 0
    ticketCount: int = 0
    totalCost: int = 0
    totalPrize: int = 0
    returnRate: float = 0.0
    winRate: float = 0.0

    model_config = {"from_attributes": True}


class UnboxingGameItem(BaseModel):
    """列表頁一列一款"""

    gameId: str
    name: str = ""
    price: int = 0
    ticketsPerBook: int = 0
    imageUrl: str = ""
    issueDate: str = ""
    endDate: str = ""
    scratchcardId: int | None = None
    bookCount: int = 0
    ticketCount: int = 0
    batchCount: int = 0
    cost: int = 0
    totalPrize: int = 0
    returnRate: float = 0.0
    winRate: float = 0.0
    officialReturnRate: float | None = None
    officialWinRate: float | None = None
    returnRateDelta: float | None = None
    maxPrizeHit: int = 0
    videoCount: int = 0

    model_config = {"from_attributes": True}
