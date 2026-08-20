"""整本開箱（大樣本統計）資料模型

一支影片／一次開箱行動 = 一個 UnboxingSession，底下掛 N 本 UnboxingBook。
逐張獎金以 JSON 陣列存在 UnboxingBook.prizes，不另開逐張資料表：
  - 本站聚合一律在 Python 端算（見 app/api/analytics.py），沒有查詢用 service 層
  - 前端「使用者自訂統計」本來就需要拿到原始陣列
  - 逐張開 row 會多出十萬列卻換不到好處
JSON 型別在 SQLite / PostgreSQL 皆可用（先例：app/model/ticket_snapshot.py）。
"""
from datetime import datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from app.model.database import Base

# 面額 → 每本張數對照定義在 ticket_layout（無相依模組），此處 re-export 方便使用
from app.model.ticket_layout import (  # noqa: E402,F401
    PRICE_TO_TICKETS_PER_BOOK,
    default_tickets_per_book,
)


class UnboxingSession(Base):
    """一場開箱（通常對應一支影片，但資料可先上、影片後補）"""

    __tablename__ = "unboxing_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    gameId = Column(String(64), nullable=False, index=True, comment="刮刮樂官方期數")
    gameName = Column(String(100), default="", comment="款名快照（scratchcards 尚未收錄時的備援）")
    price = Column(Integer, default=0, comment="面額快照（同上）")
    title = Column(String(200), default="", comment="場次標題")
    sourceFile = Column(String(200), default="", comment="來源檔名（供追溯）")
    videoUrl = Column(Text, default="", comment="YouTube 網址，資料先上時可為空")
    videoId = Column(String(32), default="", comment="YouTube videoId，供組縮圖網址")
    videoTitle = Column(String(300), default="", comment="YouTube 影片標題")
    recordedDate = Column(String(20), default="", comment="開箱日期 YYYY-MM-DD")
    bookCount = Column(Integer, default=0, comment="本數（快取）")
    ticketsPerBook = Column(Integer, default=0, comment="每本張數")
    note = Column(Text, default="", comment="備註")
    isPublished = Column(Boolean, default=True, index=True, comment="是否對外公開")
    createdAt = Column(DateTime, default=datetime.utcnow)
    updatedAt = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    books = relationship(
        "UnboxingBook", back_populates="session", cascade="all, delete-orphan"
    )


class UnboxingBook(Base):
    """一本（一個樣本）的逐張中獎結果"""

    __tablename__ = "unboxing_books"

    id = Column(Integer, primary_key=True, autoincrement=True)
    sessionId = Column(
        Integer, ForeignKey("unboxing_sessions.id"), nullable=False, index=True
    )
    gameId = Column(String(64), nullable=False, index=True, comment="冗餘存放，供跨場次去重與查詢")
    serialNo = Column(String(24), default="", index=True, comment="流水序號，可能有前導零故存字串")
    label = Column(String(40), default="", comment="顯示用標籤，無序號時為「樣本 N」")
    batchKey = Column(String(40), default="", comment="批次代號，由序號連號自動分群")
    seq = Column(Integer, default=0, comment="在該場次中的順序")
    ticketCount = Column(Integer, default=0)
    prizes = Column(JSON, default=list, comment="逐張獎金陣列，index 0 = 第 1 張，未中獎為 0")
    totalPrize = Column(BigInteger, default=0, comment="合計獎金（快取）")
    winCount = Column(Integer, default=0, comment="中獎張數（快取）")

    session = relationship("UnboxingSession", back_populates="books")
