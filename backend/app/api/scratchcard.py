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
    item_ids = [it.id for it in items]

    # 撈玩法資料 (一次查詢避免 N+1)
    from app.model.game_mechanic import GameMechanic
    mech_map: dict[int, GameMechanic] = {}
    if item_ids:
        for m in db.query(GameMechanic).filter(GameMechanic.scratchcardId.in_(item_ids)).all():
            mech_map[m.scratchcardId] = m

    # 撈獎金結構統計 (一次性算 winningTickets/per card, 動態計算中獎率)
    from app.model.database import PrizeStructure
    from sqlalchemy import func
    win_count_map: dict[int, int] = {}
    if item_ids:
        rows = (
            db.query(PrizeStructure.scratchcardId, func.sum(PrizeStructure.totalCount))
            .filter(
                PrizeStructure.scratchcardId.in_(item_ids),
                PrizeStructure.prizeAmount > 0,
            )
            .group_by(PrizeStructure.scratchcardId)
            .all()
        )
        win_count_map = {sid: int(cnt or 0) for sid, cnt in rows}

    # 拼裝 response: 動態算中獎率 + 附玩法資料
    result = []
    for item in items:
        # 動態計算: winningTickets / totalIssued (與詳情頁邏輯一致)
        winning = win_count_map.get(item.id, 0)
        total = int(getattr(item, "totalIssued", 0) or 0)
        if total > 0 and winning > 0:
            rate = round(winning / total * 10000) / 100
            item.overallWinRate = f"{rate:.2f}%"
        elif not item.overallWinRate:
            item.overallWinRate = "—"

        d = ScratchcardListItem.model_validate(item, from_attributes=True)
        m = mech_map.get(item.id)
        if m:
            d.mechanicTypes = m.mechanicTypes or []
            d.complexityScore = m.complexityScore or 0
        result.append(d)

    # --- 存入快取 ---
    set_cache(cache_key, [r.model_dump() for r in result])

    return result


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
