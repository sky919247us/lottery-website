"""
SHOPLINE Payments (SLP) 串接端點
- GET  /api/payment/slp/claim/{claim_id}/checkout-url
       提供一鍵結帳連結 (給前端 PlanCard 替代 Lemonsqueezy)
- POST /api/payment/slp/create
       直接以 claim_id + plan 建立 session (供進階呼叫)
- POST /api/payment/slp/webhook
       接 SLP 事件 (驗章 → 升級 / 退款降級)

升級對象: MerchantClaim (同步更新 Retailer.merchantTier / tierExpireAt)
方案 PRO_YEARLY: NT$1,680 / 365 天
"""

import os
import json
import logging
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.model.database import get_db
from app.model.merchant import MerchantClaim
from app.model.retailer import Retailer
from app.service import slp_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/payment/slp", tags=["金流支付-SHOPLINE"])

# ---------- 方案表 ----------
PLAN_TABLE = {
    "PRO_YEARLY": {"amount": 1680, "days": 365, "desc": "刮刮研究室 PRO 專業版 (年費)"},
}


def _make_reference_id(claim_id: int) -> str:
    return f"PRO_CLAIM_{claim_id}_{int(datetime.now().timestamp())}"


def _parse_claim_id(reference_id: str) -> int | None:
    if not reference_id.startswith("PRO_CLAIM_"):
        return None
    parts = reference_id.split("_")
    if len(parts) < 4:
        return None
    try:
        return int(parts[2])
    except ValueError:
        return None


def _create_session_for_claim(
    *, claim: MerchantClaim, plan_code: str, request: Request
) -> dict:
    plan = PLAN_TABLE.get(plan_code)
    if not plan:
        raise HTTPException(status_code=400, detail=f"未知方案: {plan_code}")

    reference_id = _make_reference_id(claim.id)
    frontend_url = os.getenv("FRONTEND_URL", "http://localhost:5173")
    return_url = f"{frontend_url}/admin/merchant/dashboard?payment=slp&ref={reference_id}"

    # 從 claim / retailer 撈使用者資訊 (盡量帶滿，SLP 必填欄位多)
    retailer = None
    try:
        from app.model.retailer import Retailer
        retailer = db.query(Retailer).filter(Retailer.id == claim.retailerId).first()
    except Exception:
        pass

    customer_email = getattr(claim, "contactEmail", None) or getattr(retailer, "email", None) or "no-reply@i168.win"
    customer_phone = getattr(claim, "contactPhone", None) or getattr(retailer, "phone", None) or "+886900000000"
    customer_name = getattr(claim, "contactName", "") or ""
    if customer_name:
        # 簡單拆姓名 (繁中第一字當姓)
        first_name = customer_name[1:] if len(customer_name) > 1 else customer_name
        last_name = customer_name[0]
    else:
        first_name, last_name = "User", "i168"

    # 取得真實 client IP (考慮 Cloudflare / proxy)
    client_ip = (
        request.headers.get("cf-connecting-ip")
        or request.headers.get("x-forwarded-for", "").split(",")[0].strip()
        or (request.client.host if request.client else None)
        or "0.0.0.0"
    )

    try:
        result = slp_client.create_checkout_session(
            reference_id=reference_id,
            amount=plan["amount"],
            return_url=return_url,
            customer_email=customer_email,
            customer_ref_id=str(claim.id),
            customer_first_name=first_name,
            customer_last_name=last_name,
            customer_phone=customer_phone,
            item_id=f"plan_{plan_code.lower()}",
            item_name=plan["desc"],
            item_desc=plan["desc"],
            client_ip=client_ip,
        )
    except Exception as e:
        logger.exception("SLP create session 失敗")
        raise HTTPException(status_code=502, detail=f"金流建立失敗: {e}")

    session_url = result.get("sessionUrl") or result.get("data", {}).get("sessionUrl")
    session_id = result.get("sessionId") or result.get("data", {}).get("sessionId")
    if not session_url:
        raise HTTPException(status_code=502, detail=f"SLP 回應缺少 sessionUrl: {result}")

    return {
        "referenceId": reference_id,
        "sessionId": session_id,
        "sessionUrl": session_url,
        "amount": plan["amount"],
        "plan": plan_code,
    }


