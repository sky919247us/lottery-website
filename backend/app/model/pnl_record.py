"""
我的錢包個人盈虧紀錄 (PnL Records)
- userId: LINE 登入使用者
- 選填 city: 中獎發生地縣市 (用於分享到全台熱區)
- sharedToPublic: 是否同步寫入 checkins 表 (匿名)
- checkinId: 對應 checkins.id, 用戶刪除錢包紀錄時連帶刪 checkin
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, BigInteger, Boolean, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship

from app.model.database import Base


class PnLRecord(Base):
    __tablename__ = "pnl_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    userId = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    gameName = Column(String(100), default="", comment="款式名稱")
    scratchcardId = Column(Integer, nullable=True, comment="關聯刮刮樂 ID (選填)")
    retailerId = Column(Integer, nullable=True, comment="購買店家 ID (選填)")
    spent = Column(Integer, nullable=False, default=0, comment="花費金額")
    won = Column(Integer, nullable=False, default=0, comment="中獎金額")
    city = Column(String(20), nullable=True, comment="中獎縣市 (選填)")
    sharedToPublic = Column(Boolean, default=False, comment="是否同步到全台熱區 (匿名)")
    checkinId = Column(Integer, nullable=True, comment="對應的 checkin id, 用於刪除連動")
    createdAt = Column(DateTime, default=datetime.utcnow, index=True)

    __table_args__ = (
        Index("idx_pnl_user_created", "userId", "createdAt"),
    )
