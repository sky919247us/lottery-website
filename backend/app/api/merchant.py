"""
店家管理 API 路由
認領、營業設定、設施標籤、臨時公告
"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.model.database import get_db
from app.model.retailer import Retailer
from app.model.user import User
from app.model.merchant import MerchantClaim, MerchantAnnouncement
from app.schema.user import (
    MerchantClaimCreate, MerchantClaimResponse,
    MerchantAnnouncementCreate, RetailerTagsUpdate
)
from app.api.user import add_karma
from app.service.lemonsqueezy import LemonsqueezyService
from fastapi import Query, UploadFile, File
from app.service.r2_service import upload_image

router = APIRouter(prefix="/api/merchant", tags=["店家管理"])


@router.post("/claim", response_model=MerchantClaimResponse, status_code=201)
def submit_claim(data: MerchantClaimCreate, db: Session = Depends(get_db)):
    """提交店家認領申請"""
    # 驗證使用者
    user = db.query(User).filter(User.id == data.userId).first()
    if not user:
        raise HTTPException(status_code=404, detail="使用者不存在")

    # 驗證店家
    retailer = db.query(Retailer).filter(Retailer.id == data.retailerId).first()
    if not retailer:
        raise HTTPException(status_code=404, detail="經銷商不存在")

    # 檢查是否已被認領
    existing = db.query(MerchantClaim).filter(
        MerchantClaim.retailerId == data.retailerId,
        MerchantClaim.status == "approved",
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="此店家已被認領")

    # 檢查是否有待審核申請
    pending = db.query(MerchantClaim).filter(
        MerchantClaim.retailerId == data.retailerId,
        MerchantClaim.status == "pending",
    ).first()
    if pending:
        raise HTTPException(status_code=400, detail="此店家已有待審核的認領申請")

    claim = MerchantClaim(
        retailerId=data.retailerId,
        userId=data.userId,
        contactName=data.contactName,
        contactPhone=data.contactPhone,
        licenseUrl=data.licenseUrl,
        idCardUrl=data.idCardUrl,
    )
    db.add(claim)
    db.commit()
    db.refresh(claim)
    return claim





@router.put("/{retailer_id}/tags")
def update_tags(
    retailer_id: int,
    data: RetailerTagsUpdate,
    db: Session = Depends(get_db),
):
    """更新店家設施標籤（需已認領）"""
    retailer = db.query(Retailer).filter(Retailer.id == retailer_id).first()
    if not retailer:
        raise HTTPException(status_code=404, detail="經銷商不存在")

    # 更新所有標籤
    for field in data.model_dump():
        setattr(retailer, field, getattr(data, field))

    db.commit()
    return {"status": "ok", "message": "設施標籤已更新"}


@router.put("/{retailer_id}/status")
def update_business_status(
    retailer_id: int,
    is_active: bool = True,
    db: Session = Depends(get_db),
):
    """更新營業狀態"""
    retailer = db.query(Retailer).filter(Retailer.id == retailer_id).first()
    if not retailer:
        raise HTTPException(status_code=404, detail="經銷商不存在")

    retailer.isActive = is_active
    db.commit()
    return {"status": "ok", "isActive": is_active}


@router.post("/{retailer_id}/announcement")
def create_announcement(
    retailer_id: int,
    data: MerchantAnnouncementCreate,
    db: Session = Depends(get_db),
):
    """發佈臨時公告"""
    # 找到認領
    claim = db.query(MerchantClaim).filter(
        MerchantClaim.retailerId == retailer_id,
        MerchantClaim.status == "approved",
    ).first()
    if not claim:
        raise HTTPException(status_code=403, detail="此店家尚未認領或未核准")

    # 更新經銷商公告欄位
    retailer = db.query(Retailer).filter(Retailer.id == retailer_id).first()
    if retailer:
        retailer.announcement = data.content

    announcement = MerchantAnnouncement(
        claimId=claim.id,
        content=data.content,
    )
    db.add(announcement)
    db.commit()
    return {"status": "ok", "message": "公告已發佈"}


# ========== PRO 商家升級相關 API ==========

@router.get("/retailers/{retailer_id}/claim")
def get_retailer_claim(retailer_id: int, db: Session = Depends(get_db)):
    """取得零售商的認領資訊（若存在）"""
    claim = db.query(MerchantClaim).filter(
        MerchantClaim.retailerId == retailer_id,
    ).order_by(MerchantClaim.createdAt.desc()).first()

    if not claim:
        return {"id": None}

    return {
        "id": claim.id,
        "status": claim.status,
        "tier": claim.tier,
    }


@router.get("/claim/{claim_id}/status")
def get_claim_status(claim_id: int, db: Session = Depends(get_db)):
    """取得認領申請狀態"""
    claim = db.query(MerchantClaim).filter(MerchantClaim.id == claim_id).first()
    if not claim:
        raise HTTPException(status_code=404, detail="申請不存在")

    return {
        "id": claim.id,
        "status": claim.status,  # pending / approved / rejected
        "tier": claim.tier,      # basic / pro
        "verificationComplete": bool(claim.licenseUrl and claim.idCardUrl),
        "paymentStatus": claim.paymentStatus,  # pending / paid
        "proExpiresAt": claim.proExpiresAt,
    }


@router.get("/claim/{claim_id}/checkout-url")
def get_checkout_url(claim_id: int, db: Session = Depends(get_db)):
    """
    取得 Lemonsqueezy 結帳連結
    前置條件：申請已核准
    """
    claim = db.query(MerchantClaim).filter(MerchantClaim.id == claim_id).first()
    if not claim:
        raise HTTPException(status_code=404, detail="申請不存在")

    # 驗證申請已核准
    if claim.status != "approved":
        raise HTTPException(status_code=403, detail="申請尚未核准")

    # 返回結帳 URL（帶 claim_id）
    checkout_url = LemonsqueezyService.get_checkout_url_with_claim(claim_id)
    if not checkout_url:
        raise HTTPException(status_code=500, detail="支付系統未設定")

    return {
        "checkoutUrl": checkout_url,
        "productId": LemonsqueezyService.PRODUCT_ID,
        "price": "NT$1,680",
    }


@router.post("/claim/{claim_id}/upload-verification")
async def upload_verification_document(
    claim_id: int,
    doc_type: str = Query(..., description="license 或 idcard"),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """
    上傳驗證文件（營業執照或身份證）

    Args:
        claim_id: MerchantClaim ID
        doc_type: 文件類型 (license / idcard)
        file: 上傳的檔案
    """
    claim = db.query(MerchantClaim).filter(MerchantClaim.id == claim_id).first()
    if not claim:
        raise HTTPException(status_code=404, detail="申請不存在")

    # 驗證文件類型
    if doc_type not in ["license", "idcard"]:
        raise HTTPException(status_code=400, detail="無效的文件類型")

    try:
        # 讀取檔案內容
        file_data = await file.read()

        # 使用 r2_service 上傳（category 用 "verification" 區別商家文件）
        public_url, r2_key = upload_image(
            file_data=file_data,
            retailer_id=claim.retailerId,
            category=f"verification_{doc_type}",
        )

        # 保存 URL 到 claim
        if doc_type == "license":
            claim.licenseUrl = public_url
        else:  # idcard
            claim.idCardUrl = public_url

        db.commit()

        return {
            "status": "ok",
            "docType": doc_type,
            "fileUrl": public_url,
            "message": "文件已上傳",
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"上傳失敗: {str(e)}")