# ---------- 端點 1: 給前端一鍵取得結帳連結 ----------
@router.get("/claim/{claim_id}/checkout-url")
def get_slp_checkout_url(claim_id: int, request: Request, db: Session = Depends(get_db)):
    """
    取代 Lemonsqueezy /api/merchant/claim/{id}/checkout-url
    回傳格式相容: { checkoutUrl, price }
    """
    claim = db.query(MerchantClaim).filter(MerchantClaim.id == claim_id).first()
    if not claim:
        raise HTTPException(status_code=404, detail="申請不存在")
    if claim.status != "approved":
        raise HTTPException(status_code=403, detail="申請尚未核准")
    # 不擋 PRO 中再次付款 — 續約會在 webhook 端 MAX(現有到期日, now) + 365 累加
    # 永久 PRO 才擋 (避免無謂消費)
    if claim.proExpiresAt and claim.proExpiresAt.year >= 9999:
        raise HTTPException(status_code=409, detail="本店為永久 PRO，無需付費續約")

    data = _create_session_for_claim(claim=claim, plan_code="PRO_YEARLY", request=request)
    return {
        "checkoutUrl": data["sessionUrl"],
        "sessionId": data["sessionId"],
        "referenceId": data["referenceId"],
        "price": "NT$1,680",
        "provider": "shopline",
    }


# ---------- 端點 2: POST 進階建單 (備用) ----------
class SLPCheckoutRequest(BaseModel):
    claim_id: int
    plan: str = "PRO_YEARLY"


@router.post("/create")
def create_slp_checkout(req: SLPCheckoutRequest, request: Request, db: Session = Depends(get_db)):
    claim = db.query(MerchantClaim).filter(MerchantClaim.id == req.claim_id).first()
    if not claim:
        raise HTTPException(status_code=404, detail="申請不存在")
    data = _create_session_for_claim(claim=claim, plan_code=req.plan, request=request)
    return {"status": "success", "data": data}


