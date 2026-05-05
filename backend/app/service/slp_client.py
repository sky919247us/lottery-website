"""
SHOPLINE Payments (SLP) API client - 導轉式 (Redirect Session)

依官方 PHP 範例校準:
- Server API 不需 HMAC 簽章，只用 merchantId + apiKey + requestId
- allowPaymentMethodList 為 PascalCase enum
- amount.value 單位 = 元 (整數)
- 必填: order.products / customer.personalInfo / client.ip / billing

Webhook 驗章預留 verify_webhook_sign 仍保留 HMAC 候選邏輯，
等收到第一筆 webhook 後再依實際 header / 演算法調整。
"""

import os
import time
import json
import hmac
import uuid
import hashlib
import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

# ---------- 環境變數 ----------
SLP_MERCHANT_ID = os.getenv("SLP_MERCHANT_ID", "")
SLP_API_KEY = os.getenv("SLP_API_KEY", "")
SLP_SIGN_KEY = os.getenv("SLP_SIGN_KEY", "")
SLP_BASE_URL = os.getenv("SLP_BASE_URL", "https://api.shoplinepayments.com")
# webhook 簽章演算法 (待實測確認)
SLP_SIGN_ALGO = os.getenv("SLP_SIGN_ALGO", "hmac_sha256_sorted_body")


# ---------- API 呼叫 ----------
def _build_headers() -> dict:
    return {
        "merchantId": SLP_MERCHANT_ID,
        "apiKey": SLP_API_KEY,
        "requestId": str(uuid.uuid4()),
        "Content-Type": "application/json",
    }


def _post(path: str, body: dict) -> dict:
    if not (SLP_MERCHANT_ID and SLP_API_KEY):
        raise RuntimeError("SLP_MERCHANT_ID / SLP_API_KEY 環境變數未設定")
    url = f"{SLP_BASE_URL.rstrip('/')}{path}"
    headers = _build_headers()
    logger.info("SLP POST %s requestId=%s", path, headers["requestId"])
    with httpx.Client(timeout=30.0) as cli:
        resp = cli.post(url, json=body, headers=headers)
        logger.info("SLP %s -> %s", path, resp.status_code)
        try:
            data = resp.json()
        except Exception:
            data = {"raw": resp.text}
        if resp.status_code >= 400:
            raise RuntimeError(f"SLP API {path} 失敗 [{resp.status_code}]: {data}")
        return data


def create_checkout_session(
    *,
    reference_id: str,
    amount: int,
    currency: str = "TWD",
    return_url: str,
    customer_email: Optional[str] = None,
    customer_ref_id: Optional[str] = None,
    customer_first_name: str = "",
    customer_last_name: str = "",
    customer_phone: str = "",
    item_id: str = "",
    item_name: str = "",
    item_desc: str = "",
    client_ip: Optional[str] = None,
    expire_seconds: int = 600,
    language: str = "zh-Hant",
) -> dict:
    """
    建立結帳 session。回傳含 sessionId / sessionUrl / status / amount 等欄位。
    """
    # SLP amount.value 單位是「分」(最小單位 ×100)
    # 即使 TWD 沒小數，SLP 仍要求 cents (1680 元 → 168000)
    amount_minor = int(amount) * 100
    safe_ip = client_ip or "0.0.0.0"
    safe_email = customer_email or "no-reply@i168.win"
    safe_first = customer_first_name or "User"
    safe_last = customer_last_name or "i168"
    safe_phone = customer_phone or "+886900000000"
    pid = item_id or reference_id
    pname = item_name or item_desc or "Subscription"

    personal_info = {
        "firstName": safe_first,
        "lastName": safe_last,
        "email": safe_email,
        "phone": safe_phone,
    }
    # 數位商品也需給一組 address (SLP 必填)，用商家統一地址
    address = {
        "countryCode": "TW",
        "stateCode": "",
        "state": "",
        "city": "台北市",
        "district": "中正區",
        "street": "重慶南路一段122號",
        "postcode": "100",
    }

    body: dict = {
        "referenceId": reference_id,
        "language": language,
        "amount": {"value": amount_minor, "currency": currency},
        "expireTime": expire_seconds,
        "returnUrl": return_url,
        "mode": "regular",
        "allowPaymentMethodList": ["CreditCard", "ApplePay"],
        "paymentMethodOptions": {
            "CreditCard": {"installmentCounts": ["0"]},
        },
        "order": {
            "products": [
                {
                    "id": pid,
                    "name": pname,
                    "quantity": 1,
                    "amount": {"value": amount_minor, "currency": currency},
                    "desc": item_desc or pname,
                }
            ],
            "shipping": {
                "shippingMethod": "數位",
                "carrier": "電子交付",
                "personalInfo": personal_info,
                "address": address,
            },
        },
        "customer": {
            "referenceCustomerId": customer_ref_id or pid,
            "type": "0",
            "personalInfo": personal_info,
        },
        "billing": {
            "personalInfo": personal_info,
            "address": address,
        },
        "client": {"ip": safe_ip},
    }
    return _post("/api/v1/trade/sessions/create", body)


def query_checkout_session(session_id: str) -> dict:
    return _post("/api/v1/trade/sessions/query", {"sessionId": session_id})


def create_refund(*, reference_id: str, original_reference_id: str, amount: int, reason: str = "") -> dict:
    return _post(
        "/api/v1/trade/refund/create",
        {
            "referenceId": reference_id,
            "originalReferenceId": original_reference_id,
            "amount": {"value": amount, "currency": "TWD"},
            "reason": reason,
        },
    )


# ---------- Webhook 驗章 (已透過 sign_solver 驗證) ----------
# SLP webhook 簽章規則:
#   message = f"{timestamp}.".encode() + raw_body_bytes
#   sign    = HMAC-SHA256(SLP_SIGN_KEY 字串, message).hex()
def verify_webhook_sign(raw_body: bytes, headers: dict) -> bool:
    sign = headers.get("sign")
    timestamp = headers.get("timestamp")
    if not (sign and timestamp):
        logger.warning("webhook 缺 sign 或 timestamp header")
        return False

    msg = f"{timestamp}.".encode("utf-8") + raw_body
    expected = hmac.new(SLP_SIGN_KEY.encode("utf-8"), msg, hashlib.sha256).hexdigest()
    ok = hmac.compare_digest(expected, sign)
    if not ok:
        logger.warning("webhook 簽章不符 expected=%s got=%s", expected[:8], sign[:8])
    return ok
