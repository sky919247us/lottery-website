"""
SQLAlchemy 資料庫模型與連線設定
使用 SQLite 作為本地開發資料庫
"""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, Session, relationship, sessionmaker

# NOTE: 本地開發使用 SQLite，生產環境將切換至 Cloudflare D1
DATABASE_URL = "sqlite:///./scratchcard.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False, "timeout": 15})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """SQLAlchemy 宣告式基底類別"""
    pass


class Scratchcard(Base):
    """刮刮樂基本資訊"""
    __tablename__ = "scratchcards"

    id = Column(Integer, primary_key=True, autoincrement=True)
    gameId = Column(String(20), unique=True, nullable=False, index=True, comment="官方編號")
    name = Column(String(100), nullable=False, comment="遊戲名稱")
    price = Column(BigInteger, default=0, comment="售價（新台幣）")
    maxPrize = Column(String(50), default="", comment="最高獎金文字")
    maxPrizeAmount = Column(BigInteger, default=0, comment="最高獎金數值")
    issueDate = Column(String(20), default="", comment="發行日（民國年格式）")
    endDate = Column(String(20), default="", comment="下市日")
    redeemDeadline = Column(String(20), default="", comment="兌獎截止日")
    totalIssued = Column(BigInteger, default=0, comment="發行張數")
    salesRate = Column(String(20), default="", comment="銷售率文字")
    salesRateValue = Column(Float, default=0.0, comment="銷售率數值（0~100）")
    grandPrizeCount = Column(BigInteger, default=0, comment="頭獎張數")
    grandPrizeUnclaimed = Column(BigInteger, default=0, comment="頭獎未兌領張數")
    overallWinRate = Column(String(20), default="", comment="總中獎率")
    isHighWinRate = Column(Boolean, default=False, comment="「紅色警戒」高勝率預警")
    prizeInfoUrl = Column(Text, default="", comment="獎金結構連結")
    imageUrl = Column(Text, default="", comment="刮刮樂圖片 URL")
    updatedAt = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 關聯：一款刮刮樂擁有多個獎項
    prizes = relationship("PrizeStructure", back_populates="scratchcard", cascade="all, delete-orphan")


class PrizeStructure(Base):
    """獎金結構（單一獎項）"""
    __tablename__ = "prize_structures"

    id = Column(Integer, primary_key=True, autoincrement=True)
    scratchcardId = Column(Integer, ForeignKey("scratchcards.id"), nullable=False, index=True)
    prizeName = Column(String(100), default="", comment="獎項名稱（如 頭獎、NT$1,000,000）")
    prizeAmount = Column(BigInteger, default=0, comment="獎金金額")
    totalCount = Column(BigInteger, default=0, comment="該獎項總張數")
    perBookDesc = Column(String(100), default="", comment="每本描述（如 每本保底 2 張）")

    scratchcard = relationship("Scratchcard", back_populates="prizes")


class Checkin(Base):
    """中獎打卡紀錄"""
    __tablename__ = "checkins"

    id = Column(Integer, primary_key=True, autoincrement=True)
    city = Column(String(20), nullable=False, comment="縣市")
    amount = Column(BigInteger, nullable=False, comment="中獎金額")
    gameName = Column(String(100), default="", comment="款式名稱（選填）")
    createdAt = Column(DateTime, default=datetime.utcnow)


class YouTubeLink(Base):
    """YouTube 開箱影片連結"""
    __tablename__ = "youtube_links"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(200), default="", comment="影片標題")
    url = Column(Text, nullable=False, comment="YouTube 網址")
    thumbnailUrl = Column(Text, default="", comment="縮圖 URL")
    gameId = Column(String(20), default="", comment="關聯的刮刮樂編號（選填）")


# NOTE: 匯入所有模型，確保 init_db 時建立所有資料表
from app.model.retailer import Retailer  # noqa: F401
from app.model.user import User, KarmaLog, InventoryReport  # noqa: F401
from app.model.merchant import MerchantClaim, MerchantAnnouncement  # noqa: F401
from app.model.merchant_photo import MerchantPhoto  # noqa: F401
from app.model.rating import RetailerRating  # noqa: F401
from app.model.admin import AdminUser  # noqa: F401
from app.model.jackpot_store import JackpotStore  # noqa: F401


def init_db():
    """建立所有資料表"""
    Base.metadata.create_all(bind=engine)


def get_db():
    """FastAPI 依賴注入：取得 DB Session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
