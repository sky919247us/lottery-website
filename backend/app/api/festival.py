"""
節慶庫存快報 API 路由
提供節慶模式開關與熱力圖資料
"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.model.database import get_db
from app.model.retailer import Retailer

router = APIRouter(prefix="/api/festival", tags=["節慶模式"])


class FestivalStatus(BaseModel):
    """節慶模式狀態"""
    isActive: bool
    name: str
    description: str
    startDate: Optional[str] = None
    endDate: Optional[str] = None


class HeatmapPoint(BaseModel):
    """熱力圖資料點"""
    city: str
    district: str
    lat: float
    lng: float
    jackpotCount: int
    retailerCount: int


# NOTE: 實際生產環境中應從資料庫或設定檔讀取節慶設定
# 目前使用硬編碼的節慶資訊
FESTIVALS = {
    1: {"name": "🧧 春節加碼", "description": "新春開運，全台刮刮樂庫存即時回報", "months": [1, 2]},
    2: {"name": "🏮 元宵節", "description": "元宵求財，中獎機會大增", "months": [2]},
    5: {"name": "🐲 端午節", "description": "端午加碼，粽子旺旺來", "months": [5, 6]},
    9: {"name": "🥮 中秋節", "description": "中秋博餅，刮出好運", "months": [9]},
    10: {"name": "🎃 雙十國慶", "description": "國慶加碼，雙倍好運", "months": [10]},
    12: {"name": "🎄 跨年特別版", "description": "歲末迎新，大獎等你刮", "months": [12]},
}


def get_current_festival() -> FestivalStatus:
    """取得當前是否有節慶活動"""
    now = datetime.now()
    month = now.month

    for _fid, festival in FESTIVALS.items():
        if month in festival["months"]:
            return FestivalStatus(
                isActive=True,
                name=festival["name"],
                description=festival["description"],
            )

    return FestivalStatus(
        isActive=False,
        name="",
        description="目前沒有節慶活動",
    )


@router.get("/status", response_model=FestivalStatus)
def festival_status():
    """取得節慶模式狀態"""
    return get_current_festival()


@router.get("/heatmap", response_model=list[HeatmapPoint])
def festival_heatmap(
    min_jackpot: int = Query(0, description="最低頭獎次數門檻"),
    db: Session = Depends(get_db),
):
    """
    取得熱力圖資料
    依行政區彙總有座標的經銷商數量與頭獎次數
    """
    # 依行政區分組，計算 retailerCount 和 jackpotCount 總和
    results = (
        db.query(
            Retailer.city,
            Retailer.district,
            func.avg(Retailer.lat).label("avg_lat"),
            func.avg(Retailer.lng).label("avg_lng"),
            func.sum(Retailer.jackpotCount).label("total_jackpot"),
            func.count(Retailer.id).label("retailer_count"),
        )
        .filter(
            Retailer.lat.isnot(None),
            Retailer.lng.isnot(None),
            Retailer.isActive == True,
        )
        .group_by(Retailer.city, Retailer.district)
        .having(func.sum(Retailer.jackpotCount) >= min_jackpot)
        .all()
    )

    return [
        HeatmapPoint(
            city=row.city,
            district=row.district,
            lat=round(row.avg_lat, 6),
            lng=round(row.avg_lng, 6),
            jackpotCount=row.total_jackpot or 0,
            retailerCount=row.retailer_count,
        )
        for row in results
        if row.avg_lat and row.avg_lng
    ]
