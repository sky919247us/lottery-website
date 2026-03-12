"""
店家評分模型
服務品質星等 + 服務標籤 + 硬體設施群眾回報
"""

from datetime import datetime

from sqlalchemy import (
    Column, DateTime, Float, Integer, String, Text,
    ForeignKey, Boolean, UniqueConstraint
)
from sqlalchemy.orm import relationship

from app.model.database import Base


class RetailerRating(Base):
    """投注站服務品質評分"""
    __tablename__ = "retailer_ratings"
    __table_args__ = (
        # 每人對每間店只能評一次
        UniqueConstraint("userId", "retailerId", name="uq_user_retailer_rating"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    retailerId = Column(Integer, ForeignKey("retailers.id"), nullable=False, index=True)
    userId = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    # 星等 1~5
    rating = Column(Integer, nullable=False, comment="服務品質星等 1~5")

    # 服務品質標籤（逗號分隔）：環境乾淨,店員親切,品項齊全,攻略豐富,交通方便,願意再訪
    serviceTags = Column(String(200), default="", comment="服務標籤（逗號分隔）")

    # 硬體設施標籤（逗號分隔）：群眾回報用
    # hasAC,hasToilet,hasSeats,hasWifi,hasAccessibility,hasEPay,
    # hasStrategy,hasNumberPick,hasScratchBoard,hasMagnifier,hasNewspaper,hasSportTV
    facilityTags = Column(String(300), default="", comment="硬體設施標籤（逗號分隔）")

    # 文字評論（選填）
    comment = Column(Text, default="", comment="文字評論（最多 200 字）")

    # GPS 驗證（200m 內）
    isGpsVerified = Column(Boolean, default=False, comment="是否在 200m 內 GPS 驗證")

    # 評分者 Karma 權重快照（用於加權平均計算）
    karmaWeight = Column(Float, default=1.0, comment="評分者 Karma 權重快照")

    createdAt = Column(DateTime, default=datetime.utcnow)

    # 關聯
    user = relationship("User", back_populates="ratings")
