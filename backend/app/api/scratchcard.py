"""
刮刮樂 API 路由
提供列表查詢與單筆詳情端點
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload

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
    db: Session = Depends(get_db),
):
    """取得刮刮樂列表（支援排序與篩選）"""
    # NOTE: eager load prizes 以計算中獎率
    query = db.query(Scratchcard).options(joinedload(Scratchcard.prizes))

    # 篩選
    if price is not None:
        query = query.filter(Scratchcard.price == price)
    if high_win_only:
        query = query.filter(Scratchcard.isHighWinRate == True)

    # 主要排序
    sort_column = getattr(Scratchcard, sort_by, Scratchcard.issueDate)
    if order == "desc":
        query = query.order_by(sort_column.desc())
    else:
        query = query.order_by(sort_column.asc())

    # NOTE: 次要排序 — 同名彩券依發行日期降序（最新在前）
    if sort_by != "issueDate":
        query = query.order_by(Scratchcard.issueDate.desc())

    items = query.all()

    # NOTE: 補算中獎率（爬蟲未抓取時從 prizes 計算）
    for item in items:
        if not item.overallWinRate:
            item.overallWinRate = _compute_win_rate(item)

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
