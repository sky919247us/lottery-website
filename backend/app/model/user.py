"""
使用者與 Karma 信用系統模型
10 級信用體系 + LINE 身分認證
"""

from datetime import datetime

from sqlalchemy import (
    BigInteger, Column, DateTime, Float,
    Integer, String, Text, ForeignKey, Boolean
)
from sqlalchemy.orm import relationship

from app.model.database import Base


# Karma 等級設定：等級 -> (稱號, 權重, 所需積分)
KARMA_LEVELS = {
    1: ("刮刮新手", 1, 0),
    2: ("尋寶學徒", 2, 100),
    3: ("幸運路人", 4, 300),
    4: ("資深玩家", 7, 800),
    5: ("刮刮研究室研究員", 12, 1500),   # YT 頻道初階會員對應等級
    6: ("情報專家", 20, 3000),
    7: ("彩券達人", 35, 6000),
    8: ("刮刮研究室金主", 60, 12000),    # YT 頻道高階會員對應等級
    9: ("傳奇財神", 100, 25000),
    10: ("官方觀察員", 250, 999999),     # 手動授予
}


def calc_karma_level(points: int) -> int:
    """根據積分計算等級"""
    level = 1
    for lv, (_, _, required) in KARMA_LEVELS.items():
        if points >= required:
            level = lv
    return level


def get_level_info(level: int) -> tuple[str, int, int]:
    """取得等級資訊 (稱號, 權重, 所需積分)"""
    return KARMA_LEVELS.get(level, KARMA_LEVELS[1])


class User(Base):
    """社群使用者（LINE 登入制）"""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # 新增的 LINE 資訊
    lineUserId = Column(String(100), unique=True, nullable=False, index=True, comment="LINE User ID")
    displayName = Column(String(100), nullable=True, comment="LINE 顯示名稱")
    pictureUrl = Column(Text, nullable=True, comment="LINE 大頭貼 URL")
    customNickname = Column(String(50), nullable=True, comment="使用者自訂暱稱")
    
    karmaPoints = Column(Integer, default=0, comment="Karma 總積分")
    karmaLevel = Column(Integer, default=1, comment="目前等級 1~10")
    isBanned = Column(Integer, default=0, comment="是否封禁 (0=否, 1=是)")
    createdAt = Column(DateTime, default=datetime.utcnow)

    # 關聯
    karmaLogs = relationship("KarmaLog", back_populates="user", cascade="all, delete-orphan")
    inventoryReports = relationship("InventoryReport", back_populates="user", cascade="all, delete-orphan")
    ratings = relationship("RetailerRating", back_populates="user", cascade="all, delete-orphan")


class KarmaLog(Base):
    """Karma 積分變動紀錄"""
    __tablename__ = "karma_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    userId = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    action = Column(String(50), nullable=False, comment="動作：checkin, report, rating, liked, penalty")
    points = Column(Integer, nullable=False, comment="積分變動（正=加分, 負=扣分）")
    description = Column(String(200), default="", comment="說明")
    retailerId = Column(Integer, ForeignKey("retailers.id"), nullable=True, comment="相關店家")
    createdAt = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="karmaLogs")


class InventoryReport(Base):
    """即時庫存回報"""
    __tablename__ = "inventory_reports"

    id = Column(Integer, primary_key=True, autoincrement=True)
    retailerId = Column(Integer, ForeignKey("retailers.id"), nullable=False, index=True)
    userId = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    item = Column(String(20), nullable=False, comment="品項：2000元 / 1000元 / 500元")
    status = Column(String(10), nullable=False, comment="狀態：充足 / 少量 / 完售")
    lat = Column(Float, nullable=True, comment="回報時的緯度")
    lng = Column(Float, nullable=True, comment="回報時的經度")
    distance = Column(Float, nullable=True, comment="與店家的距離（公尺）")
    confidence = Column(Float, default=0, comment="信心值（等級權重 × 距離因子）")
    createdAt = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="inventoryReports")
