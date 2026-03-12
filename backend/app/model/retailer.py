"""
經銷商（投注站）資料模型
儲存台灣彩券與運彩經銷商地址、座標、設施標籤
"""

from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String, Text

from app.model.database import Base


class Retailer(Base):
    """經銷商 / 投注站"""
    __tablename__ = "retailers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False, comment="投注站名稱")
    address = Column(Text, default="", comment="完整地址")
    city = Column(String(20), default="", comment="縣市")
    district = Column(String(20), default="", comment="行政區")
    source = Column(String(20), default="", comment="來源：台灣彩券 / 台灣運彩")
    lat = Column(Float, nullable=True, comment="緯度")
    lng = Column(Float, nullable=True, comment="經度")
    isActive = Column(Boolean, default=True, comment="是否仍在營業")
    updatedAt = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # --- Phase 3：設施標籤 ---
    hasAC = Column(Boolean, default=False, comment="冷氣")
    hasToilet = Column(Boolean, default=False, comment="廁所")
    hasSeats = Column(Boolean, default=False, comment="座位")
    hasWifi = Column(Boolean, default=False, comment="Wi-Fi")
    hasAccessibility = Column(Boolean, default=False, comment="無障礙空間")
    hasEPay = Column(Boolean, default=False, comment="電子支付")
    hasStrategy = Column(Boolean, default=False, comment="提供攻略")
    hasNumberPick = Column(Boolean, default=False, comment="挑號服務")
    hasScratchBoard = Column(Boolean, default=False, comment="專業刮板")
    hasMagnifier = Column(Boolean, default=False, comment="放大鏡")
    hasReadingGlasses = Column(Boolean, default=False, comment="老花眼鏡")
    hasNewspaper = Column(Boolean, default=False, comment="明牌報紙")
    hasSportTV = Column(Boolean, default=False, comment="運彩轉播")

    # --- Phase 3：認領相關 ---
    isClaimed = Column(Boolean, default=False, comment="是否已被認領")
    merchantTier = Column(String(10), default="", comment="方案層級：basic / pro")
    announcement = Column(String(200), default="", comment="臨時公告文字")

    # --- Phase 4：熱力圖 ---
    jackpotCount = Column(Integer, default=0, comment="近期頭獎開出次數")

    # --- Phase 5：統計與人工評分 ---
    mapClickCount = Column(Integer, default=0, comment="地圖店家點擊次數")
    nearbyInventoryCount = Column(Integer, default=0, comment="附近店家找庫存曝光次數")
    manualRating = Column(Float, nullable=True, comment="超級管理員人工覆寫評分 (1.0~5.0)")
