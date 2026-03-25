"""
店家認領與管理模型
分級制度：基礎版（免費）/ 專業版（$999/年）
"""

from datetime import datetime

from sqlalchemy import (
    Column, DateTime, Integer, String, Text, ForeignKey
)
from sqlalchemy.orm import relationship

from app.model.database import Base


class MerchantClaim(Base):
    """店家認領申請 + PRO 付款"""
    __tablename__ = "merchant_claims"

    id = Column(Integer, primary_key=True, autoincrement=True)
    retailerId = Column(Integer, ForeignKey("retailers.id"), nullable=False, index=True)
    userId = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    contactName = Column(String(50), default="", comment="聯絡人姓名")
    contactPhone = Column(String(20), default="", comment="聯絡電話")
    licenseUrl = Column(Text, default="", comment="營業執照/證照 URL (R2)")
    idCardUrl = Column(Text, default="", comment="代理人身份證 URL (R2)")
    status = Column(String(20), default="pending", comment="審核狀態：pending / approved / rejected")
    tier = Column(String(20), default="basic", comment="方案：basic / pro")
    rejectReason = Column(String(200), default="", comment="駁回原因")

    # Lemonsqueezy PRO 支付
    lemonsqueezyOrderId = Column(String(100), nullable=True, comment="LM 訂單 ID")
    paymentStatus = Column(String(20), default="pending", comment="付款狀態：pending / paid / failed")
    proExpiresAt = Column(DateTime, nullable=True, comment="PRO 到期日期（一年後）")

    createdAt = Column(DateTime, default=datetime.utcnow)
    approvedAt = Column(DateTime, nullable=True, comment="核准時間")

    # 關聯
    announcements = relationship("MerchantAnnouncement", back_populates="claim", cascade="all, delete-orphan")


class MerchantAnnouncement(Base):
    """店家臨時公告（專業版功能）"""
    __tablename__ = "merchant_announcements"

    id = Column(Integer, primary_key=True, autoincrement=True)
    claimId = Column(Integer, ForeignKey("merchant_claims.id"), nullable=False, index=True)
    content = Column(String(200), nullable=False, comment="公告內容")
    isActive = Column(Integer, default=1, comment="是否啟用")
    createdAt = Column(DateTime, default=datetime.utcnow)
    expiresAt = Column(DateTime, nullable=True, comment="過期時間")

    claim = relationship("MerchantClaim", back_populates="announcements")
