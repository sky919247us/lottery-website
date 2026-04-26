"""
刮刮樂每日快照模型
每日爬蟲執行後寫入一筆，用於計算消耗速度、頭獎存活機率曲線、
以及未來累積足夠歷史資料後的正期望值窗口統計。
"""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    UniqueConstraint,
)

from app.model.database import Base


class TicketSnapshot(Base):
    """每日快照（一款遊戲一天一筆）"""
    __tablename__ = "ticket_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    scratchcardId = Column(Integer, ForeignKey("scratchcards.id"), nullable=False, index=True)
    snapshotDate = Column(Date, nullable=False, index=True, comment="快照日期")
    remainingTickets = Column(BigInteger, default=0, comment="當日剩餘張數")
    remainingPrizes = Column(JSON, default=dict, comment="各獎項剩餘數量 {prizeAmount: count}")
    fullReturnRate = Column(Float, nullable=True, comment="完整回收率")
    excludeJackpotReturnRate = Column(Float, nullable=True, comment="排除大獎回收率")
    grandPrizeUnclaimed = Column(BigInteger, default=0, comment="當日頭獎未兌領張數")
    soldRatio = Column(Float, default=0.0, comment="累積銷售比例（0~1）")
    createdAt = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("scratchcardId", "snapshotDate", name="uq_snapshot_card_date"),
    )
