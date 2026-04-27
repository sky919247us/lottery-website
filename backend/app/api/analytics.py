"""
刮刮樂分析 API
提供三模式回收率、同價位排行榜、頭獎存活機率等開放查詢端點。

中文用語對照：
  - 回收率（Return Rate）：玩家平均能拿回多少錢，舊文件稱 RTP。
  - 完整回收率：所有獎項一律納入。
  - 排除大獎回收率：把中獎機率低於閾值的大獎排除後重算，反映一般購票實際期望。
  - 自訂排除回收率：使用者自選要排除的獎項後重算。
  - 頭獎存活機率：頭獎尚未被領走的比例。
"""

import math
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session, joinedload

from app.model.database import PrizeStructure, Scratchcard, get_db

router = APIRouter(prefix="/api/analytics", tags=["分析"])


# ============================================================
# 計算工具
# ============================================================

def _expected_value_per_ticket(prizes: list[PrizeStructure], total_issued: int) -> float:
    """單張票的期望回收金額：sum(獎金 × 張數) / 總印製張數"""
    if total_issued <= 0:
        return 0.0
    total = sum((p.prizeAmount or 0) * (p.totalCount or 0) for p in prizes)
    return total / total_issued


def _return_rate(prizes: list[PrizeStructure], total_issued: int, price: int) -> float:
    """回收率 = 期望回收金額 / 售價"""
    if price <= 0:
        return 0.0
    return _expected_value_per_ticket(prizes, total_issued) / price


def _odds_denominator(prize: PrizeStructure, total_issued: int) -> int:
    """取得「幾張中一張」分母。優先使用資料庫欄位，無資料則用 total_issued / count 反推。"""
    if prize.oddsDenominator and prize.oddsDenominator > 0:
        return int(prize.oddsDenominator)
    if (prize.totalCount or 0) > 0 and total_issued > 0:
        return int(total_issued / prize.totalCount)
    return 0


# ============================================================
# 請求/回應 schema
# ============================================================

class ReturnRateRequest(BaseModel):
    """三模式回收率請求"""
    # 模式：full（完整）/ exclude_threshold（排除中獎率低於閾值）/ exclude_ids（自訂排除指定獎項）
    mode: str = "full"
    # exclude_threshold 模式用：排除「幾張中一張」大於此值的獎項。預設 100000 = 排除中獎率低於 1/100000 的獎項
    threshold: int = 100000
    # exclude_ids 模式用：要排除的 prize_structures.id 清單
    excludeIds: list[int] = []


class PrizeBreakdown(BaseModel):
    id: int
    prizeName: str
    prizeAmount: int
    totalCount: int
    oddsDenominator: int
    excluded: bool


class ReturnRateResponse(BaseModel):
    scratchcardId: int
    name: str
    price: int
    totalIssued: int
    mode: str
    modeLabel: str
    returnRate: float
    returnRatePercent: str
    expectedValuePerTicket: float
    excludedPrizeIds: list[int]
    breakdown: list[PrizeBreakdown]
    note: str


class LeaderboardItem(BaseModel):
    id: int
    gameId: str
    name: str
    price: int
    fullReturnRate: float
    excludeJackpotReturnRate: float
    grandPrizeMultiplier: float
    salesRateValue: float
    isPreview: bool
    imageUrl: str


class JackpotSurvivalResponse(BaseModel):
    scratchcardId: int
    name: str
    grandPrizeTotal: int
    grandPrizeUnclaimed: int
    survivalRate: float
    survivalRatePercent: str
    remainingTicketsEstimate: int
    ticketsPerJackpot: Optional[float]
    note: str


# ============================================================
# 端點：三模式回收率
# ============================================================

MODE_LABELS = {
    "full": "完整回收率",
    "exclude_threshold": "排除大獎回收率",
    "exclude_ids": "自訂排除回收率",
}


