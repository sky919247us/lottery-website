"""
SHOPLINE Payments (SLP) 串接端點
- POST /api/payment/slp/create   建立結帳 session 回傳 sessionUrl
- POST /api/payment/slp/webhook  接 SLP 主動推送的事件 (驗章 + 升級店家)

升級對象: Retailer (店家)
方案 PRO_YEARLY 1,680 / 365 天
"""

import os
import logging
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.model.database import get_db
from app.model.retailer import Retailer
from app.service import slp_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/payment/slp", tags=["金流支付-SHOPLINE"])

# ---------- 方案表 ----------
PLAN_TABLE = {
    "PRO_YEARLY": {"amount": 1680, "days": 365, "desc": "刮刮研究室 PRO 專業版 (年費)"},
    # 未來擴充: PRO_MONTHLY 等
}


class SLPCheckoutRequest(BaseModel):
    retailer_id: int
    plan: str = "PRO_YEARLY"


@router.post("/create")
def create_slp_checkout(req: SLPCheckoutRequest, request: Request, db: Session = Depends(get_db)):
    """
    建立 SLP 結帳 session 並回傳 sessionUrl 供前端導轉。
    """
    plan = PLAN_TABLE.get(req.plan)
    if not plan:
        raise HTTPException(status_code=400, detail=f"未知方案: {req.plan}")

    retailer = db.query(Retailer).filter(Retailer.id == req.retailer_id).first()
    if not retailer:
        raise HTTPException(status_code=404, detail="找不到此彩券行")

    reference_id = f"PRO_{retailer.id}_{int(datetime.now().timestamp())}"
    frontend_url = os.getenv("FRONTEND_URL", "http://localhost:5173")
    return_url = f"{frontend_url}/admin/merchant/dashboard?payment=slp&ref={reference_id}"

    try:
        result = slp_client.create_checkout_session(
            reference_id=reference_id,
            amount=plan["amount"],
            return_url=return_url,
            customer_ref_id=str(retailer.id),
            item_desc=plan["desc"],
            client_ip=request.client.host if request.client else None,
        )
    except Exception as e:
        logger.exception("SLP create session 失敗")
        raise HTTPException(status_code=502, detail=f"金流建立失敗: {e}")

    session_url = result.get("sessionUrl") or result.get("data", {}).get("sessionUrl")
    if not session_url:
        raise HTTPException(status_code=502, detail=f"SLP 回應缺少 sessionUrl: {result}")

    return {
        "status": "success",
        "data": {
            "referenceId": reference_id,
            "sessionId": result.get("sessionId") or result.get("data", {}).get("sessionId"),
            "sessionUrl": session_url,
            "amount": plan["amount"],
            "plan": req.plan,
        },
    }


@router.post("/webhook")
async def slp_webhook(request: Request, db: Session = Depends(get_db)):
    """
    SLP 推送事件 webhook。
    必須驗章，且做冪等處理 (同 referenceId 不重複升級)。
    """
    raw = await request.body()
    headers = {k.lower(): v for k, v in request.headers.items()}

    if not slp_client.verify_webhook_sign(raw, headers):
        logger.warning("SLP webhook 驗章失敗")
        return Response(content="INVALID_SIGN", media_type="text/plain", status_code=401)

    try:
        import json
        payload = json.loads(raw.decode("utf-8"))
    except Exception:
        return Response(content="BAD_JSON", media_type="text/plain", status_code=400)

    event_type = payload.get("eventType") or payload.get("type") or ""
    data = payload.get("data") or payload
    reference_id = data.get("referenceId") or ""
    status = data.get("status") or ""

    logger.info("SLP webhook event=%s ref=%s status=%s", event_type, reference_id, status)

    # 僅處理付款成功事件
    is_success = (
        event_type in ("session.succeeded", "trade.succeeded")
        or status in ("SUCCEEDED", "SUCCESS", "PAID")
    )
    if not is_success:
        return Response(content="OK", media_type="text/plain")

    # 從 referenceId 解出 retailer_id (格式: PRO_{retailer_id}_{ts})
    if not reference_id.startswith("PRO_"):
        logger.warning("非 PRO 格式 referenceId: %s", reference_id)
        return Response(content="OK", media_type="text/plain")

    parts = reference_id.split("_")
    if len(parts) < 3:
        return Response(content="OK", media_type="text/plain")
    try:
        retailer_id = int(parts[1])
    except ValueError:
        return Response(content="OK", media_type="text/plain")

    retailer = db.query(Retailer).filter(Retailer.id == retailer_id).first()
    if not retailer:
        logger.warning("找不到 retailer_id=%s", retailer_id)
        return Response(content="OK", media_type="text/plain")

    # 冪等檢查: 若已升級且到期日 > 此次預期+延長後的時間 - 60s，視為已處理
    # (簡單做法: 檢查 reference_id 是否處理過; 暫存於 retailer 一個欄位或新 log table)
    # 這版先用「同 reference 在 5 分鐘內重送 → 略過」的時間冪等
    last_paid = getattr(retailer, "lastPaymentRef", None)
    if last_paid == reference_id:
        logger.info("referenceId %s 已處理過，跳過", reference_id)
        return Response(content="OK", media_type="text/plain")

    # 推算延長天數
    amount = (data.get("amount") or {}).get("value") or 0
    days = 365  # 目前只有 PRO_YEARLY
    for plan in PLAN_TABLE.values():
        if plan["amount"] == amount:
            days = plan["days"]
            break

    now = datetime.now()
    current_expire = getattr(retailer, "tierExpireAt", None) or now
    if current_expire < now:
        current_expire = now
    retailer.merchantTier = "pro"
    retailer.tierExpireAt = current_expire + timedelta(days=days)
    if hasattr(retailer, "lastPaymentRef"):
        retailer.lastPaymentRef = reference_id
    db.commit()

    logger.info(
        "店家 %s 升級 PRO 成功，到期日延長至 %s",
        retailer_id, retailer.tierExpireAt.isoformat(),
    )
    return Response(content="OK", media_type="text/plain")
