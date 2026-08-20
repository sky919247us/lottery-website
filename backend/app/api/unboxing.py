"""大樣本統計（整本開箱）API

資料分級三層，**一律在後端切**，低權限的回應裡不會出現逐張序號：
  T0 未登入      全站與單款彙總、跨本聚合統計（各張號中獎次數、每本回本金額分佈）
  T1 已登入      加上逐本明細（回本金額／中獎張數／槓龜張數／各獎項張數），流水序號遮蔽
  T2 Lv.5 研究員  流水序號全開 + 逐張獎金陣列

回應一律帶 accessLevel，讓前端知道該畫哪種升級引導。
"""
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.api.cache import get_cache, set_cache
from app.model.database import PrizeStructure, Scratchcard, get_db
from app.model.unboxing import UnboxingBook, UnboxingSession
from app.model.user import User
from app.schema.unboxing import UnboxingGameItem, UnboxingSummary
from app.service.auth_service import effective_karma_level, get_optional_user

router = APIRouter(prefix="/api/unboxing", tags=["大樣本統計"])

# 看得到完整逐張序號所需的等級（Lv.5「刮刮研究室研究員」＝ YT 頻道初階會員）
FULL_ACCESS_LEVEL = 5

# 逐張序號是 GET，全域 rate limit middleware 只擋寫入，這裡自行加一層防爬
_detail_hits: dict[str, list[float]] = defaultdict(list)
DETAIL_RPM = 60


def _check_detail_rate(request: Request) -> None:
    import time

    ip = request.client.host if request.client else "unknown"
    now = time.time()
    hits = [t for t in _detail_hits[ip] if now - t < 60]
    if len(hits) >= DETAIL_RPM:
        _detail_hits[ip] = hits
        raise HTTPException(status_code=429, detail="請求過於頻繁，請稍後再試")
    hits.append(now)
    _detail_hits[ip] = hits


def _access_level(user: User | None) -> int:
    if user is None:
        return 0
    return 2 if effective_karma_level(user) >= FULL_ACCESS_LEVEL else 1


def _mask_serial(serial: str) -> str:
    """流水序號遮蔽：只留頭尾各一碼"""
    if not serial:
        return ""
    if len(serial) <= 2:
        return serial[0] + "*"
    return serial[0] + "*" * (len(serial) - 2) + serial[-1]


def _max_dry_run(prizes: list[int]) -> int:
    """最長連續未中獎張數"""
    best = cur = 0
    for p in prizes:
        cur = cur + 1 if not p else 0
        best = max(best, cur)
    return best


def _official_stats(card: Scratchcard, prizes: list[PrizeStructure]) -> dict:
    """由官方獎金結構算理論派彩率與中獎率"""
    if not card or not prizes or not card.totalIssued or not card.price:
        return {"returnRate": None, "winRate": None}
    total_amount = sum((p.prizeAmount or 0) * (p.totalCount or 0) for p in prizes)
    total_count = sum(p.totalCount or 0 for p in prizes)
    sales = card.totalIssued * card.price
    return {
        "returnRate": (total_amount / sales) if sales else None,
        "winRate": (total_count / card.totalIssued) if card.totalIssued else None,
    }


def _book_tiers(prizes: list[int]) -> dict[str, int]:
    tiers: dict[str, int] = {}
    for p in prizes:
        if p > 0:
            key = str(p)
            tiers[key] = tiers.get(key, 0) + 1
    return tiers


def _fallback_maps(sessions) -> tuple[dict, dict]:
    """scratchcards 尚未收錄該期時，用場次快照補面額與款名"""
    price_map, name_map = {}, {}
    for s in sessions:
        if s.price and s.gameId not in price_map:
            price_map[s.gameId] = s.price
        if s.gameName and s.gameId not in name_map:
            name_map[s.gameId] = s.gameName
    return price_map, name_map


def _collect(db: Session):
    """一次撈齊所有已公開的本與對應款式，避免 N+1"""
    sessions = (
        db.query(UnboxingSession).filter(UnboxingSession.isPublished.is_(True)).all()
    )
    session_ids = [s.id for s in sessions]
    books = (
        db.query(UnboxingBook).filter(UnboxingBook.sessionId.in_(session_ids)).all()
        if session_ids
        else []
    )
    game_ids = sorted({b.gameId for b in books})
    cards = (
        db.query(Scratchcard).filter(Scratchcard.gameId.in_(game_ids)).all()
        if game_ids
        else []
    )
    return sessions, books, {c.gameId: c for c in cards}


