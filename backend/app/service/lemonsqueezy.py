"""
Lemonsqueezy 支付集成服務
處理 PRO 商家年費付款、Webhook、訂單驗證
"""

import os
import json
import hmac
import hashlib
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session
from app.model.merchant import MerchantClaim


class LemonsqueezyService:
    """Lemonsqueezy 支付服務"""

    PRODUCT_ID = os.getenv("LEMONSQUEEZY_PRODUCT_ID", "919326")
    CHECKOUT_URL = os.getenv("LEMONSQUEEZY_CHECKOUT_URL", "")
    SIGNING_SECRET = os.getenv("LEMONSQUEEZY_SIGNING_SECRET", "")

    @staticmethod
    def verify_webhook_signature(payload: str, signature: str) -> bool:
        """
        驗證 Webhook 簽名（使用 X-Signature header）

        Args:
            payload: 原始請求 body (bytes)
            signature: X-Signature header 值

        Returns:
            True 如果簽名正確
        """
        if not LemonsqueezyService.SIGNING_SECRET:
            # 未設定 secret，先跳過驗證（開發模式）
            return True

        # Lemonsqueezy 使用 HMAC-SHA256
        expected = hmac.new(
            LemonsqueezyService.SIGNING_SECRET.encode(),
            payload,
            hashlib.sha256
        ).hexdigest()

        return hmac.compare_digest(signature, expected)

    @staticmethod
    def handle_order_created(
        db: Session,
        order_data: dict
    ) -> Optional[MerchantClaim]:
        """
        處理 order.created 事件

        Args:
            db: 數據庫 session
            order_data: Webhook 事件 data.order

        Returns:
            更新後的 MerchantClaim，或 None
        """
        order_id = order_data.get("id")
        customer_email = order_data.get("customer_email")
        status = order_data.get("status")  # 通常是 "pending" 或 "completed"

        # 只處理已支付的訂單
        if status != "completed":
            return None

        # 根據 customer_email 查找 MerchantClaim
        claim = db.query(MerchantClaim).filter(
            MerchantClaim.userId.in_(
                db.query("id").from_statement(
                    f"SELECT u.id FROM users u WHERE u.email = '{customer_email}'"
                )
            )
        ).order_by(MerchantClaim.createdAt.desc()).first()

        if not claim:
            print(f"[LM] 找不到對應的 MerchantClaim: {customer_email}")
            return None

        # 更新訂單資訊
        claim.lemonsqueezyOrderId = order_id
        claim.paymentStatus = "paid"
        claim.tier = "pro"
        claim.proExpiresAt = datetime.utcnow() + timedelta(days=365)

        db.commit()

        print(f"[LM] ✅ PRO 訂單已激活: claim_id={claim.id}, order_id={order_id}")
        return claim

    @staticmethod
    def handle_order_refunded(
        db: Session,
        order_data: dict
    ) -> Optional[MerchantClaim]:
        """
        處理 order.refunded 事件（退款）

        Args:
            db: 數據庫 session
            order_data: Webhook 事件 data.order

        Returns:
            更新後的 MerchantClaim，或 None
        """
        order_id = order_data.get("id")

        claim = db.query(MerchantClaim).filter(
            MerchantClaim.lemonsqueezyOrderId == order_id
        ).first()

        if not claim:
            print(f"[LM] 找不到對應的退款訂單: {order_id}")
            return None

        # 降級回 basic，清除 PRO 過期日
        claim.paymentStatus = "refunded"
        claim.tier = "basic"
        claim.proExpiresAt = None

        db.commit()

        print(f"[LM] ⚠️ PRO 訂單已退款: claim_id={claim.id}, order_id={order_id}")
        return claim

    @staticmethod
    def get_checkout_url() -> str:
        """取得結帳連結（前端用），自動加上繁體中文語系"""
        url = LemonsqueezyService.CHECKOUT_URL
        if url and "?" not in url:
            url += "?locale=zh-TW"
        elif url and "locale=" not in url:
            url += "&locale=zh-TW"
        return url
