"""
商家方案狀態判斷與過期處理。
與前端 admin/utils/tier.ts 邏輯一致：
  視為 PRO 的條件 = (merchantTier == 'pro') AND (tierExpireAt IS NULL OR tierExpireAt > now())
"""

import logging
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.model.merchant import MerchantClaim
from app.model.retailer import Retailer

logger = logging.getLogger(__name__)


def is_retailer_pro(retailer: Optional[Retailer]) -> bool:
    if retailer is None:
        return False
    if (retailer.merchantTier or "").lower() != "pro":
        return False
    expire = getattr(retailer, "tierExpireAt", None)
    if expire is None:
        return True  # 永久或未設到期日視為有效
    return expire > datetime.utcnow()


def expire_overdue_pro(db: Session) -> int:
    """
    把所有 (tier=pro AND tierExpireAt < now()) 的 retailer 物理降級為 basic，
    同時同步 MerchantClaim。
    回傳處理筆數。每日排程呼叫。
    """
    now = datetime.utcnow()
    overdue = (
        db.query(Retailer)
        .filter(Retailer.merchantTier == "pro", Retailer.tierExpireAt != None, Retailer.tierExpireAt < now)
        .all()
    )
    count = 0
    for r in overdue:
        r.merchantTier = "basic"
        r.tierExpireAt = None
        claim = (
            db.query(MerchantClaim)
            .filter(MerchantClaim.retailerId == r.id, MerchantClaim.status == "approved")
            .first()
        )
        if claim:
            claim.tier = "basic"
            claim.proExpiresAt = None
            if claim.paymentStatus == "paid":
                claim.paymentStatus = "expired"
        count += 1
        logger.info("[tier-expire] 過期降級 retailer=%s", r.id)
    if count:
        db.commit()
    return count
