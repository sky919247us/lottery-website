"""
經銷商 API 路由
提供經銷商查詢功能（支援縣市、來源、關鍵字篩選）
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.model.database import get_db
from app.model.retailer import Retailer
from app.schema.retailer import RetailerResponse

router = APIRouter(prefix="/api/retailers", tags=["經銷商"])


@router.get("", response_model=list[RetailerResponse])
def get_retailers(
    city: str | None = Query(None, description="篩選縣市"),
    source: str | None = Query(None, description="篩選來源（台灣彩券/台灣運彩）"),
    search: str | None = Query(None, description="關鍵字搜尋（名稱或地址）"),
    has_coords: bool = Query(False, description="僅回傳有座標的經銷商"),
    db: Session = Depends(get_db),
):
    """取得經銷商列表（支援篩選）"""
    query = db.query(Retailer).filter(Retailer.isActive == True)

    if city:
        # 相容「台」與「臺」
        alt_city = city.replace("台", "臺") if "台" in city else city.replace("臺", "台")
        query = query.filter((Retailer.city == city) | (Retailer.city == alt_city))

    if source:
        query = query.filter(Retailer.source == source)

    if search:
        # 同樣防護搜尋框的「臺/台」
        keyword = f"%{search}%"
        alt_search = search.replace("台", "臺") if "台" in search else search.replace("臺", "台")
        alt_keyword = f"%{alt_search}%"
        query = query.filter(
            (Retailer.name.like(keyword)) | (Retailer.address.like(keyword)) |
            (Retailer.name.like(alt_keyword)) | (Retailer.address.like(alt_keyword))
        )

    if has_coords:
        # [FIX] 確保 lat/lng 存在且非零 (避免經緯度為 0 顯示異常)
        query = query.filter(Retailer.lat.is_not(None), Retailer.lng.is_not(None))
        query = query.filter(Retailer.lat != 0, Retailer.lng != 0)

    return query.order_by(Retailer.city, Retailer.district, Retailer.name).all()


@router.get("/{retailer_id}", response_model=RetailerResponse)
def get_retailer(retailer_id: int, db: Session = Depends(get_db)):
    """取得單一經銷商詳情"""
    retailer = db.query(Retailer).filter(Retailer.id == retailer_id).first()
    if not retailer:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="經銷商不存在")
    return retailer