@router.get("/summary", response_model=UnboxingSummary)
def get_summary(db: Session = Depends(get_db)):
    """全站累計數字（公開）"""
    cached = get_cache("unboxing:summary", ttl=600)
    if cached is not None:
        return cached

    sessions, books, cards = _collect(db)
    price_map, _ = _fallback_maps(sessions)
    tickets = sum(b.ticketCount or 0 for b in books)
    prize = sum(b.totalPrize or 0 for b in books)
    wins = sum(b.winCount or 0 for b in books)
    cost = sum(
        (b.ticketCount or 0)
        * ((cards[b.gameId].price if b.gameId in cards else 0) or price_map.get(b.gameId, 0))
        for b in books
    )
    result = UnboxingSummary(
        gameCount=len({b.gameId for b in books}),
        sessionCount=len(sessions),
        bookCount=len(books),
        ticketCount=tickets,
        totalCost=cost,
        totalPrize=prize,
        returnRate=(prize / cost) if cost else 0.0,
        winRate=(wins / tickets) if tickets else 0.0,
    )
    set_cache("unboxing:summary", result.model_dump())
    return result


@router.get("/games", response_model=list[UnboxingGameItem])
def list_games(
    order: str = Query("desc", description="依期數排序：desc（新到舊）/ asc"),
    db: Session = Depends(get_db),
):
    """款式列表，預設按遊戲期數由新到舊排列（公開）"""
    cache_key = f"unboxing:games:{order}"
    cached = get_cache(cache_key, ttl=600)
    if cached is not None:
        return cached

    sessions, books, cards = _collect(db)
    price_map, name_map = _fallback_maps(sessions)
    by_game: dict[str, list[UnboxingBook]] = defaultdict(list)
    for b in books:
        by_game[b.gameId].append(b)

    video_count: dict[str, int] = defaultdict(int)
    for s in sessions:
        if s.videoId:
            video_count[s.gameId] += 1

    prize_rows = (
        db.query(PrizeStructure)
        .filter(
            PrizeStructure.scratchcardId.in_([c.id for c in cards.values()])
        )
        .all()
        if cards
        else []
    )
    prizes_by_card: dict[int, list[PrizeStructure]] = defaultdict(list)
    for p in prize_rows:
        prizes_by_card[p.scratchcardId].append(p)

    items: list[UnboxingGameItem] = []
    for gid, gbooks in by_game.items():
        card = cards.get(gid)
        price = (card.price if card else 0) or price_map.get(gid, 0)
        tickets = sum(b.ticketCount or 0 for b in gbooks)
        prize = sum(b.totalPrize or 0 for b in gbooks)
        wins = sum(b.winCount or 0 for b in gbooks)
        cost = tickets * price
        official = _official_stats(card, prizes_by_card.get(card.id, [])) if card else {"returnRate": None, "winRate": None}
        rate = (prize / cost) if cost else 0.0
        max_hit = 0
        for b in gbooks:
            for p in b.prizes or []:
                max_hit = max(max_hit, int(p or 0))
        items.append(
            UnboxingGameItem(
                gameId=gid,
                name=(card.name if card else "") or name_map.get(gid, ""),
                price=price,
                ticketsPerBook=(gbooks[0].ticketCount if gbooks else 0),
                imageUrl=card.imageUrl if card else "",
                issueDate=card.issueDate if card else "",
                endDate=card.endDate if card else "",
                scratchcardId=card.id if card else None,
                bookCount=len(gbooks),
                ticketCount=tickets,
                batchCount=len({b.batchKey for b in gbooks if b.batchKey}),
                cost=cost,
                totalPrize=prize,
                returnRate=rate,
                winRate=(wins / tickets) if tickets else 0.0,
                officialReturnRate=official["returnRate"],
                officialWinRate=official["winRate"],
                returnRateDelta=(
                    rate - official["returnRate"] if official["returnRate"] else None
                ),
                maxPrizeHit=max_hit,
                videoCount=video_count.get(gid, 0),
            )
        )

    items.sort(key=lambda x: int(x.gameId) if x.gameId.isdigit() else 0, reverse=(order != "asc"))
    payload = [i.model_dump() for i in items]
    set_cache(cache_key, payload)
    return payload


