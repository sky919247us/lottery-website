"""
Webhook 路由
處理 Lemonsqueezy 支付回調
"""

from fastapi import APIRouter, Request, HTTPException, Depends, status
from sqlalchemy.orm import Session

from app.model.database import get_db
from app.service.lemonsqueezy import LemonsqueezyService

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])


@router.post("/lemonsqueezy")
async def handle_lemonsqueezy_webhook(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Lemonsqueezy Webhook 端點
    接收 order.created, order.refunded 等事件
    """
    # 取得請求 body（用於簽名驗證）
    payload = await request.body()

    # 驗證簽名
    signature = request.headers.get("X-Signature", "")
    if not LemonsqueezyService.verify_webhook_signature(payload.decode(), signature):
        raise HTTPException(status_code=401, detail="Invalid signature")

    # 解析 JSON
    try:
        data = await request.json()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {str(e)}")

    event_name = data.get("meta", {}).get("event_name")
    event_data = data.get("data", {})

    print(f"[Webhook] 收到 Lemonsqueezy 事件: {event_name}")

    try:
        if event_name == "order.created":
            # 取得 order 對象（在 data 中）
            order = event_data.get("order")
            if order:
                LemonsqueezyService.handle_order_created(db, order)

        elif event_name == "order.refunded":
            order = event_data.get("order")
            if order:
                LemonsqueezyService.handle_order_refunded(db, order)

        return {"status": "ok"}

    except Exception as e:
        print(f"[Webhook] ❌ 處理失敗: {str(e)}")
        # 不要拋出異常，讓 Lemonsqueezy 知道我們收到了
        return {"status": "error", "message": str(e)}