# ---------- 端點 3: webhook ----------
@router.post("/webhook")
async def slp_webhook(request: Request, db: Session = Depends(get_db)):
    raw = await request.body()
    headers = {k.lower(): v for k, v in request.headers.items()}

    if not slp_client.verify_webhook_sign(raw, headers):
        logger.warning("SLP webhook 驗章失敗，拒絕事件")
        return Response(content="INVALID_SIGN", media_type="text/plain", status_code=401)

    # 偵錯: refund 事件 body 結構未知，先 dump
    try:
        _peek = json.loads(raw.decode("utf-8"))
        if (_peek.get("type") or "").startswith("trade.refund"):
            logger.info("=" * 60)
            logger.info("REFUND BODY (%d bytes): %s", len(raw), raw.decode("utf-8", errors="replace"))
            logger.info("=" * 60)
    except Exception:
        pass

    try:
        payload = json.loads(raw.decode("utf-8"))
    except Exception:
        return Response(content="BAD_JSON", media_type="text/plain", status_code=400)

    event_type = payload.get("eventType") or payload.get("type") or ""
    data = payload.get("data") or payload
    reference_id = data.get("referenceId") or ""
    status_field = (data.get("status") or "").upper()

    logger.info("SLP webhook event=%s ref=%s status=%s", event_type, reference_id, status_field)

    # 解析 claim_id: 多重 fallback
    # 1. data.referenceId (session.succeeded 才有)
    # 2. data.order.customer.referenceCustomerId (trade.succeeded 才有)
    # ===== 事件分流 =====
    # SLP 對一筆付款會同時送 trade.succeeded + session.succeeded,
    # 為避免重複升級, 規則:
    #   - trade.succeeded → 只把 tradeOrderId 寫入 claim (退款反查用), 不升級
    #   - session.succeeded → 真正升級 / 續約 (依 referenceId)
    #   - trade.refund.succeeded → 用 tradeOrderId 反查 claim 並降級

    # ---- trade.succeeded: 純記錄 tradeOrderId, 不升級 ----
    if event_type == "trade.succeeded":
        order = data.get("order") or {}
        ref_customer = (order.get("customer") or {}).get("referenceCustomerId")
        trade_order_id = data.get("tradeOrderId")
        if not (ref_customer and str(ref_customer).isdigit() and trade_order_id):
            logger.info("trade.succeeded 缺 referenceCustomerId 或 tradeOrderId, 忽略")
            return Response(content="OK", media_type="text/plain")
        cid = int(ref_customer)
        claim = db.query(MerchantClaim).filter(MerchantClaim.id == cid).first()
        if claim:
            if hasattr(claim, "slpTradeOrderId"):
                claim.slpTradeOrderId = str(trade_order_id)
                db.commit()
                logger.info("trade.succeeded 記錄 claim=%s tradeOrderId=%s", cid, trade_order_id)
        return Response(content="OK", media_type="text/plain")

    # ---- session.succeeded: 升級 / 續約 ----
    # 注意: 嚴格只認 event_type, 不可用 status_field 判斷
    # (trade.refund.succeeded 的 status 也是 SUCCEEDED, 會被誤歸類)
    if event_type == "session.succeeded":
        claim_id = _parse_claim_id(reference_id)
        if not claim_id:
            logger.info("session.succeeded 非 PRO_CLAIM 格式 ref=%s, 忽略", reference_id)
            return Response(content="OK", media_type="text/plain")
        claim = db.query(MerchantClaim).filter(MerchantClaim.id == claim_id).first()
        if not claim:
            logger.warning("session.succeeded 找不到 claim_id=%s", claim_id)
            return Response(content="OK", media_type="text/plain")

        # 冪等: 同一筆 referenceId 重送 (SLP webhook retry) -> 跳過
        existing_ref = getattr(claim, "lemonsqueezyOrderId", None)
        if existing_ref == reference_id and claim.tier == "pro":
            logger.info("claim %s 同一 referenceId 已處理過 (%s)，跳過 (idempotent)",
                        claim_id, reference_id)
            return Response(content="OK", media_type="text/plain")

        if claim.status != "approved":
            logger.warning("claim %s status=%s 非 approved，仍接受付款但不變更 tier",
                           claim_id, claim.status)

        now = datetime.utcnow()
        amount_minor = (data.get("amount") or {}).get("value") or 0
        days = 365
        for plan in PLAN_TABLE.values():
            if plan["amount"] * 100 == amount_minor:
                days = plan["days"]
                break

        base = claim.proExpiresAt if (claim.proExpiresAt and claim.proExpiresAt > now) else now
        new_expire = base + timedelta(days=days)
        is_renewal = claim.tier == "pro" and claim.proExpiresAt and claim.proExpiresAt > now

        claim.paymentStatus = "paid"
        claim.tier = "pro"
        claim.proExpiresAt = new_expire
        if hasattr(claim, "lemonsqueezyOrderId"):
            claim.lemonsqueezyOrderId = reference_id

        retailer = db.query(Retailer).filter(Retailer.id == claim.retailerId).first()
        if retailer:
            retailer.merchantTier = "pro"
            retailer.tierExpireAt = new_expire
        db.commit()
        logger.info(
            "[SLP] ✅ PRO %s claim=%s retailer=%s ref=%s 加 %s 天 -> 到期=%s",
            "續約" if is_renewal else "已激活",
            claim_id, claim.retailerId, reference_id, days, new_expire,
        )
        return Response(content="OK", media_type="text/plain")

    # ---- trade.refund.succeeded: 用 tradeOrderId 反查降級 ----
    if event_type == "trade.refund.succeeded":
        trade_order_id = data.get("tradeOrderId")
        if not trade_order_id:
            logger.warning("refund 事件缺 tradeOrderId, 忽略")
            return Response(content="OK", media_type="text/plain")
        claim = db.query(MerchantClaim).filter(
            MerchantClaim.slpTradeOrderId == str(trade_order_id)
        ).first()
        if not claim:
            logger.warning("refund 找不到 claim (slpTradeOrderId=%s), 忽略", trade_order_id)
            return Response(content="OK", media_type="text/plain")

        claim.paymentStatus = "refunded"
        claim.tier = "basic"
        claim.proExpiresAt = None
        retailer = db.query(Retailer).filter(Retailer.id == claim.retailerId).first()
        if retailer:
            retailer.merchantTier = "basic"
            retailer.tierExpireAt = None
        db.commit()
        logger.info("[SLP] ⚠️ PRO 已退款降級 claim=%s tradeOrderId=%s", claim.id, trade_order_id)
        return Response(content="OK", media_type="text/plain")

    # 其他事件 (session.expired / trade.failed / trade.cancelled 等) — 不變更 DB
    return Response(content="OK", media_type="text/plain")
