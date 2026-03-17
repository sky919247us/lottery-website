"""
商家專屬頁面圖片資料模型
存儲商家上傳的店內照片與中獎牆照片的元資料
實際圖片檔案存放於 Cloudflare R2
"""

from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text

from app.model.database import Base


class MerchantPhoto(Base):
    """商家上傳的圖片（相簿 / 中獎牆）"""
    __tablename__ = "merchant_photos"

    id = Column(Integer, primary_key=True, autoincrement=True)
    retailerId = Column(Integer, ForeignKey("retailers.id"), nullable=False, index=True,
                        comment="關聯的經銷商 ID")
    category = Column(String(20), nullable=False, default="gallery",
                      comment="圖片分類：gallery（相簿）/ winning_wall（中獎牆）")
    imageUrl = Column(Text, nullable=False, comment="Cloudflare R2 公開 URL")
    r2Key = Column(Text, default="", comment="R2 物件 Key，用於刪除")
    caption = Column(String(100), default="", comment="圖片說明（中獎牆可填獎項名稱）")
    sortOrder = Column(Integer, default=0, comment="排序順序（越小越前面）")
    createdAt = Column(DateTime, default=datetime.utcnow)
