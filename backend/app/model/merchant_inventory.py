"""
商家官方庫存管理資料模型
商家透過後台關聯刮刮樂資料庫中的款式，標記即時庫存狀態
"""

from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.model.database import Base


class MerchantInventory(Base):
    """商家官方庫存狀態"""
    __tablename__ = "merchant_inventory"

    id = Column(Integer, primary_key=True, autoincrement=True)
    retailerId = Column(Integer, ForeignKey("retailers.id"), nullable=False, index=True,
                        comment="關聯的經銷商 ID")
    # 關聯刮刮樂資料庫（可選，自訂品項時為 NULL）
    scratchcardId = Column(Integer, ForeignKey("scratchcards.id"), nullable=True, index=True,
                           comment="關聯的刮刮樂 ID（來自官方資料庫）")
    itemName = Column(String(100), nullable=False, comment="品項名稱，例如「2000萬超級紅包」或「2000元刮刮樂」")
    itemPrice = Column(Integer, default=0, comment="面額（用於排序/分組）")
    status = Column(String(10), nullable=False, default="未設定",
                    comment="狀態：充足 / 少量 / 售完 / 未設定")
    updatedAt = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow,
                       comment="最後更新時間")
    createdAt = Column(DateTime, default=datetime.utcnow)

    # 關聯（方便查詢刮刮樂詳情）
    scratchcard = relationship("Scratchcard", foreign_keys=[scratchcardId])

    @property
    def effective_status(self) -> str:
        """
        動態計算有效狀態：
        - 充足：60 天後自動轉為售完
        - 少量：30 天後自動轉為售完
        """
        if self.status not in ("充足", "少量"):
            return self.status

        # 若系統尚未有 updatedAt，則直接回傳原狀態
        if not self.updatedAt:
            return self.status

        now = datetime.utcnow()
        days_diff = (now - self.updatedAt).days

        if self.status == "充足" and days_diff >= 60:
            return "售完"
        if self.status == "少量" and days_diff >= 30:
            return "售完"

        return self.status
