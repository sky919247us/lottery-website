"""
Webhook 路由
處理 Lemonsqueezy 支付回調
"""

from fastapi import APIRouter, Request, HTTPException, Depends
from sqlalchemy.orm import Session

from app.model.database import get_db
from app.service.lemonsqueezy import LemonsqueezyService

router = APIRouter(prefix="/api/webhooks", tags=["Webhooks"])


@router.post("/lemonsqueezy")
async def handle_lemonsqueezy_webhook(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Lemonsqueezy Webhook 端點
    接收 order_created, order_refunded 等事件
    """
    # 取得原始 body（用於簽名驗證）
    payload = await request.body()

    # 驗證簽名
    signature = request.headers.get("X-Signature", "")
    if not LemonsqueezyService.verify_webhook_signature(payload, signature):
        raise HTTPException(status_code=401, detail="Invalid signature")

    # 解析 JSON
    try:
        data = await request.json()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {str(e)}")

    # Lemonsqueezy 格式: { meta: { event_name, custom_data }, data: { id, type, attributes } }
    meta = data.get("meta", {})
    event_name = meta.get("event_name", "")
    event_data = data.get("data", {})

    print(f"[Webhook] 收到 Lemonsqueezy 事件: {event_name}")
    print(f"[Webhook] meta: {meta}")
    print(f"[Webhook] data.id: {event_data.get('id')}, data.type: {event_data.get('type')}")

    try:
        if event_name == "order_created":
            result = LemonsqueezyService.handle_order_created(db, event_data, meta)
            if result:
                return {"status": "ok", "message": f"PRO activated for claim {result.id}"}
            return {"status": "ok", "message": "Order received but no matching claim found"}

        elif event_name == "order_refunded":
            result = LemonsqueezyService.handle_order_refunded(db, event_data)
            if result:
                return {"status": "ok", "message": f"PRO revoked for claim {result.id}"}
            return {"status": "ok", "message": "Refund received but no matching claim found"}

        else:
            print(f"[Webhook] 未處理的事件類型: {event_name}")
            return {"status": "ok", "message": f"Event {event_name} ignored"}

    except Exception as e:
        print(f"[Webhook] ❌ 處理失敗: {str(e)}")
        import traceback
        traceback.print_exc()
        # 回傳 200 讓 Lemonsqueezy 不重試
        return {"status": "error", "message": str(e)}
