import os
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.model.database import get_db, SessionLocal
from app.model.admin import AdminUser
from app.model.retailer import Retailer
from app.service.payment_service import create_mpg_data, decrypt_trade_info

router = APIRouter(prefix="/api/payment", tags=["金流支付"])

class PaymentCreateRequest(BaseModel):
    retailer_id: int
    plan: str = "PRO_MONTHLY" # PRO_MONTHLY 或 PRO_YEARLY
    amount: int

@router.post("/create")
def create_payment(req: PaymentCreateRequest, db: Session = Depends(get_db)):
    """
    產生前端表單所需之金流參數 (TradeInfo, TradeSha)
    """
    retailer = db.query(Retailer).filter(Retailer.id == req.retailer_id).first()
    if not retailer:
        raise HTTPException(status_code=404, detail="找不到此彩券行")
    
    # 產生訂單編號
    order_no = f"PRO_{req.retailer_id}_{int(datetime.now().timestamp())}"
    
    # 假設 ReturnURL 和 NotifyURL 設定在環境變數或是固定路由
    frontend_url = os.getenv("FRONTEND_URL", "http://localhost:5173")
    backend_url = os.getenv("BACKEND_URL", "http://localhost:8000")
    
    return_url = f"{frontend_url}/admin/merchant/dashboard?payment=success"
    notify_url = f"{backend_url}/api/payment/notify"
    
    # 呼叫支付服務產生加密參數
    mpg_data = create_mpg_data(
        order_no=order_no,
        amount=req.amount,
        item_desc=f"升級專業版 ({req.plan})",
        email="merchant@example.com", # TODO: 如果資料庫有聯絡信箱可帶入
        return_url=return_url,
        notify_url=notify_url,
    )
    
    return {"status": "success", "data": mpg_data}

@router.post("/notify")
async def payment_notify(request: Request, db: Session = Depends(get_db)):
    """
    藍新支付背景回傳 Webhook (Content-Type: application/x-www-form-urlencoded)
    依照藍新文件，TradeInfo 會是加密過後的字串。
    """
    form_data = await request.form()
    trade_info_encrypted = form_data.get("TradeInfo")
    
    if not trade_info_encrypted:
        return Response(content="FAIL", media_type="text/plain")
        
    try:
        trade_info = decrypt_trade_info(trade_info_encrypted) # Type is dict or Query String parsed
        # 藍新回傳的 TradeInfo 解出後是 json
        import json
        if isinstance(trade_info, str):
            trade_info = json.loads(trade_info)
            
        status = trade_info.get("Status")
        if status != "SUCCESS":
            return Response(content="FAIL", media_type="text/plain")
            
        result = trade_info.get("Result", {})
        order_no = result.get("MerchantOrderNo", "")
        # 解析訂單編號 (PRO_{retailer_id}_{timestamp})
        if order_no.startswith("PRO_"):
            parts = order_no.split("_")
            if len(parts) >= 2:
                retailer_id = int(parts[1])
                
                # 更新此店家的 merchantTier 為 'pro'，並延長 expirationDate
                retailer = db.query(Retailer).filter(Retailer.id == retailer_id).first()
                if retailer:
                    retailer.merchantTier = "pro"
                    now = datetime.now()
                    
                    # 判斷現有到期日是否還未到，如果未到就累加，否則從今天算起
                    current_expire = getattr(retailer, "tierExpireAt", None)
                    if not current_expire or current_expire < now:
                        current_expire = now
                        
                    # 簡易判斷金額 (如 500=月, 5000=年) (實際專案應設計 Order Table)
                    if result.get("Amt") >= 5000:
                        retailer.tierExpireAt = current_expire + timedelta(days=365)
                    else:
                        retailer.tierExpireAt = current_expire + timedelta(days=31)
                        
                    db.commit()
                    
        return Response(content="SUCCESS", media_type="text/plain")
    except Exception as e:
        print(f"Payment Notify Error: {e}")
        return Response(content="FAIL", media_type="text/plain")
