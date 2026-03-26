"""
Lemonsqueezy 支付集成服務
處理 PRO 商家年費付款、Webhook、訂單驗證
"""

import os
import hmac
import hashlib
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session
from app.model.merchant import MerchantClaim
from app.model.retailer import Retailer


class LemonsqueezyService:
    """Lemonsqueezy 支付服務"""

    PRODUCT_ID = os.getenv("LEMONSQUEEZY_PRODUCT_ID", "919326")
    CHECKOUT_URL = os.getenv(
        "LEMONSQUEEZY_CHECKOUT_URL",
        "https://i168.lemonsqueezy.com/checkout/buy/5ab4ec1f-a4c8-4055-9ca4-51b06610e861",
    )
    SIGNING_SECRET = os.getenv("LEMONSQUEEZY_SIGNING_SECRET", "")

    @staticmethod
    def verify_webhook_signature(payload: bytes, signature: str) -> bool:
        """
        驗證 Webhook 簽名（使用 X-Signature header）
        """
        if not LemonsqueezyService.SIGNING_SECRET:
            # 未設定 secret，先跳過驗證（開發/測試模式）
            print("[LM] ⚠️ 未設定 SIGNING_SECRET，跳過簽名驗證")
            return True

        expected = hmac.new(
            LemonsqueezyService.SIGNING_SECRET.encode(),
            payload,
            hashlib.sha256,
        ).hexdigest()

        return hmac.compare_digest(signature, expected)

    @staticmethod
    def get_checkout_url_with_claim(claim_id: int) -> str:
        """
        產生帶有 claim_id 的結帳連結
        Lemonsqueezy 支援 checkout[custom][key]=value 格式傳遞自訂資料
        """
        base = LemonsqueezyService.CHECKOUT_URL
        if not base:
            return ""
        sep = "&" if "?" in base else "?"
        return f"{base}{sep}checkout[custom][claim_id]={claim_id}"

    @staticmethod
    def get_checkout_url() -> str:
        """取得基本結帳連結（前端用）"""
        return LemonsqueezyService.CHECKOUT_URL

    @staticmethod
    def handle_order_created(
        db: Session,
        event_data: dict,
        meta: dict,
    ) -> Optional[MerchantClaim]:
        """
        處理 order_created 事件

        Lemonsqueezy webhook payload 格式:
        {
            "meta": { "event_name": "order_created", "custom_data": { "claim_id": "5" } },
            "data": {
                "id": "123",
                "type": "orders",
                "attributes": { "status": "paid", "user_email": "...", ... }
            }
        }
        """
        order_id = str(event_data.get("id", ""))
        attributes = event_data.get("attributes", {})
        status = attributes.get("status", "")

        print(f"[LM] order_created: order_id={order_id}, status={status}")

        # 只處理已付款的訂單
        if status != "paid":
            print(f"[LM] 訂單狀態非 paid，略過: {status}")
            return None

        # 用 custom_data 中的 claim_id 查找對應店家
        custom_data = meta.get("custom_data") or {}
        claim_id = custom_data.get("claim_id")

        if not claim_id:
            print(f"[LM] ❌ webhook 缺少 claim_id，無法識別店家")
            return None

        claim = db.query(MerchantClaim).filter(
            MerchantClaim.id == int(claim_id)
        ).first()
        print(f"[LM] 透過 claim_id={claim_id} 查找: {'找到' if claim else '未找到'}")

        if not claim:
            print(f"[LM] ❌ 找不到對應的 MerchantClaim: claim_id={claim_id}")
            return None

        if claim.status != "approved":
            print(f"[LM] ❌ claim 狀態非 approved: {claim.status}")
            return None

        # 更新為 PRO
        claim.lemonsqueezyOrderId = order_id
        claim.paymentStatus = "paid"
        claim.tier = "pro"
        claim.proExpiresAt = datetime.utcnow() + timedelta(days=365)

        # 同步更新 Retailer 的 merchantTier
        retailer = db.query(Retailer).filter(Retailer.id == claim.retailerId).first()
        if retailer:
            retailer.merchantTier = "pro"
            retailer.tierExpireAt = claim.proExpiresAt

        db.commit()

        print(f"[LM] ✅ PRO 已激活: claim_id={claim.id}, retailer_id={claim.retailerId}, order_id={order_id}, 到期={claim.proExpiresAt}")
        return claim

    @staticmethod
    def handle_order_refunded(
        db: Session,
        event_data: dict,
    ) -> Optional[MerchantClaim]:
        """
        處理 order_refunded 事件（退款）
        """
        order_id = str(event_data.get("id", ""))

        claim = db.query(MerchantClaim).filter(
            MerchantClaim.lemonsqueezyOrderId == order_id
        ).first()

        if not claim:
            print(f"[LM] ❌ 找不到對應的退款訂單: {order_id}")
            return None

        # 降級回 basic
        claim.paymentStatus = "refunded"
        claim.tier = "basic"
        claim.proExpiresAt = None

        # 同步更新 Retailer
        retailer = db.query(Retailer).filter(Retailer.id == claim.retailerId).first()
        if retailer:
            retailer.merchantTier = "basic"
            retailer.tierExpireAt = None

        db.commit()

        print(f"[LM] ⚠️ PRO 已退款降級: claim_id={claim.id}, retailer_id={claim.retailerId}, order_id={order_id}")
        return claim
