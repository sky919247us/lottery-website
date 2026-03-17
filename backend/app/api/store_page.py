"""
商家專屬頁面 API 路由
公開展示頁面 + 商家後台圖片管理
"""

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session

from app.model.database import get_db
from app.model.retailer import Retailer
from app.model.merchant import MerchantClaim
from app.model.merchant_photo import MerchantPhoto
from app.model.merchant_inventory import MerchantInventory
from app.model.admin import AdminUser, ROLE_SUPER_ADMIN, ROLE_ADMIN
from app.service.admin_auth_service import get_current_admin, require_role

logger = logging.getLogger(__name__)

router = APIRouter(tags=["商家專屬頁面"])

# 每位商家各分類圖片上限
MAX_PHOTOS_PER_CATEGORY = 10


# ─── 公開 API（不需登入）────────────────────────────────

@router.get("/api/store/{retailer_id}")
async def get_store_page(retailer_id: int, db: Session = Depends(get_db)):
    """取得商家公開專屬頁面資料"""
    retailer = db.query(Retailer).filter(Retailer.id == retailer_id).first()
    if not retailer:
        raise HTTPException(status_code=404, detail="店家不存在")

    # 僅 PRO 等級且已認領的商家才開放專屬頁面
    if retailer.merchantTier != "pro" or not retailer.isClaimed:
        raise HTTPException(status_code=404, detail="此店家尚未開通專屬頁面")

    # 取得圖片
    photos = (
        db.query(MerchantPhoto)
        .filter(MerchantPhoto.retailerId == retailer_id)
        .order_by(MerchantPhoto.sortOrder, MerchantPhoto.createdAt.desc())
        .all()
    )
    gallery = [
        {"id": p.id, "imageUrl": p.imageUrl, "caption": p.caption}
        for p in photos if p.category == "gallery"
    ]
    winning_wall = [
        {"id": p.id, "imageUrl": p.imageUrl, "caption": p.caption}
        for p in photos if p.category == "winning_wall"
    ]

    # 取得庫存
    inventory = (
        db.query(MerchantInventory)
        .filter(MerchantInventory.retailerId == retailer_id)
        .all()
    )

    # 設施標籤
    facility_keys = [
        "hasAC", "hasToilet", "hasSeats", "hasWifi",
        "hasAccessibility", "hasEPay", "hasStrategy", "hasNumberPick",
        "hasScratchBoard", "hasMagnifier", "hasReadingGlasses",
        "hasNewspaper", "hasSportTV"
    ]
    facilities = {k: getattr(retailer, k, False) for k in facility_keys}

    return {
        "store": {
            "id": retailer.id,
            "name": retailer.name,
            "address": retailer.address,
            "city": retailer.city,
            "district": retailer.district,
            "lat": retailer.lat,
            "lng": retailer.lng,
            "description": retailer.description or "",
            "bannerUrl": retailer.bannerUrl or "",
            "contactLine": retailer.contactLine or "",
            "contactFb": retailer.contactFb or "",
            "contactPhone": retailer.contactPhone or "",
            "businessHours": retailer.businessHours or "",
            "announcement": retailer.announcement or "",
        },
        "facilities": facilities,
        "gallery": gallery,
        "winningWall": winning_wall,
        "inventory": [
            {
                "id": inv.id,
                "itemName": inv.itemName,
                "itemPrice": inv.itemPrice,
                "status": inv.effective_status,
                "imageUrl": inv.scratchcard.imageUrl if inv.scratchcard else "",
                "gameId": inv.scratchcard.gameId if inv.scratchcard else "",
                "updatedAt": inv.updatedAt.isoformat() if inv.updatedAt else None,
            }
            for inv in inventory
        ],
    }


# ─── 商家後台 API（需要登入）──────────────────────────────

@router.put("/api/admin/merchant/store-page")
async def update_store_page(
    data: dict,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
):
    """更新商家專屬頁面資訊（文字欄位）"""
    # 取得商家對應的經銷商
    retailer = _get_merchant_retailer(admin, db)

    # PRO 才能編輯
    if retailer.merchantTier != "pro":
        raise HTTPException(status_code=403, detail="此功能僅限 PRO 方案商家使用")

    # 允許更新的欄位
    allowed_fields = [
        "description", "bannerUrl", "contactLine", "contactFb",
        "contactPhone", "businessHours"
    ]
    for field in allowed_fields:
        if field in data:
            setattr(retailer, field, data[field])

    db.commit()
    logger.info(f"商家 {admin.username} 更新了專屬頁面資訊")
    return {"status": "ok"}


