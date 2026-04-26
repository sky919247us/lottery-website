"""
每日快照寫入服務
在每日爬蟲完成後執行，將當下各款刮刮樂狀態寫入 ticket_snapshots 表，
作為消耗速度、頭獎存活機率曲線、正期望值窗口統計的歷史基礎。

每款刮刮樂每日僅一筆（uq_snapshot_card_date 限制），重複呼叫會走 upsert。
"""

import logging
from datetime import date

from sqlalchemy.orm import Session

from app.model.database import PrizeStructure, Scratchcard, SessionLocal
from app.model.ticket_snapshot import TicketSnapshot

logger = logging.getLogger(__name__)


def _expected_value(prizes: list[PrizeStructure], total_issued: int) -> float:
    if total_issued <= 0:
        return 0.0
    return sum((p.prizeAmount or 0) * (p.totalCount or 0) for p in prizes) / total_issued


def _odds_denominator(prize: PrizeStructure, total_issued: int) -> int:
    if prize.oddsDenominator and prize.oddsDenominator > 0:
        return int(prize.oddsDenominator)
    if (prize.totalCount or 0) > 0 and total_issued > 0:
        return int(total_issued / prize.totalCount)
    return 0


def write_daily_snapshots(snapshot_date: date | None = None) -> int:
    """寫入今日所有在售款的快照。回傳寫入筆數。"""
    snapshot_date = snapshot_date or date.today()
    db: Session = SessionLocal()
    written = 0
    try:
        # 只對非預告款寫快照
        cards = db.query(Scratchcard).filter(Scratchcard.isPreview == False).all()

        for card in cards:
            prizes = db.query(PrizeStructure).filter(
                PrizeStructure.scratchcardId == card.id
            ).all()

            sold_ratio = (card.salesRateValue or 0.0) / 100.0
            remaining = int(card.totalIssued * (1 - sold_ratio)) if card.totalIssued else 0

            full_ev = _expected_value(prizes, card.totalIssued)
            full_rate = (full_ev / card.price) if card.price else 0.0

            kept = [p for p in prizes if _odds_denominator(p, card.totalIssued) <= 100000]
            excl_ev = _expected_value(kept, card.totalIssued)
            excl_rate = (excl_ev / card.price) if card.price else 0.0

            remaining_prizes = {
                str(p.prizeAmount): p.totalCount for p in prizes
            }

            existing = db.query(TicketSnapshot).filter(
                TicketSnapshot.scratchcardId == card.id,
                TicketSnapshot.snapshotDate == snapshot_date,
            ).first()

            if existing:
                existing.remainingTickets = remaining
                existing.remainingPrizes = remaining_prizes
                existing.fullReturnRate = round(full_rate, 6)
                existing.excludeJackpotReturnRate = round(excl_rate, 6)
                existing.grandPrizeUnclaimed = card.grandPrizeUnclaimed or 0
                existing.soldRatio = round(sold_ratio, 6)
            else:
                db.add(TicketSnapshot(
                    scratchcardId=card.id,
                    snapshotDate=snapshot_date,
                    remainingTickets=remaining,
                    remainingPrizes=remaining_prizes,
                    fullReturnRate=round(full_rate, 6),
                    excludeJackpotReturnRate=round(excl_rate, 6),
                    grandPrizeUnclaimed=card.grandPrizeUnclaimed or 0,
                    soldRatio=round(sold_ratio, 6),
                ))
            written += 1

        db.commit()
        logger.info(f"📸 寫入 {written} 筆每日快照（{snapshot_date}）")
    except Exception as e:
        db.rollback()
        logger.error(f"❌ 寫入每日快照失敗: {e}")
        raise
    finally:
        db.close()
    return written
