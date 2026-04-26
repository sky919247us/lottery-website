"""
收藏與停售提醒模型
- Favorite：使用者收藏的刮刮樂款式
- 停售提醒：使用者收藏的款式若 endDate 接近，會在 GET /api/favorites 回應時夾帶 alert 旗標。
  推播動作交由前端決定（顯示 toast / 紅點），LINE 推播留待 line_notify 整合。

只有綁定 LINE 的 User 才能呼叫，因為 API 走 get_current_user（強制登入）。
"""

from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import relationship

from app.model.database import Base


class Favorite(Base):
    """使用者收藏的刮刮樂"""
    __tablename__ = "favorites"

    id = Column(Integer, primary_key=True, autoincrement=True)
    userId = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    scratchcardId = Column(Integer, ForeignKey("scratchcards.id", ondelete="CASCADE"), nullable=False, index=True)
    createdAt = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("userId", "scratchcardId", name="uq_favorite_user_card"),
    )