@router.post("/api/admin/merchant/photos")
async def upload_store_photo(
    file: UploadFile = File(...),
    category: str = Form("gallery"),
    caption: str = Form(""),
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
):
    """上傳商家圖片至 Cloudflare R2"""
    retailer = _get_merchant_retailer(admin, db)

    if retailer.merchantTier != "pro":
        raise HTTPException(status_code=403, detail="此功能僅限 PRO 方案商家使用")

    if category not in ("gallery", "winning_wall"):
        raise HTTPException(status_code=400, detail="不支援的圖片分類")

    # 檢查該分類數量是否超過上限
    count = (
        db.query(MerchantPhoto)
        .filter(
            MerchantPhoto.retailerId == retailer.id,
            MerchantPhoto.category == category,
        )
        .count()
    )
    if count >= MAX_PHOTOS_PER_CATEGORY:
        raise HTTPException(
            status_code=400,
            detail=f"每個分類最多 {MAX_PHOTOS_PER_CATEGORY} 張圖片，請先刪除舊照片"
        )

    # 讀取並上傳至 R2
    file_data = await file.read()

    from app.service.r2_service import upload_image
    try:
        public_url, r2_key = upload_image(file_data, retailer.id, category)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))

    # 寫入資料庫
    photo = MerchantPhoto(
        retailerId=retailer.id,
        category=category,
        imageUrl=public_url,
        r2Key=r2_key,
        caption=caption,
        sortOrder=count,  # 新圖片排在最後
    )
    db.add(photo)
    db.commit()
    db.refresh(photo)

    logger.info(f"商家 {admin.username} 上傳了 {category} 圖片: {r2_key}")
    return {
        "status": "ok",
        "photo": {
            "id": photo.id,
            "imageUrl": photo.imageUrl,
            "caption": photo.caption,
            "category": photo.category,
        }
    }


@router.delete("/api/admin/merchant/photos/{photo_id}")
async def delete_store_photo(
    photo_id: int,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
):
    """刪除商家圖片（商家本人、管理員、超級管理員皆可操作）"""
    photo = db.query(MerchantPhoto).filter(MerchantPhoto.id == photo_id).first()
    if not photo:
        raise HTTPException(status_code=404, detail="圖片不存在")

    # 權限檢查：超級管理員與管理員可刪除任何圖片，商家只能刪除自己的
    if admin.role not in (ROLE_SUPER_ADMIN, ROLE_ADMIN):
        retailer = _get_merchant_retailer(admin, db)
        if photo.retailerId != retailer.id:
            raise HTTPException(status_code=403, detail="無權刪除此圖片")

    # 從 R2 刪除
    from app.service.r2_service import delete_image
    delete_image(photo.r2Key)

    # 從資料庫刪除
    db.delete(photo)
    db.commit()

    logger.info(f"使用者 {admin.username} 刪除了圖片 #{photo_id}")
    return {"status": "ok"}


@router.post("/api/admin/merchant/banner")
async def upload_banner(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
):
    """上傳或更換商家頁面橫幅圖片"""
    retailer = _get_merchant_retailer(admin, db)

    if retailer.merchantTier != "pro":
        raise HTTPException(status_code=403, detail="此功能僅限 PRO 方案商家使用")

    file_data = await file.read()

    from app.service.r2_service import upload_image, delete_image

    # 若有舊 Banner，先刪除
    if retailer.bannerUrl:
        # 從 URL 反推 r2_key
        public_base = __import__("os").getenv("R2_PUBLIC_URL", "").rstrip("/")
        if public_base and retailer.bannerUrl.startswith(public_base):
            old_key = retailer.bannerUrl[len(public_base) + 1:]
            delete_image(old_key)

    try:
        public_url, r2_key = upload_image(file_data, retailer.id, "banner")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))

    retailer.bannerUrl = public_url
    db.commit()

    logger.info(f"商家 {admin.username} 更新了 Banner: {r2_key}")
    return {"status": "ok", "bannerUrl": public_url}


# ─── 管理員 API（超級管理員與管理員可刪除任何商家圖片）──────

@router.get("/api/admin/store-photos/{retailer_id}")
async def admin_get_store_photos(
    retailer_id: int,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(require_role(ROLE_SUPER_ADMIN, ROLE_ADMIN)),
):
    """管理員檢視某間店家的所有圖片"""
    photos = (
        db.query(MerchantPhoto)
        .filter(MerchantPhoto.retailerId == retailer_id)
        .order_by(MerchantPhoto.category, MerchantPhoto.sortOrder)
        .all()
    )
    return [
        {
            "id": p.id,
            "category": p.category,
            "imageUrl": p.imageUrl,
            "caption": p.caption,
            "sortOrder": p.sortOrder,
            "createdAt": p.createdAt.isoformat() if p.createdAt else None,
        }
        for p in photos
    ]


# ─── 內部工具函式 ──────────────────────────────────────

def _get_merchant_retailer(admin: AdminUser, db: Session) -> Retailer:
    """根據商家帳號取得關聯的經銷商"""
    if not admin.retailerId:
        raise HTTPException(status_code=400, detail="此帳號未關聯任何店家")

    retailer = db.query(Retailer).filter(Retailer.id == admin.retailerId).first()
    if not retailer:
        raise HTTPException(status_code=404, detail="關聯的店家不存在")

    return retailer