@router.post("/scratchcards/{scratchcard_id}/return-rate", response_model=ReturnRateResponse)
def calc_return_rate(
    scratchcard_id: int,
    payload: ReturnRateRequest,
    db: Session = Depends(get_db),
):
    """三模式回收率計算（公開）。

    - mode=full：所有獎項納入計算
    - mode=exclude_threshold：排除中獎率低於 1/threshold 的獎項
    - mode=exclude_ids：排除使用者勾選的獎項 id
    """
    card = db.query(Scratchcard).options(joinedload(Scratchcard.prizes)).filter(
        Scratchcard.id == scratchcard_id
    ).first()
    if not card:
        raise HTTPException(status_code=404, detail="找不到刮刮樂")

    if payload.mode not in MODE_LABELS:
        raise HTTPException(status_code=400, detail=f"未知模式：{payload.mode}")

    excluded_ids: set[int] = set()
    breakdown: list[PrizeBreakdown] = []

    for p in card.prizes:
        denom = _odds_denominator(p, card.totalIssued)
        excluded = False
        if payload.mode == "exclude_threshold":
            # 中獎率 = 1/denom，低於 1/threshold 表示 denom > threshold
            if denom > payload.threshold:
                excluded = True
        elif payload.mode == "exclude_ids":
            if p.id in payload.excludeIds:
                excluded = True
        if excluded:
            excluded_ids.add(p.id)
        breakdown.append(PrizeBreakdown(
            id=p.id,
            prizeName=p.prizeName or "",
            prizeAmount=p.prizeAmount or 0,
            totalCount=p.totalCount or 0,
            oddsDenominator=denom,
            excluded=excluded,
        ))

    kept_prizes = [p for p in card.prizes if p.id not in excluded_ids]
    rate = _return_rate(kept_prizes, card.totalIssued, card.price)
    ev = _expected_value_per_ticket(kept_prizes, card.totalIssued)

    note = (
        "回收率為群體期望值統計，代表「購買所有票券的平均回收比例」。"
        "單張購買結果仍為完全隨機，回收率 > 100% 並非獲利保證。"
    )

    return ReturnRateResponse(
        scratchcardId=card.id,
        name=card.name,
        price=card.price,
        totalIssued=card.totalIssued,
        mode=payload.mode,
        modeLabel=MODE_LABELS[payload.mode],
        returnRate=round(rate, 6),
        returnRatePercent=f"{rate * 100:.2f}%",
        expectedValuePerTicket=round(ev, 2),
        excludedPrizeIds=sorted(excluded_ids),
        breakdown=breakdown,
        note=note,
    )


# ============================================================
# 端點：同價位排行榜
# ============================================================

LEADERBOARD_METRICS = {
    "full_return_rate",          # 完整回收率
    "exclude_jackpot_return_rate",  # 排除大獎回收率
    "grand_prize_multiplier",    # 頭獎倍率
    "sales_rate",                # 銷售率（消耗速度近似）
}


