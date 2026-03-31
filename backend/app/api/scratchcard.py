"""
刮刮樂 API 路由
提供列表查詢與單筆詳情端點
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload

from app.api.cache import get_cache, set_cache
from app.model.database import Scratchcard, PrizeStructure, get_db
from app.schema.scratchcard import ScratchcardDetail, ScratchcardListItem

router = APIRouter(prefix="/api/scratchcards", tags=["刮刮樂"])


def _compute_win_rate(item: Scratchcard) -> str:
    """從 prizes 計算中獎率（有獎張數 / 總發行張數）"""
    if not item.prizes or item.totalIssued == 0:
        return item.overallWinRate or ""
    winning = sum(p.totalCount for p in item.prizes if p.prizeAmount > 0)
    if winning == 0:
        return item.overallWinRate or ""
    rate = round(winning / item.totalIssued * 100, 2)
    return f"{rate}%"


@router.get("", response_model=list[ScratchcardListItem])
def get_scratchcard_list(
    sort_by: str = Query("issueDate", description="排序欄位：issueDate / salesRate / price / maxPrizeAmount"),
    order: str = Query("desc", description="排序方向：asc / desc"),
    price: int | None = Query(None, description="依售價篩選"),
    high_win_only: bool = Query(False, description="僅顯示紅色警戒款式"),
    is_preview: bool | None = Query(None, description="篩選預告款 (True) 或在售款 (False)"),
    db: Session = Depends(get_db),
):
    """取得刮刮樂列表（輕量版，不含獎金結構詳情）"""
    # --- 快取檢查 (TTL 86400 秒 = 24 小時，台彩每天 09:00 更新一次) ---
    cache_key = f"scratchcards:list:{sort_by}:{order}:{price}:{high_win_only}:{is_preview}"
    cached = get_cache(cache_key, ttl=86400)
    if cached is not None:
        return cached

    # [OPTIMIZE] 移除 joinedload 避免列表 Payload 過大導致 9s 載入延遲
    query = db.query(Scratchcard)

    # 篩選
    if price is not None:
        query = query.filter(Scratchcard.price == price)
    if high_win_only:
        query = query.filter(Scratchcard.isHighWinRate == True)
    if is_preview is not None:
        query = query.filter(Scratchcard.isPreview == is_preview)

    # 主要排序
    sort_column = getattr(Scratchcard, sort_by, Scratchcard.issueDate)
    if order == "desc":
        query = query.order_by(sort_column.desc())
    else:
        query = query.order_by(sort_column.asc())

    # 次要排序
    if sort_by != "issueDate":
        query = query.order_by(Scratchcard.issueDate.desc())

    items = query.all()

    # NOTE: 列表頁面直接回傳資料庫中的 overallWinRate，不再動態計算，若空白則顯示為 "—"
    for item in items:
        if not item.overallWinRate:
            item.overallWinRate = "—"

    # --- 存入快取 ---
    set_cache(cache_key, items)

    return items


@router.get("/{scratchcard_id}", response_model=ScratchcardDetail)
def get_scratchcard_detail(
    scratchcard_id: int,
    db: Session = Depends(get_db),
):
    """取得單一刮刮樂詳情（含獎金結構）"""
    item = (
        db.query(Scratchcard)
        .options(joinedload(Scratchcard.prizes))
        .filter(Scratchcard.id == scratchcard_id)
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="找不到該刮刮樂")

    # NOTE: 補算中獎率
    if not item.overallWinRate:
        item.overallWinRate = _compute_win_rate(item)

    return item
