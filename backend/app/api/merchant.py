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


@router.get("/claims", response_model=list[MerchantClaimResponse])
def get_claims(
    status: str | None = None,
    db: Session = Depends(get_db),
):
    """取得認領申請列表（管理員用）"""
    query = db.query(MerchantClaim)
    if status:
        query = query.filter(MerchantClaim.status == status)
    return query.order_by(MerchantClaim.createdAt.desc()).all()


@router.put("/claims/{claim_id}/approve")
def approve_claim(claim_id: int, db: Session = Depends(get_db)):
    """核准認領（管理員操作）"""
    claim = db.query(MerchantClaim).filter(MerchantClaim.id == claim_id).first()
    if not claim:
        raise HTTPException(status_code=404, detail="認領申請不存在")

    claim.status = "approved"
    claim.approvedAt = datetime.utcnow()

    # 更新經銷商狀態
    retailer = db.query(Retailer).filter(Retailer.id == claim.retailerId).first()
    if retailer:
        retailer.isClaimed = True
        retailer.merchantTier = claim.tier

    db.commit()
    return {"status": "ok", "message": "已核准認領"}


@router.put("/claims/{claim_id}/reject")
def reject_claim(claim_id: int, reason: str = "", db: Session = Depends(get_db)):
    """駁回認領（管理員操作）"""
    claim = db.query(MerchantClaim).filter(MerchantClaim.id == claim_id).first()
    if not claim:
        raise HTTPException(status_code=404, detail="認領申請不存在")

    claim.status = "rejected"
    claim.rejectReason = reason
    db.commit()
    return {"status": "ok", "message": "已駁回認領"}


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