@router.get("/leaderboard", response_model=list[LeaderboardItem])
def get_leaderboard(
    price: int = Query(..., description="售價帶（50/100/200/500/1000）"),
    metric: str = Query("full_return_rate", description="排序指標"),
    include_ended: bool = Query(True, description="是否含已停售款"),
    threshold: int = Query(100000, description="排除大獎閾值（幾張中一張）"),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """同價位排行榜（公開，全部維度開放）。"""
    if metric not in LEADERBOARD_METRICS:
        raise HTTPException(status_code=400, detail=f"未知指標：{metric}")

    q = db.query(Scratchcard).options(joinedload(Scratchcard.prizes)).filter(
        Scratchcard.price == price
    )
    if not include_ended:
        # 沒有 status 欄位前，以 isPreview=False 且 endDate 為空當作在售款的近似
        q = q.filter(Scratchcard.isPreview == False)
        q = q.filter((Scratchcard.endDate == "") | (Scratchcard.endDate.is_(None)))
    cards = q.all()

    items: list[LeaderboardItem] = []
    for c in cards:
        full_rate = _return_rate(c.prizes, c.totalIssued, c.price)
        kept = []
        for p in c.prizes:
            denom = _odds_denominator(p, c.totalIssued)
            if denom > threshold:
                continue
            kept.append(p)
        excl_rate = _return_rate(kept, c.totalIssued, c.price)
        multiplier = (c.maxPrizeAmount / c.price) if c.price else 0.0
        items.append(LeaderboardItem(
            id=c.id,
            gameId=c.gameId,
            name=c.name,
            price=c.price,
            fullReturnRate=round(full_rate, 6),
            excludeJackpotReturnRate=round(excl_rate, 6),
            grandPrizeMultiplier=round(multiplier, 2),
            salesRateValue=c.salesRateValue or 0.0,
            isPreview=bool(c.isPreview),
            imageUrl=c.imageUrl or "",
        ))

    sort_key = {
        "full_return_rate": lambda i: i.fullReturnRate,
        "exclude_jackpot_return_rate": lambda i: i.excludeJackpotReturnRate,
        "grand_prize_multiplier": lambda i: i.grandPrizeMultiplier,
        "sales_rate": lambda i: i.salesRateValue,
    }[metric]
    items.sort(key=sort_key, reverse=True)
    return items[:limit]


# ============================================================
# 端點：頭獎存活機率
# ============================================================

@router.get("/scratchcards/{scratchcard_id}/jackpot-survival", response_model=JackpotSurvivalResponse)
def jackpot_survival(scratchcard_id: int, db: Session = Depends(get_db)):
    """頭獎存活機率（公開）。

    survivalRate = 頭獎未兌領 / 頭獎總數
    ticketsPerJackpot = 推估剩餘張數 / 頭獎未兌領（每多少張票藏一張頭獎）
    """
    card = db.query(Scratchcard).filter(Scratchcard.id == scratchcard_id).first()
    if not card:
        raise HTTPException(status_code=404, detail="找不到刮刮樂")

    total = card.grandPrizeCount or 0
    unclaimed = card.grandPrizeUnclaimed or 0
    survival = (unclaimed / total) if total else 0.0

    # 推估剩餘張數：用 salesRateValue（百分比）反推
    sold_ratio = (card.salesRateValue or 0.0) / 100.0
    remaining = int(card.totalIssued * (1 - sold_ratio)) if card.totalIssued else 0
    tickets_per_jackpot: Optional[float] = None
    if unclaimed > 0 and remaining > 0:
        tickets_per_jackpot = round(remaining / unclaimed, 1)

    note = "此為群體統計：剩餘票中平均每 N 張含 1 張頭獎，不代表您買的那張的中獎機率。"

    return JackpotSurvivalResponse(
        scratchcardId=card.id,
        name=card.name,
        grandPrizeTotal=total,
        grandPrizeUnclaimed=unclaimed,
        survivalRate=round(survival, 6),
        survivalRatePercent=f"{survival * 100:.2f}%",
        remainingTicketsEstimate=remaining,
        ticketsPerJackpot=tickets_per_jackpot,
        note=note,
    )


# ============================================================
# 端點：相似遊戲推薦（獎金結構相似度）
# ============================================================

class SimilarItem(BaseModel):
    id: int
    gameId: str
    name: str
    price: int
    imageUrl: str
    issueDate: str
    isPreview: bool
    similarity: float
    similarityPercent: str
    fullReturnRate: float
    grandPrizeMultiplier: float
    prizeLevelCount: int
    reasons: list[str]


class SimilarResponse(BaseModel):
    targetId: int
    targetName: str
    price: int
    items: list[SimilarItem]
    note: str


def _prize_vector(prizes: list[PrizeStructure]) -> dict[int, int]:
    """以「獎金金額 → 張數」當特徵向量。"""
    vec: dict[int, int] = {}
    for p in prizes:
        amt = int(p.prizeAmount or 0)
        cnt = int(p.totalCount or 0)
        if amt <= 0 or cnt <= 0:
            continue
        vec[amt] = vec.get(amt, 0) + cnt
    return vec


def _cosine(a: dict[int, int], b: dict[int, int]) -> float:
    """以「獎金金額」對齊兩向量計算餘弦相似度。"""
    if not a or not b:
        return 0.0
    keys = set(a.keys()) | set(b.keys())
    dot = 0.0
    na = 0.0
    nb = 0.0
    for k in keys:
        va = a.get(k, 0)
        vb = b.get(k, 0)
        dot += va * vb
        na += va * va
        nb += vb * vb
    if na == 0 or nb == 0:
        return 0.0
    return dot / (math.sqrt(na) * math.sqrt(nb))


def _explain(target: Scratchcard, candidate: Scratchcard,
             target_rate: float, cand_rate: float,
             target_mult: float, cand_mult: float) -> list[str]:
    """產生「為什麼相似」的人話說明。"""
    reasons: list[str] = []
    if target.price == candidate.price:
        reasons.append(f"同價位 ${target.price}")
    rate_diff = abs(target_rate - cand_rate) * 100
    if rate_diff < 2:
        reasons.append(f"完整回收率接近（差 {rate_diff:.1f}%）")
    mult_diff_ratio = abs(target_mult - cand_mult) / max(target_mult, 1)
    if mult_diff_ratio < 0.15 and target_mult > 0:
        reasons.append(f"頭獎倍率相近（{cand_mult:.0f}x）")
    if abs(len(target.prizes) - len(candidate.prizes)) <= 1:
        reasons.append(f"獎項層數相同（{len(candidate.prizes)} 層）")
    return reasons


@router.get("/scratchcards/{scratchcard_id}/similar", response_model=SimilarResponse)
def get_similar_scratchcards(
    scratchcard_id: int,
    limit: int = Query(5, ge=1, le=20),
    include_preview: bool = Query(False, description="是否納入預告款"),
    same_price_only: bool = Query(True, description="只比較同價位"),
    db: Session = Depends(get_db),
):
    """新款（或任何一款）刮刮樂的歷史相似款比對（公開）。

    比對方式（Phase 1：純獎金結構，未含玩法）：
      1. 過濾候選池：預設只取同價位、排除自己、排除預告款
      2. 對「獎金金額 → 張數」向量做餘弦相似度
      3. 產生 top N 並附人話說明（同價位 / 回收率接近 / 頭獎倍率相近 / 獎項層數相同）

    後續 Phase 2 接入玩法 AI 解析後，會再加上 mechanic_similarity 加權。
    """
    target = db.query(Scratchcard).options(joinedload(Scratchcard.prizes)).filter(
        Scratchcard.id == scratchcard_id
    ).first()
    if not target:
        raise HTTPException(status_code=404, detail="找不到刮刮樂")

    q = db.query(Scratchcard).options(joinedload(Scratchcard.prizes)).filter(
        Scratchcard.id != scratchcard_id
    )
    if same_price_only:
        q = q.filter(Scratchcard.price == target.price)
    if not include_preview:
        q = q.filter(Scratchcard.isPreview == False)

    candidates = q.all()

    target_vec = _prize_vector(target.prizes)
    target_rate = _return_rate(target.prizes, target.totalIssued, target.price)
    target_mult = (target.maxPrizeAmount / target.price) if target.price else 0.0

    scored: list[tuple[float, Scratchcard, float, float]] = []
    for c in candidates:
        sim = _cosine(target_vec, _prize_vector(c.prizes))
        if sim <= 0:
            continue
        c_rate = _return_rate(c.prizes, c.totalIssued, c.price)
        c_mult = (c.maxPrizeAmount / c.price) if c.price else 0.0
        scored.append((sim, c, c_rate, c_mult))

    scored.sort(key=lambda x: x[0], reverse=True)

    items: list[SimilarItem] = []
    for sim, c, c_rate, c_mult in scored[:limit]:
        items.append(SimilarItem(
            id=c.id,
            gameId=c.gameId,
            name=c.name,
            price=c.price,
            imageUrl=c.imageUrl or "",
            issueDate=c.issueDate or "",
            isPreview=bool(c.isPreview),
            similarity=round(sim, 4),
            similarityPercent=f"{sim * 100:.1f}%",
            fullReturnRate=round(c_rate, 4),
            grandPrizeMultiplier=round(c_mult, 2),
            prizeLevelCount=len(c.prizes),
            reasons=_explain(target, c, target_rate, c_rate, target_mult, c_mult),
        ))

    note = (
        "本相似度僅基於獎金結構（金額分布 + 張數）。"
        "玩法機制（match3 / 比大小 / 連線等）尚未納入，將於 Phase 2 加上 AI 解析後補完。"
    )
    return SimilarResponse(
        targetId=target.id,
        targetName=target.name,
        price=target.price,
        items=items,
        note=note,
    )
