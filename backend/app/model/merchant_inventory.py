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

    # 統一效期天數：任何庫存記錄自最後更新起算，超過即視為過期
    EXPIRE_DAYS = 30

    @property
    def is_expired(self) -> bool:
        """是否已過 30 天效期（以最後更新時間 updatedAt 倒數）。
        店家每次手動更新會刷新 updatedAt，等同重新續命 30 天。
        """
        if not self.updatedAt:
            return False
        updated = self.updatedAt
        # 容錯：updatedAt 可能為 aware (店家編輯端用 timezone.utc)，統一轉 naive UTC 比較
        if getattr(updated, "tzinfo", None) is not None:
            updated = updated.replace(tzinfo=None)
        return (datetime.utcnow() - updated).days >= self.EXPIRE_DAYS

    @property
    def effective_status(self) -> str:
        """
        動態計算有效狀態（統一 30 天制）：
        - 充足 / 少量 / 售完 皆依店家最後更新時間倒數 30 天
        - 超過 30 天未更新 → 視為過期（售完），不再對外顯示為有貨
        - 自動鋪貨的新款預設「充足」，亦適用同一規則
        """
        if self.status not in ("充足", "少量"):
            return self.status
        if self.is_expired:
            return "售完"
        return self.status
