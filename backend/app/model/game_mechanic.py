"""
玩法結構表（AI 解析後的玩法資料）
一款刮刮樂對應一筆。重新解析時走 upsert（依 scratchcardId）。
"""

from datetime import datetime

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)

from app.model.database import Base


class GameMechanic(Base):
    """AI 解析後的玩法資料"""
    __tablename__ = "game_mechanics"

    id = Column(Integer, primary_key=True, autoincrement=True)
    scratchcardId = Column(Integer, ForeignKey("scratchcards.id", ondelete="CASCADE"), nullable=False, index=True)
    rawText = Column(Text, default="", comment="玩法原文（爬蟲或人工貼入）")
    sourceType = Column(String(20), default="text", comment="來源類型：text / image / url")
    sourceUrl = Column(Text, default="", comment="圖片或頁面 URL")

    mechanicTypes = Column(JSON, default=list, comment="玩法機制陣列：match3 / multiplier / bingo_line / ...")
    parsedTags = Column(JSON, default=list, comment="所有適用標籤陣列")
    layoutTags = Column(JSON, default=list, comment="視覺佈局標籤")
    complexityScore = Column(Integer, default=0, comment="複雜度 1~5")
    resultSpeed = Column(String(20), default="", comment="instant / multi_zone / sequence")
    aiDescription = Column(Text, default="", comment="AI 自動生成的繁中玩法介紹")

    parseModel = Column(String(50), default="", comment="使用的 AI 模型版本")
    parseProvider = Column(String(20), default="", comment="供應商：gemini / openai / claude")
    parsedAt = Column(DateTime, default=datetime.utcnow, comment="AI 解析時間")
    updatedAt = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("scratchcardId", name="uq_mechanic_scratchcard"),
    )
