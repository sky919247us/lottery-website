"""
頭獎店家明細模型
儲存台彩官方頭獎 CSV 中的每一筆頭獎紀錄
使用 Unique Key (gameType + period + storeName) 實現 Upsert
"""

from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String, Text, UniqueConstraint

from app.model.database import Base


class JackpotStore(Base):
    """頭獎店家紀錄（逐筆儲存）"""
    __tablename__ = "jackpot_stores"

    id = Column(Integer, primary_key=True, autoincrement=True)
    # 遊戲種類（如：今彩539、大樂透、威力彩）
    gameType = Column(String(50), nullable=False, comment="遊戲種類")
    # 期別（如：115000065）
    period = Column(String(20), nullable=False, comment="期別")
    # 開獎日期（如：2026/03/13）
    drawDate = Column(String(20), default="", comment="開獎日期")
    # 售出頭獎商店名稱
    storeName = Column(String(200), nullable=False, comment="頭獎店家名稱")
    # 售出頭獎商店地址
    storeAddress = Column(Text, default="", comment="頭獎店家地址")
    # 時間戳記
    createdAt = Column(DateTime, default=datetime.utcnow, comment="建立時間")
    updatedAt = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment="更新時間")

    # Unique Key：同一期別 + 遊戲種類 + 店家名稱 視為同一筆紀錄
    __table_args__ = (
        UniqueConstraint("gameType", "period", "storeName", name="uq_jackpot_game_period_store"),
    )
