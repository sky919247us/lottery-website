"""
經銷商 API 路由
提供經銷商查詢功能（支援縣市、來源、關鍵字篩選）
"""

import math

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.cache import get_cache, set_cache
from app.model.database import get_db
from app.model.retailer import Retailer
from app.schema.retailer import RetailerResponse

router = APIRouter(prefix="/api/retailers", tags=["經銷商"])


@router.get("/nearby", response_model=list[RetailerResponse])
def get_nearby_retailers(
    lat: float = Query(..., description="緯度"),
    lng: float = Query(..., description="經度"),
    radius_km: float = Query(5.0, description="半徑（公里）"),
    limit: int = Query(50, description="最多回傳筆數"),
    db: Session = Depends(get_db),
):
    """取得附近經銷商（依距離排序）"""
    # --- 快取檢查 (TTL 60 秒) ---
    cache_key = f"retailers:nearby:{round(lat, 3)}:{round(lng, 3)}:{radius_km}:{limit}"
    cached = get_cache(cache_key, ttl=60)
    if cached is not None:
        return cached

    # 1 度 ≈ 111 公里，先用方形範圍粗篩
    delta = radius_km / 111.0

    query = db.query(Retailer).filter(
        Retailer.isActive == True,
        Retailer.lat.is_not(None),
        Retailer.lng.is_not(None),
        Retailer.lat != 0,
        Retailer.lng != 0,
        Retailer.lat.between(lat - delta, lat + delta),
        Retailer.lng.between(lng - delta, lng + delta),
    )

    candidates = query.all()

    # 在 Python 計算實際距離並排序
    def _distance(r: Retailer) -> float:
        dlat = (r.lat - lat) * 111.0
        dlng = (r.lng - lng) * 111.0 * math.cos(math.radians(lat))
        return math.sqrt(dlat * dlat + dlng * dlng)

    candidates_with_dist = [(r, _distance(r)) for r in candidates]
    candidates_with_dist = [(r, d) for r, d in candidates_with_dist if d <= radius_km]
    candidates_with_dist.sort(key=lambda x: x[1])

    items = [r for r, _ in candidates_with_dist[:limit]]

    # --- 存入快取 ---
    set_cache(cache_key, items)

    return items


@router.get("", response_model=list[RetailerResponse])
def get_retailers(
    city: str | None = Query(None, description="篩選縣市"),
    source: str | None = Query(None, description="篩選來源（台灣彩券/台灣運彩）"),
    search: str | None = Query(None, description="關鍵字搜尋（名稱或地址）"),
    has_coords: bool = Query(False, description="僅回傳有座標的經銷商"),
    exclude_ids: str | None = Query(None, description="排除的 ID 列表，逗號分隔"),
    db: Session = Depends(get_db),
):
    """取得經銷商列表（支援篩選）"""
    # --- 快取檢查 (TTL 120 秒) ---
    cache_key = f"retailers:list:{city}:{source}:{search}:{has_coords}:{exclude_ids}"
    cached = get_cache(cache_key, ttl=120)
    if cached is not None:
        return cached

    query = db.query(Retailer).filter(Retailer.isActive == True)

    # 排除已載入的 ID
    if exclude_ids:
        try:
            ids_to_exclude = [int(x.strip()) for x in exclude_ids.split(",") if x.strip()]
            if ids_to_exclude:
                query = query.filter(Retailer.id.notin_(ids_to_exclude))
        except ValueError:
            pass  # 忽略無效的 ID 格式

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

    items = query.order_by(Retailer.city, Retailer.district, Retailer.name).all()

    # --- 存入快取 ---
    set_cache(cache_key, items)

    return items


@router.get("/{retailer_id}", response_model=RetailerResponse)
def get_retailer(retailer_id: int, db: Session = Depends(get_db)):
    """取得單一經銷商詳情"""
    retailer = db.query(Retailer).filter(Retailer.id == retailer_id).first()
    if not retailer:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="經銷商不存在")
    return retailer
