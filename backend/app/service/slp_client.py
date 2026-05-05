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

    body: dict = {
        "referenceId": reference_id,
        "language": language,
        "amount": {"value": amount, "currency": currency},
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
                    "amount": {"value": amount, "currency": currency},
                    "desc": item_desc or pname,
                }
            ],
        },
        "customer": {
            "referenceCustomerId": customer_ref_id or pid,
            "type": "0",
            "personalInfo": personal_info,
        },
        "billing": {
            "personalInfo": personal_info,
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


# ---------- Webhook 驗章 (留待實測) ----------
def _sign_hmac_sha256_sorted_body(body: dict, timestamp: str, request_id: str) -> str:
    payload = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    msg = f"{timestamp}{request_id}{payload}"
    return hmac.new(SLP_SIGN_KEY.encode("utf-8"), msg.encode("utf-8"), hashlib.sha256).hexdigest()


def _sign_hmac_sha256_body_only(body: dict, timestamp: str, request_id: str) -> str:
    payload = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hmac.new(SLP_SIGN_KEY.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()


_SIGN_ALGOS = {
    "hmac_sha256_sorted_body": _sign_hmac_sha256_sorted_body,
    "hmac_sha256_body_only": _sign_hmac_sha256_body_only,
}


def verify_webhook_sign(raw_body: bytes, headers: dict) -> bool:
    """
    Webhook 驗章。第一次收到 webhook 時把 raw_body + headers 完整 log 出來，
    再依 SLP 實際送過來的格式調整這個函式。
    現階段先放寬: 若沒有 sign header 就接受 (測試期), 之後再強制驗。
    """
    sign = headers.get("sign") or headers.get("x-shopline-signature")
    if not sign:
        logger.warning("webhook 缺 sign header (測試期暫接受). headers=%s", list(headers.keys()))
        return True  # 測試期; production 強化前改回 False

    timestamp = headers.get("timestamp") or ""
    request_id = headers.get("requestid") or headers.get("requestid".lower()) or ""
    try:
        body_dict = json.loads(raw_body.decode("utf-8"))
    except Exception:
        logger.warning("webhook body 非 JSON")
        return False

    fn = _SIGN_ALGOS.get(SLP_SIGN_ALGO)
    if not fn:
        logger.warning("未知 SLP_SIGN_ALGO=%s", SLP_SIGN_ALGO)
        return False
    expected = fn(body_dict, timestamp, request_id)
    ok = hmac.compare_digest(expected, sign)
    if not ok:
        logger.warning("webhook 簽章不符 expected=%s got=%s algo=%s", expected[:8], sign[:8], SLP_SIGN_ALGO)
    return ok
