"""
SQLAlchemy 資料庫模型與連線設定
支援 PostgreSQL（生產）與 SQLite（本地開發）
"""

import os
from datetime import datetime

from dotenv import load_dotenv
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
    text,
)
from sqlalchemy.orm import DeclarativeBase, Session, relationship, sessionmaker

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./scratchcard.db")

# SQLite 需要特殊連線參數
if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False, "timeout": 15})
else:
    # PostgreSQL 連線池最佳化（2GB RAM VPS）
    # pool_size: 基礎連線數（多使用者併發）
    # max_overflow: 超出基礎後的臨時連線數
    # pool_pre_ping: 連線前檢查有效性（避免閒置連線斷開）
    # pool_recycle: 連線回收時間（60 秒，避免 PostgreSQL 閒置超時）
    engine = create_engine(
        DATABASE_URL,
        pool_size=20,           # 原本 10，改為 20
        max_overflow=30,        # 原本 20，改為 30
        pool_pre_ping=True,
        pool_recycle=60,        # 新增：60 秒自動回收連線
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """SQLAlchemy 宣告式基底類別"""
    pass


class Scratchcard(Base):
    """刮刮樂基本資訊"""
    __tablename__ = "scratchcards"

    id = Column(Integer, primary_key=True, autoincrement=True)
    gameId = Column(String(64), unique=True, nullable=False, index=True, comment="官方編號")
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
    isPreview = Column(Boolean, default=False, comment="即將發售（預告款）")
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


def _create_composite_indexes():
    """建立複合索引以加速常用查詢"""
    is_sqlite = DATABASE_URL.startswith("sqlite")
    is_postgres = DATABASE_URL.startswith("postgresql")

    with engine.connect() as conn:
        if is_postgres:
            # PostgreSQL 複合索引（GIS 查詢最佳化）
            indexes_to_create = [
                "CREATE INDEX IF NOT EXISTS idx_retailers_active_coords ON retailers (isActive, lat, lng) WHERE isActive = true",
                "CREATE INDEX IF NOT EXISTS idx_retailers_tier_active ON retailers (merchantTier, isActive) WHERE isActive = true",
            ]
            for idx_sql in indexes_to_create:
                try:
                    conn.execute(text(idx_sql))
                    conn.commit()
                except Exception as e:
                    print(f"[索引] {idx_sql[:50]}... 已存在或建立失敗: {e}")


def _run_migrations():
    """執行增量欄位遷移（補充 create_all 不會自動新增欄位的限制）"""
    is_sqlite = DATABASE_URL.startswith("sqlite")
    with engine.connect() as conn:
        if is_sqlite:
            # SQLite 用 PRAGMA 檢查欄位
            result = conn.execute(text("PRAGMA table_info(admin_users)"))
            existing_cols = {row[1] for row in result.fetchall()}
            if "retailerId" not in existing_cols:
                conn.execute(text("ALTER TABLE admin_users ADD COLUMN retailerId INTEGER REFERENCES retailers(id)"))
                conn.commit()

            result = conn.execute(text("PRAGMA table_info(scratchcards)"))
            existing_cols = {row[1] for row in result.fetchall()}
            if "isPreview" not in existing_cols:
                conn.execute(text("ALTER TABLE scratchcards ADD COLUMN isPreview BOOLEAN DEFAULT 0"))
                conn.commit()
            # 確保既有資料的 isPreview 不為 NULL（SQLite ALTER TABLE 不會回填既有資料）
            conn.execute(text("UPDATE scratchcards SET isPreview = 0 WHERE isPreview IS NULL"))
            conn.commit()

            result = conn.execute(text("PRAGMA table_info(retailers)"))
            existing_cols = {row[1] for row in result.fetchall()}
            pro_columns = {
                "tierExpireAt": "DATETIME",
                "description": "TEXT DEFAULT ''",
                "bannerUrl": "TEXT DEFAULT ''",
                "contactLine": "VARCHAR(100) DEFAULT ''",
                "contactFb": "VARCHAR(200) DEFAULT ''",
                "contactPhone": "VARCHAR(20) DEFAULT ''",
                "businessHours": "VARCHAR(200) DEFAULT ''",
            }
            for col_name, col_type in pro_columns.items():
                if col_name not in existing_cols:
                    conn.execute(text(f"ALTER TABLE retailers ADD COLUMN {col_name} {col_type}"))
            conn.commit()
            # 建立 admin_retailer_mapping 表（如果不存在）
            result = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='admin_retailer_mapping'"))
            if not result.fetchone():
                conn.execute(text("""
                    CREATE TABLE admin_retailer_mapping (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        adminId INTEGER NOT NULL REFERENCES admin_users(id) ON DELETE CASCADE,
                        retailerId INTEGER NOT NULL REFERENCES retailers(id) ON DELETE CASCADE,
                        createdAt DATETIME DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(adminId, retailerId)
                    )
                """))
                conn.execute(text("CREATE INDEX IF NOT EXISTS ix_arm_adminId ON admin_retailer_mapping(adminId)"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS ix_arm_retailerId ON admin_retailer_mapping(retailerId)"))
                # 回填：將現有 admin_users.retailerId 資料搬到 mapping 表
                conn.execute(text("""
                    INSERT OR IGNORE INTO admin_retailer_mapping (adminId, retailerId, createdAt)
                    SELECT id, retailerId, createdAt FROM admin_users
                    WHERE retailerId IS NOT NULL AND role = 'MERCHANT'
                """))
                conn.commit()

        else:
            # PostgreSQL：用 ALTER TABLE ... ADD COLUMN IF NOT EXISTS 新增欄位
            pg_migrations = [
                'ALTER TABLE scratchcards ADD COLUMN IF NOT EXISTS "isPreview" BOOLEAN DEFAULT false',
                'ALTER TABLE scratchcards ALTER COLUMN "gameId" TYPE VARCHAR(64)',
            ]
            for sql in pg_migrations:
                try:
                    conn.execute(text(sql))
                    conn.commit()
                except Exception:
                    pass
            conn.execute(text('UPDATE scratchcards SET "isPreview" = false WHERE "isPreview" IS NULL'))
            conn.commit()

            # 建立 admin_retailer_mapping 表
            try:
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS admin_retailer_mapping (
                        id SERIAL PRIMARY KEY,
                        "adminId" INTEGER NOT NULL REFERENCES admin_users(id) ON DELETE CASCADE,
                        "retailerId" INTEGER NOT NULL REFERENCES retailers(id) ON DELETE CASCADE,
                        "createdAt" TIMESTAMP DEFAULT NOW(),
                        UNIQUE("adminId", "retailerId")
                    )
                """))
                conn.execute(text('CREATE INDEX IF NOT EXISTS ix_arm_adminId ON admin_retailer_mapping("adminId")'))
                conn.execute(text('CREATE INDEX IF NOT EXISTS ix_arm_retailerId ON admin_retailer_mapping("retailerId")'))
                conn.commit()
            except Exception:
                pass

            # 回填現有資料（只在 mapping 表為空時）
            result = conn.execute(text("SELECT COUNT(*) FROM admin_retailer_mapping"))
            if result.scalar() == 0:
                conn.execute(text("""
                    INSERT INTO admin_retailer_mapping ("adminId", "retailerId", "createdAt")
                    SELECT id, "retailerId", "createdAt" FROM admin_users
                    WHERE "retailerId" IS NOT NULL AND role = 'MERCHANT'
                """))
                conn.commit()


def init_db():
    """建立所有資料表"""
    Base.metadata.create_all(bind=engine)
    _create_composite_indexes()
    _run_migrations()


def get_db():
    """FastAPI 依賴注入：取得 DB Session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