@router.get("/games/{game_id}")
def get_game_detail(
    game_id: str,
    request: Request,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
):
    """單款詳情。books 的細節依 accessLevel 而定，低權限拿不到逐張序號。"""
    _check_detail_rate(request)
    level = _access_level(user)

    sessions = (
        db.query(UnboxingSession)
        .filter(
            UnboxingSession.gameId == game_id,
            UnboxingSession.isPublished.is_(True),
        )
        .all()
    )
    if not sessions:
        raise HTTPException(status_code=404, detail="查無此款的開箱資料")
    books = (
        db.query(UnboxingBook)
        .filter(UnboxingBook.sessionId.in_([s.id for s in sessions]))
        .order_by(UnboxingBook.sessionId, UnboxingBook.seq)
        .all()
    )
    card = db.query(Scratchcard).filter(Scratchcard.gameId == game_id).first()
    prize_rows = (
        db.query(PrizeStructure).filter(PrizeStructure.scratchcardId == card.id).all()
        if card
        else []
    )
    prize_rows.sort(key=lambda p: -(p.prizeAmount or 0))

    price_map, name_map = _fallback_maps(sessions)
    price = (card.price if card else 0) or price_map.get(game_id, 0)
    game_name = (card.name if card else "") or name_map.get(game_id, "")
    tickets_per_book = books[0].ticketCount if books else 0
    tickets = sum(b.ticketCount or 0 for b in books)
    total_prize = sum(b.totalPrize or 0 for b in books)
    wins = sum(b.winCount or 0 for b in books)
    cost = tickets * price

    # 跨本聚合 —— 這些是彙總統計，不含任何一本的身分，故 T0 也給
    position_wins = [0] * tickets_per_book
    position_prize = [0] * tickets_per_book
    prize_counts: dict[str, int] = {}
    for b in books:
        for i, p in enumerate(b.prizes or []):
            if i >= tickets_per_book:
                break
            if p:
                position_wins[i] += 1
                position_prize[i] += int(p)
                key = str(int(p))
                prize_counts[key] = prize_counts.get(key, 0) + 1

    official = _official_stats(card, prize_rows)
    official_prizes = []
    for p in prize_rows:
        expected = None
        if card and card.totalIssued and tickets_per_book:
            expected = (p.totalCount or 0) / card.totalIssued * tickets_per_book
        official_prizes.append(
            {
                "prizeName": p.prizeName,
                "prizeAmount": p.prizeAmount,
                "totalCount": p.totalCount,
                "perBookDesc": p.perBookDesc,
                "expectedPerBook": expected,
                "measuredPerBook": (
                    prize_counts.get(str(p.prizeAmount), 0) / len(books)
                    if books
                    else 0
                ),
            }
        )

    book_payload = []
    if level >= 1:
        for b in books:
            row = {
                "id": b.id,
                "label": b.serialNo if level >= 2 else _mask_serial(b.serialNo or ""),
                "batchKey": b.batchKey or "",
                "sessionId": b.sessionId,
                "ticketCount": b.ticketCount,
                "totalPrize": b.totalPrize,
                "winCount": b.winCount,
                "missCount": (b.ticketCount or 0) - (b.winCount or 0),
                "maxDryRun": _max_dry_run(b.prizes or []),
                "prizeCounts": _book_tiers(b.prizes or []),
                "returnRate": (
                    (b.totalPrize or 0) / ((b.ticketCount or 0) * price) if price else 0
                ),
            }
            if level >= 2:
                row["serialNo"] = b.serialNo
                row["prizes"] = b.prizes
            book_payload.append(row)

    return {
        "gameId": game_id,
        "name": game_name,
        "price": price,
        "ticketsPerBook": tickets_per_book,
        "imageUrl": card.imageUrl if card else "",
        "issueDate": card.issueDate if card else "",
        "endDate": card.endDate if card else "",
        "totalIssued": card.totalIssued if card else 0,
        "scratchcardId": card.id if card else None,
        "accessLevel": level,
        "requiredLevelForFull": FULL_ACCESS_LEVEL,
        "official": {
            "returnRate": official["returnRate"],
            "winRate": official["winRate"],
            "prizes": official_prizes,
        },
        "measured": {
            "bookCount": len(books),
            "batchCount": len({b.batchKey for b in books if b.batchKey}),
            "ticketCount": tickets,
            "cost": cost,
            "totalPrize": total_prize,
            "returnRate": (total_prize / cost) if cost else 0.0,
            "winRate": (wins / tickets) if tickets else 0.0,
            "prizeCounts": prize_counts,
            # 匿名的每本合計，供直方圖與變異數；不含序號故 T0 也給
            "bookTotals": sorted(b.totalPrize or 0 for b in books),
            "positionWins": position_wins,
            "positionPrize": position_prize,
        },
        "sessions": [
            {
                "id": s.id,
                "title": s.title,
                "videoUrl": s.videoUrl or "",
                "videoId": s.videoId or "",
                "videoTitle": s.videoTitle or "",
                "bookCount": s.bookCount,
                "recordedDate": s.recordedDate or "",
            }
            for s in sessions
        ],
        "books": book_payload,
    }
