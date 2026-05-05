"""
SHOPLINE Payments (SLP) API client
- 導轉式 (Redirect Session) 串接
- 簽章演算法寫成可切換 (HMAC-SHA256 字典序 hex 為預設候選)，
  等 sandbox 實測確認後固定為單一實作。
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
SLP_SIGN_ALGO = os.getenv("SLP_SIGN_ALGO", "hmac_sha256_sorted_body")

# ---------- 簽章 ----------
def _sign_hmac_sha256_sorted_body(body: dict, timestamp: str, request_id: str) -> str:
    """
    候選 1 (預設):
      message = method + path + timestamp + requestId + sorted(body json)
      HMAC-SHA256(signKey, message) -> hex lowercase
    Sandbox 實測後若不對，改試其他候選。
    """
    payload = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    message = f"{timestamp}{request_id}{payload}"
    return hmac.new(
        SLP_SIGN_KEY.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def _sign_hmac_sha256_concat_kv(body: dict, timestamp: str, request_id: str) -> str:
    """
    候選 2:
      message = key1=val1&key2=val2... (字典序) + &timestamp=... + &requestId=...
    """
    items = sorted(body.items()) + [("requestId", request_id), ("timestamp", timestamp)]
    message = "&".join(f"{k}={v}" for k, v in items if v is not None)
    return hmac.new(
        SLP_SIGN_KEY.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


_SIGN_ALGOS = {
    "hmac_sha256_sorted_body": _sign_hmac_sha256_sorted_body,
    "hmac_sha256_concat_kv": _sign_hmac_sha256_concat_kv,
}


def compute_sign(body: dict, timestamp: str, request_id: str) -> str:
    fn = _SIGN_ALGOS.get(SLP_SIGN_ALGO)
    if not fn:
        raise ValueError(f"未知簽章演算法 SLP_SIGN_ALGO={SLP_SIGN_ALGO}")
    return fn(body, timestamp, request_id)


def verify_webhook_sign(raw_body: bytes, headers: dict) -> bool:
    """
    Webhook 驗章。SLP 推送 webhook 時應在 header 帶上 sign / timestamp / requestId。
    Sandbox 實測後依實際 header 名稱與演算法調整。
    """
    sign = headers.get("sign") or headers.get("Sign")
    timestamp = headers.get("timestamp") or headers.get("Timestamp")
    request_id = headers.get("requestid") or headers.get("requestId") or headers.get("RequestId") or ""
    if not (sign and timestamp):
        logger.warning("webhook 缺少 sign / timestamp header")
        return False
    try:
        body_dict = json.loads(raw_body.decode("utf-8"))
    except Exception:
        logger.warning("webhook body 非 JSON")
        return False
    expected = compute_sign(body_dict, timestamp, request_id)
    ok = hmac.compare_digest(expected, sign)
    if not ok:
        logger.warning("webhook 簽章不符 expected=%s got=%s", expected[:8], sign[:8])
    return ok


# ---------- API 呼叫 ----------
def _build_headers(body: dict) -> dict:
    timestamp = str(int(time.time()))
    request_id = str(uuid.uuid4())
    sign = compute_sign(body, timestamp, request_id)
    return {
        "merchantId": SLP_MERCHANT_ID,
        "apiKey": SLP_API_KEY,
        "requestId": request_id,
        "timestamp": timestamp,
        "sign": sign,
        "Content-Type": "application/json",
    }


def _post(path: str, body: dict) -> dict:
    if not (SLP_MERCHANT_ID and SLP_API_KEY and SLP_SIGN_KEY):
        raise RuntimeError("SLP_MERCHANT_ID / SLP_API_KEY / SLP_SIGN_KEY 環境變數未設定")
    url = f"{SLP_BASE_URL.rstrip('/')}{path}"
    headers = _build_headers(body)
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
    item_desc: str = "",
    client_ip: Optional[str] = None,
) -> dict:
    """
    建立結帳 session。
    回傳含 sessionId、sessionUrl、status 等欄位。
    前端拿 sessionUrl 做導轉。
    """
    body: dict = {
        "referenceId": reference_id,
        "mode": "regular",
        "amount": {"value": amount, "currency": currency},
        "returnUrl": return_url,
        "allowPaymentMethodList": ["CREDIT_CARD"],
    }
    if item_desc:
        body["order"] = {"products": [{"name": item_desc, "amount": amount, "quantity": 1}]}
    if customer_ref_id or customer_email:
        body["customer"] = {
            "referenceCustomerId": customer_ref_id or "",
            "personalInfo": ({"email": customer_email} if customer_email else {}),
        }
    if client_ip:
        body["client"] = {"ip": client_ip}
    return _post("/api/v1/trade/sessions/create", body)


def query_checkout_session(session_id: str) -> dict:
    return _post("/api/v1/trade/sessions/query", {"sessionId": session_id})


def create_refund(*, reference_id: str, original_reference_id: str, amount: int, reason: str = "") -> dict:
    return _post(
        "/api/trade/refund/",
        {
            "referenceId": reference_id,
            "originalReferenceId": original_reference_id,
            "amount": {"value": amount, "currency": "TWD"},
            "reason": reason,
        },
    )
