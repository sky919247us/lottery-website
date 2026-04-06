"""
Admin 後台 API 路由
管理員登入、帳號管理、系統營運資料
"""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, Body
from sqlalchemy.orm import Session

from app.model.database import get_db, Scratchcard, Checkin
from app.model.admin import (
    AdminUser,
    AdminRetailerMapping,
    ROLE_SUPER_ADMIN,
    ROLE_ADMIN,
    ROLE_MERCHANT,
    hash_password,
    verify_password,
)
from app.model.retailer import Retailer
from app.model.user import User, InventoryReport, KarmaLog, KARMA_LEVELS, calc_karma_level, get_level_info
from app.service.analytics_service import CloudflareAnalyticsService
from app.schema.admin import (
    AdminLoginRequest,
    AdminLoginResponse,
    AdminCreateRequest,
    AdminUpdateRequest,
    AdminChangePasswordRequest,
    AdminRetailerUpdateRequest,
    MerchantStoreUpdate,
    KarmaAdjustRequest,
    BulkBanRequest,
    BulkRetailerStatusRequest,
)
from app.service.admin_auth_service import (
    create_admin_jwt,
    get_current_admin,
    require_role,
)
from app.service.scraper_service import sync_jackpot_stores

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin", tags=["後台管理"])


def _admin_to_dict(admin: AdminUser, db: Session = None) -> dict:
    """將 AdminUser 物件轉為前端需要的字典"""
    # 取得此帳號管理的所有店家 ID
    retailer_ids = []
    if db and admin.role == ROLE_MERCHANT:
        mappings = db.query(AdminRetailerMapping).filter(
            AdminRetailerMapping.adminId == admin.id
        ).all()
        retailer_ids = [m.retailerId for m in mappings]
        # 向下相容：如果 mapping 表為空但 retailerId 有值
        if not retailer_ids and admin.retailerId:
            retailer_ids = [admin.retailerId]

    result = {
        "id": admin.id,
        "username": admin.username,
        "displayName": admin.displayName or admin.username,
        "role": admin.role,
        "retailerId": admin.retailerId,
        "retailerIds": retailer_ids,
        "isActive": admin.isActive,
        "expireAt": admin.expireAt.isoformat() if admin.expireAt else None,
        "lastLoginAt": admin.lastLoginAt.isoformat() if admin.lastLoginAt else None,
        "createdAt": admin.createdAt.isoformat() if admin.createdAt else None,
        "proExpiresAt": None,
    }
    # 商家角色：查詢 PRO 到期日
    if db and admin.role == ROLE_MERCHANT and admin.retailerId:
        from app.model.merchant import MerchantClaim
        claim = db.query(MerchantClaim).filter(
            MerchantClaim.retailerId == admin.retailerId,
            MerchantClaim.tier == "pro",
        ).first()
        if claim and claim.proExpiresAt:
            result["proExpiresAt"] = claim.proExpiresAt.isoformat()
    return result


def _resolve_retailer_id(admin: AdminUser, db: Session, retailer_id: int | None = None) -> int:
    """
    解析商家帳號的目標店家 ID。
    如果指定了 retailer_id，驗證此帳號是否有權管理該店。
    否則使用 admin.retailerId（預設店家）。
    """
    if retailer_id:
        # 驗證帳號是否有權管理此店
        mapping = db.query(AdminRetailerMapping).filter(
            AdminRetailerMapping.adminId == admin.id,
            AdminRetailerMapping.retailerId == retailer_id,
        ).first()
        if mapping:
            return retailer_id
        # 向下相容：如果 mapping 表尚未回填，但 retailerId 吻合
        if admin.retailerId == retailer_id:
            return retailer_id
        raise HTTPException(status_code=403, detail="無權管理此店家")

    if not admin.retailerId:
        raise HTTPException(status_code=404, detail="尚未關聯店家，請聯繫管理員設定")
    return admin.retailerId


# ─── 登入 ───────────────────────────────────────────

@router.post("/auth/login", response_model=AdminLoginResponse)
async def admin_login(data: AdminLoginRequest, db: Session = Depends(get_db)):
    """管理員帳號密碼登入"""
    admin = db.query(AdminUser).filter(AdminUser.username == data.username).first()
    
    if not admin or not verify_password(data.password, admin.passwordHash, admin.passwordSalt):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="帳號或密碼錯誤",
        )

    if not admin.isActive:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="帳號已被停用",
        )

    # 更新最後登入時間
    admin.lastLoginAt = datetime.now(timezone.utc)
    db.commit()

    token = create_admin_jwt(admin.id, admin.role)
    logger.info(f"管理員登入成功: {admin.username} (角色: {admin.role})")

    return AdminLoginResponse(
        token=token,
        user=_admin_to_dict(admin, db),
    )


@router.get("/auth/me")
async def admin_me(admin: AdminUser = Depends(get_current_admin), db: Session = Depends(get_db)):
    """取得當前管理員資料"""
    return _admin_to_dict(admin, db)


# ─── 帳號管理（僅超級管理員）───────────────────────────

@router.get("/users")
async def list_admin_users(
    admin: AdminUser = Depends(require_role(ROLE_SUPER_ADMIN)),
    db: Session = Depends(get_db),
):
    """列出所有管理員帳號"""
    admins = db.query(AdminUser).order_by(AdminUser.createdAt.desc()).all()
    return [_admin_to_dict(a, db) for a in admins]


@router.post("/users")
async def create_admin_user(
    data: AdminCreateRequest,
    admin: AdminUser = Depends(require_role(ROLE_SUPER_ADMIN)),
    db: Session = Depends(get_db),
):
    """建立管理員帳號（僅超級管理員）"""
    # 檢查帳號是否重複
    existing = db.query(AdminUser).filter(AdminUser.username == data.username).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"帳號 '{data.username}' 已存在",
        )

    # 驗證角色
    if data.role not in [ROLE_SUPER_ADMIN, ROLE_ADMIN, ROLE_MERCHANT]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"無效的角色: {data.role}",
        )

    # 建立帳號
    hashed, salt = hash_password(data.password)
    new_admin = AdminUser(
        username=data.username,
        passwordHash=hashed,
        passwordSalt=salt,
        displayName=data.displayName,
        role=data.role,
        retailerId=data.retailerId,
        expireAt=data.expireAt,
    )
    db.add(new_admin)
    db.commit()
    db.refresh(new_admin)

    logger.info(f"超級管理員 [{admin.username}] 建立帳號: {data.username} (角色: {data.role})")
    return _admin_to_dict(new_admin, db)


@router.put("/users/{user_id}")
async def update_admin_user(
    user_id: int,
    data: AdminUpdateRequest,
    admin: AdminUser = Depends(require_role(ROLE_SUPER_ADMIN)),
    db: Session = Depends(get_db),
):
    """更新管理員帳號資訊（僅超級管理員）"""
    target = db.query(AdminUser).filter(AdminUser.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="帳號不存在")

    if data.displayName is not None:
        target.displayName = data.displayName
    if data.role is not None:
        target.role = data.role
    if data.retailerId is not None:
        target.retailerId = data.retailerId
    if data.isActive is not None:
        target.isActive = data.isActive

    if data.expireAt is not None:
        target.expireAt = data.expireAt

    # 處理 PRO 到期日更新（同步 MerchantClaim + Retailer）
    if data.proExpiresAt is not None and target.role == ROLE_MERCHANT and target.retailerId:
        from app.model.merchant import MerchantClaim
        from datetime import datetime as dt

        claim = db.query(MerchantClaim).filter(
            MerchantClaim.retailerId == target.retailerId,
            MerchantClaim.status == "approved",
        ).first()

        retailer = db.query(Retailer).filter(Retailer.id == target.retailerId).first()

        if data.proExpiresAt == "" or data.proExpiresAt is None:
            # 移除 PRO
            if claim:
                claim.tier = "basic"
                claim.proExpiresAt = None
            if retailer:
                retailer.merchantTier = "basic"
                retailer.tierExpireAt = None
        else:
            # 設定 PRO 到期日
            expire_dt = data.proExpiresAt if isinstance(data.proExpiresAt, dt) else dt.fromisoformat(str(data.proExpiresAt))
            if claim:
                claim.tier = "pro"
                claim.proExpiresAt = expire_dt
            if retailer:
                retailer.merchantTier = "pro"
                retailer.tierExpireAt = expire_dt

    db.commit()
    db.refresh(target)
    logger.info(f"超級管理員 [{admin.username}] 更新帳號: {target.username}")
    return _admin_to_dict(target, db)


@router.post("/users/{user_id}/reset-password")
async def reset_user_password(
    user_id: int,
    admin: AdminUser = Depends(require_role(ROLE_SUPER_ADMIN)),
    db: Session = Depends(get_db),
):
    """超級管理員重設其他帳號密碼（重設為帳號名稱）"""
    target = db.query(AdminUser).filter(AdminUser.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="帳號不存在")

    # 重設密碼為使用者名稱（帳號名稱）
    new_password = target.username
    hashed, salt = hash_password(new_password)
    target.passwordHash = hashed
    target.passwordSalt = salt
    db.commit()
    logger.info(f"超級管理員 [{admin.username}] 重設了 [{target.username}] 的密碼")
    return {"status": "ok", "message": f"密碼已重設為帳號名稱「{target.username}」"}


@router.delete("/users/{user_id}")
async def delete_admin_user(
    user_id: int,
    admin: AdminUser = Depends(require_role(ROLE_SUPER_ADMIN)),
    db: Session = Depends(get_db),
):
    """刪除管理員帳號（僅超級管理員）"""
    target = db.query(AdminUser).filter(AdminUser.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="帳號不存在")
    if target.id == admin.id:
        raise HTTPException(status_code=400, detail="無法刪除自己的帳號")

    db.delete(target)
    db.commit()
    logger.info(f"超級管理員 [{admin.username}] 刪除帳號: ID {user_id}")
    return {"status": "ok"}


# ─── 數據總覽（控制面板） ────────────────────────────

@router.get("/dashboard/stats")
async def get_dashboard_stats(
    admin: AdminUser = Depends(require_role(ROLE_SUPER_ADMIN, ROLE_ADMIN)),
    db: Session = Depends(get_db),
):
    """取得後台首頁統計數據"""
    from app.model.user import User, InventoryReport
    from app.model.retailer import Retailer
    from app.model.merchant import MerchantClaim
    from datetime import datetime, timedelta

    from app.model.database import Scratchcard

    total_retailers = db.query(Retailer).count()
    active_retailers = db.query(Retailer).filter(Retailer.isActive.is_(True)).count()
    claimed_retailers = db.query(Retailer).filter(Retailer.isClaimed.is_(True)).count()

    # 台灣彩券 / 台灣運彩 分類統計
    lottery_retailers = db.query(Retailer).filter(
        Retailer.source == "台灣彩券", Retailer.isActive.is_(True)
    ).count()
    sports_retailers = db.query(Retailer).filter(
        Retailer.source == "台灣運彩", Retailer.isActive.is_(True)
    ).count()

    # 刮刮樂款式數
    total_scratchcards = db.query(Scratchcard).count()

    total_users = db.query(User).count()
    total_claims = db.query(MerchantClaim).count()
    pending_claims = db.query(MerchantClaim).filter(MerchantClaim.status == "pending").count()

    # 庫存回報數 (近 7 天)
    week_ago = datetime.now() - timedelta(days=7)
    recent_reports = db.query(InventoryReport).filter(InventoryReport.createdAt >= week_ago).count()

    return {
        "totalRetailers": total_retailers,
        "activeRetailers": active_retailers,
        "claimedRetailers": claimed_retailers,
        "twLotteryCount": lottery_retailers,
        "sportsLotteryCount": sports_retailers,
        "totalScratchcards": total_scratchcards,
        "totalUsers": total_users,
        "pendingClaims": pending_claims,
        "totalClaims": total_claims,
        "recentInventoryReports": recent_reports,
    }


@router.get("/dashboard/traffic")
async def get_dashboard_traffic(
    admin: AdminUser = Depends(require_role(ROLE_SUPER_ADMIN, ROLE_ADMIN)),
):
    """取得流量分析數據 (串接 Cloudflare 或模擬數據)"""
    import os
    cf_token = os.getenv("CLOUDFLARE_API_TOKEN")
    cf_account = os.getenv("CLOUDFLARE_ACCOUNT_ID")
    cf_zone = os.getenv("CLOUDFLARE_ZONE_ID")

    if not all([cf_token, cf_account, cf_zone]):
        # 若無環境變數，回傳模擬數據避免 500
        from datetime import date, timedelta
        return {
            "daily": [
                {"date": (date.today() - timedelta(days=i)).isoformat(), "visits": 120 - i*5, "pageviews": 450 - i*15}
                for i in range(7, -1, -1)
            ],
            "topPages": [
                {"path": "/", "views": 2500},
                {"path": "/map", "views": 1800},
                {"path": "/calculator", "views": 1200},
            ],
            "topCountries": [
                {"country": "Taiwan", "views": 5000},
                {"country": "United States", "views": 200},
            ],
            "topReferrers": [
                {"host": "google.com", "views": 3000},
                {"host": "facebook.com", "views": 1200},
                {"host": "Direct", "views": 800},
            ]
        }

    service = CloudflareAnalyticsService(cf_token, cf_account, cf_zone)
    data = await service.get_traffic_stats()
    return data or {"error": "Failed to fetch traffic stats"}


@router.post("/users/change-password")
async def change_password(
    data: AdminChangePasswordRequest,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """修改自己的密碼"""
    if not verify_password(data.oldPassword, admin.passwordHash, admin.passwordSalt):
        raise HTTPException(status_code=400, detail="舊密碼錯誤")

    hashed, salt = hash_password(data.newPassword)
    admin.passwordHash = hashed
    admin.passwordSalt = salt
    db.commit()
    logger.info(f"管理員 [{admin.username}] 修改了密碼")
    return {"status": "ok"}


# ─── 系統設定管理 ───────────────────────────────────

@router.post("/trigger-jackpot-sync")
async def trigger_jackpot_sync(
    background_tasks: BackgroundTasks,
    admin: AdminUser = Depends(require_role(ROLE_SUPER_ADMIN)),
):
    """手動觸發台彩頭獎店家同步爬蟲（僅超級管理員可執行）"""
    logger.info(f"超級管理員 [{admin.username}] 手動觸發頭獎店家同步爬蟲")
    background_tasks.add_task(sync_jackpot_stores)
    return {"message": "頭獎店家同步已經於背景啟動"}

# ─── 認領審核管理 ───────────────────────────────────

@router.get("/merchant-claims")
async def get_claims(
    status: str | None = None,
    admin: AdminUser = Depends(require_role(ROLE_SUPER_ADMIN, ROLE_ADMIN)),
    db: Session = Depends(get_db),
):
    """取得認領申請列表（管理員用）"""
    from app.model.merchant import MerchantClaim
    from app.model.retailer import Retailer
    from app.model.user import User
    query = db.query(MerchantClaim)
    if status:
        query = query.filter(MerchantClaim.status == status)
    claims = query.order_by(MerchantClaim.createdAt.desc()).all()

    result = []
    for c in claims:
        retailer = db.query(Retailer).filter(Retailer.id == c.retailerId).first()
        user = db.query(User).filter(User.id == c.userId).first()
        item = {
            "id": c.id,
            "retailerId": c.retailerId,
            "storeName": retailer.name if retailer else "",
            "userId": c.userId,
            "lineDisplayName": user.displayName if user else "",
            "contactName": c.contactName,
            "contactPhone": c.contactPhone,
            "licenseUrl": c.licenseUrl,
            "idCardUrl": c.idCardUrl,
            "status": c.status,
            "tier": c.tier,
            "rejectReason": c.rejectReason,
            "createdAt": c.createdAt,
            "approvedAt": c.approvedAt,
        }
        result.append(item)
    return result


@router.put("/merchant-claims/{claim_id}/approve")
async def approve_claim(
    claim_id: int, 
    admin: AdminUser = Depends(require_role(ROLE_SUPER_ADMIN, ROLE_ADMIN)),
    db: Session = Depends(get_db)
):
    """核准認領（管理員操作）"""
    from app.model.merchant import MerchantClaim
    from app.model.retailer import Retailer
    from datetime import datetime
    
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

    # 自動建立商家後台帳號（支援多店：同手機號碼的帳號只建一次，後續只加 mapping）
    from app.model.admin import AdminUser, AdminRetailerMapping, ROLE_MERCHANT, hash_password
    from app.model.user import User

    user = db.query(User).filter(User.id == claim.userId).first()
    store_name = retailer.name if retailer else "店家"

    merchant_username = claim.contactPhone or f"merchant_{claim.retailerId}"
    merchant_password = None
    is_new_account = False

    # 優先用手機號碼（即帳號名稱）找既有商家帳號
    existing_account = db.query(AdminUser).filter(
        AdminUser.username == merchant_username,
        AdminUser.role == ROLE_MERCHANT,
    ).first()

    if not existing_account:
        # 全新帳號：建立 AdminUser + mapping
        is_new_account = True
        merchant_password = merchant_username  # 預設密碼 = 手機號碼

        hashed, salt = hash_password(merchant_password)
        new_admin = AdminUser(
            username=merchant_username,
            passwordHash=hashed,
            passwordSalt=salt,
            displayName=store_name,
            role=ROLE_MERCHANT,
            retailerId=claim.retailerId,
            isActive=1,
        )
        db.add(new_admin)
        db.flush()  # 取得 new_admin.id

        mapping = AdminRetailerMapping(
            adminId=new_admin.id,
            retailerId=claim.retailerId,
        )
        db.add(mapping)
    else:
        # 既有帳號：只新增 mapping（如果尚未存在）
        existing_mapping = db.query(AdminRetailerMapping).filter(
            AdminRetailerMapping.adminId == existing_account.id,
            AdminRetailerMapping.retailerId == claim.retailerId,
        ).first()
        if not existing_mapping:
            mapping = AdminRetailerMapping(
                adminId=existing_account.id,
                retailerId=claim.retailerId,
            )
            db.add(mapping)

    db.commit()

    # 發送 LINE 通知
    try:
        from app.service.line_notify import notify_claim_approved
        if user and user.lineUserId:
            notify_claim_approved(
                user.lineUserId, store_name, claim.id,
                username=merchant_username,
                password=merchant_password if is_new_account else None,
            )
    except Exception as e:
        logger.warning(f"[LINE] 通知發送失敗（不影響審核）: {e}")

    return {"status": "ok", "message": "已核准認領"}


@router.put("/merchant-claims/{claim_id}/reject")
async def reject_claim(
    claim_id: int, 
    reason: str = "", 
    admin: AdminUser = Depends(require_role(ROLE_SUPER_ADMIN, ROLE_ADMIN)),
    db: Session = Depends(get_db)
):
    """駁回認領（管理員操作）"""
    from app.model.merchant import MerchantClaim
    claim = db.query(MerchantClaim).filter(MerchantClaim.id == claim_id).first()
    if not claim:
        raise HTTPException(status_code=404, detail="認領申請不存在")

    claim.status = "rejected"
    claim.rejectReason = reason
    db.commit()

    # 發送 LINE 通知
    try:
        from app.model.user import User
        from app.model.retailer import Retailer
        from app.service.line_notify import notify_claim_rejected
        user = db.query(User).filter(User.id == claim.userId).first()
        retailer = db.query(Retailer).filter(Retailer.id == claim.retailerId).first()
        if user and user.lineUserId:
            store_name = retailer.name if retailer else "您的店家"
            notify_claim_rejected(user.lineUserId, store_name, reason)
    except Exception as e:
        logger.warning(f"[LINE] 通知發送失敗（不影響審核）: {e}")

    return {"status": "ok", "message": "已駁回認領"}


# ─── 彩券行管理（管理員 + 超級管理員）─────────────────
@router.get("/retailers/search")
async def search_retailers(
    q: str,
    admin: AdminUser = Depends(require_role(ROLE_SUPER_ADMIN, ROLE_ADMIN)),
    db: Session = Depends(get_db),
):
    """搜尋彩券行 (供關聯使用)"""
    if not q or len(q) < 2:
        return []
        
    results = db.query(Retailer).filter(
        Retailer.name.contains(q) | Retailer.address.contains(q)
    ).limit(10).all()
    
    return [{"id": r.id, "name": r.name, "address": r.address} for r in results]

@router.get("/retailers")
async def list_retailers(
    page: int = 1,
    pageSize: int = 20,
    search: str = "",
    city: str = "",
    district: str = "",
    admin: AdminUser = Depends(require_role(ROLE_SUPER_ADMIN, ROLE_ADMIN)),
    db: Session = Depends(get_db),
):
    """列出所有彩券行（支援分頁與搜尋）"""
    query = db.query(Retailer)

    if search:
        query = query.filter(
            Retailer.name.contains(search) | 
            Retailer.address.contains(search) | 
            Retailer.source.contains(search)
        )
    if city:
        # 相容「台」與「臺」
        alt_city = city.replace("台", "臺") if "台" in city else city.replace("臺", "台")
        query = query.filter((Retailer.city == city) | (Retailer.city == alt_city))
    if district:
        # 相容「台」與「臺」
        alt_district = district.replace("台", "臺") if "台" in district else district.replace("臺", "台")
        query = query.filter((Retailer.district == district) | (Retailer.district == alt_district))

    total = query.count()
    retailers = (
        query.order_by(Retailer.id)
        .offset((page - 1) * pageSize)
        .limit(pageSize)
        .all()
    )

    return {
        "total": total,
        "page": page,
        "pageSize": pageSize,
        "items": [
            {
                "id": r.id,
                "name": r.name,
                "address": r.address,
                "city": r.city,
                "district": r.district,
                "source": r.source,
                "lat": r.lat,
                "lng": r.lng,
                "isActive": r.isActive,
                "isClaimed": r.isClaimed,
                "merchantTier": r.merchantTier,
                "manualRating": r.manualRating,
            }
            for r in retailers
        ],
    }


@router.put("/retailers/{retailer_id}")
async def update_retailer(
    retailer_id: int,
    data: AdminRetailerUpdateRequest,
    admin: AdminUser = Depends(require_role(ROLE_SUPER_ADMIN, ROLE_ADMIN)),
    db: Session = Depends(get_db),
):
    """更新彩券行資料"""
    retailer = db.query(Retailer).filter(Retailer.id == retailer_id).first()
    if not retailer:
        raise HTTPException(status_code=404, detail="彩券行不存在")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(retailer, field, value)

    db.commit()
    db.refresh(retailer)
    logger.info(f"管理員 [{admin.username}] 更新彩券行 #{retailer_id}")
    return {"status": "ok"}


@router.put("/retailers/bulk-status")
async def bulk_update_retailer_status(
    data: BulkRetailerStatusRequest,
    admin: AdminUser = Depends(require_role(ROLE_SUPER_ADMIN, ROLE_ADMIN)),
    db: Session = Depends(get_db),
):
    """批量更新彩券行狀態"""
    retailers = db.query(Retailer).filter(Retailer.id.in_(data.retailerIds)).all()
    for retailer in retailers:
        retailer.isActive = data.isActive
    db.commit()
    return {"status": "ok", "updatedCount": len(retailers)}


# ─── 刮刮樂商品管理（管理員 + 超級管理員）──────────────

@router.get("/scratchcards")
async def list_scratchcards(
    page: int = 1,
    pageSize: int = 20,
    showExpired: bool = False,
    admin: AdminUser = Depends(require_role(ROLE_SUPER_ADMIN, ROLE_ADMIN)),
    db: Session = Depends(get_db),
):
    """列出所有刮刮樂商品"""
    def is_expired(deadline_str: str) -> bool:
        if not deadline_str: return False
        try:
            parts = deadline_str.strip().split('/')
            if len(parts) >= 3:
                y, m, d = int(parts[0]) + 1911, int(parts[1]), int(parts[2][:2]) # handle spaces
                from datetime import date
                return date(y, m, d) < date.today()
        except:
            pass
        return False

    all_items = db.query(Scratchcard).order_by(Scratchcard.id.desc()).all()
    
    if not showExpired:
        filtered_items = [s for s in all_items if not is_expired(s.redeemDeadline)]
    else:
        filtered_items = all_items
        
    total = len(filtered_items)
    items_page = filtered_items[(page - 1) * pageSize : page * pageSize]

    return {
        "total": total,
        "page": page,
        "pageSize": pageSize,
        "items": [
            {
                "id": s.id,
                "gameId": s.gameId,
                "name": s.name,
                "price": s.price,
                "maxPrize": s.maxPrize,
                "totalIssued": s.totalIssued,
                "salesRate": s.salesRate,
                "grandPrizeCount": s.grandPrizeCount,
                "grandPrizeUnclaimed": s.grandPrizeUnclaimed,
                "overallWinRate": s.overallWinRate,
                "imageUrl": s.imageUrl,
            }
            for s in items_page
        ],
    }


# ─── 社群使用者管理 ─────────────────────────────────────────

@router.get("/community-users")
async def list_community_users(
    page: int = 1,
    pageSize: int = 20,
    search: str = "",
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(require_role(ROLE_SUPER_ADMIN, ROLE_ADMIN)),
):
    """分頁列出所有社群使用者，支援搜尋 displayName / customNickname"""
    query = db.query(User)

    if search:
        keyword = f"%{search}%"
        query = query.filter(
            (User.displayName.like(keyword)) |
            (User.customNickname.like(keyword)) |
            (User.lineUserId.like(keyword))
        )

    total = query.count()
    users = (
        query.order_by(User.karmaPoints.desc())
        .offset((page - 1) * pageSize)
        .limit(pageSize)
        .all()
    )

    items = []
    from app.model.user import get_level_info, KARMA_LEVELS
    for u in users:
        title, weight, _ = get_level_info(u.karmaLevel)
        items.append({
            "id": u.id,
            "lineUserId": u.lineUserId,
            "displayName": u.displayName or "",
            "customNickname": u.customNickname or "",
            "pictureUrl": u.pictureUrl or "",
            "karmaPoints": u.karmaPoints,
            "karmaLevel": u.karmaLevel,
            "levelTitle": title,
            "levelWeight": weight,
            "isBanned": bool(u.isBanned),
            "createdAt": u.createdAt.isoformat() if u.createdAt else None,
        })

    return {
        "items": items,
        "total": total,
        "page": page,
        "pageSize": pageSize,
        "levels": {
            str(k): {"title": v[0], "weight": v[1], "requiredPoints": v[2]}
            for k, v in KARMA_LEVELS.items()
        },
    }

@router.get("/community-users/{user_id}/history")
async def get_community_user_history(
    user_id: int,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(require_role(ROLE_SUPER_ADMIN, ROLE_ADMIN)),
):
    """取得社群使用者的歷史紀錄 (打卡、評分、karma logs)"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="使用者不存在")
    
    from app.model.user import KarmaLog, InventoryReport, get_level_info
    from app.model.retailer import RetailerRating
    
    karma_logs = db.query(KarmaLog).filter(KarmaLog.userId == user_id).order_by(KarmaLog.createdAt.desc()).limit(50).all()
    reports = db.query(InventoryReport).filter(InventoryReport.userId == user_id).order_by(InventoryReport.createdAt.desc()).limit(50).all()
    ratings = db.query(RetailerRating).filter(RetailerRating.userId == user_id).order_by(RetailerRating.createdAt.desc()).limit(50).all()

    title, weight, _ = get_level_info(user.karmaLevel)

    return {
        "user": {
            "id": user.id,
            "lineUserId": user.lineUserId,
            "displayName": user.displayName or "",
            "customNickname": user.customNickname or "",
            "pictureUrl": user.pictureUrl or "",
            "karmaPoints": user.karmaPoints,
            "karmaLevel": user.karmaLevel,
            "levelTitle": title,
            "levelWeight": weight,
            "isBanned": bool(user.isBanned),
            "createdAt": user.createdAt.isoformat() if user.createdAt else None,
        },
        "karmaLogs": [
            {
                "id": l.id,
                "points": l.points,
                "action": l.action,
                "description": l.description,
                "createdAt": l.createdAt.isoformat() if l.createdAt else None,
            } for l in karma_logs
        ],
        "inventoryReports": [
            {
                "id": r.id,
                "retailerId": r.retailerId,
                "status": r.status,
                "createdAt": r.createdAt.isoformat() if r.createdAt else None,
            } for r in reports
        ],
        "ratings": [
            {
                "id": r.id,
                "retailerId": r.retailerId,
                "score": r.score,
                "comment": r.comment,
                "createdAt": r.createdAt.isoformat() if r.createdAt else None,
            } for r in ratings
        ]
    }

@router.put("/community-users/{user_id}/karma")
async def adjust_community_user_karma(
    user_id: int,
    data: KarmaAdjustRequest,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(require_role(ROLE_SUPER_ADMIN)),
):
    """手動調整社群使用者積分 (僅超級管理員)"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="使用者不存在")

    old_points = user.karmaPoints
    if data.set_to is None:
        if data.points == 0:
            raise HTTPException(status_code=400, detail="未指定調整數值")
        new_points = old_points + data.points
        diff = data.points
    else:
        new_points = data.set_to
        diff = new_points - old_points

    if new_points < 0:
        new_points = 0
        diff = -old_points

    user.karmaPoints = new_points
    user.karmaLevel = calc_karma_level(new_points)

    from app.model.user import KarmaLog
    log = KarmaLog(
        userId=user_id,
        points=diff,
        action="admin_adjust",
        description=f"管理員 {admin.username} 手動調整: {data.reason}"
    )
    db.add(log)
    db.commit()
    
    logger.info(f"管理員 {admin.username} 調整了使用者 {user_id} 積分: {old_points} -> {new_points}")
    return {"status": "ok", "newPoints": new_points, "newLevel": user.karmaLevel}

@router.put("/community-users/bulk-ban")
async def bulk_ban_community_users(
    data: BulkBanRequest,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(require_role(ROLE_SUPER_ADMIN)),
):
    users = db.query(User).filter(User.id.in_(data.userIds)).all()
    for user in users:
        user.isBanned = data.isBanned
    db.commit()
    logger.info(f"管理員 {admin.username} 批量{'封禁' if data.isBanned else '解封'}了使用者: {data.userIds}")
    return {"status": "ok", "updatedCount": len(users)}


# ─── 商家後台專屬店鋪讀取 ──────────────────────────────

@router.get("/merchant/my-stores")
async def get_my_stores(
    admin: AdminUser = Depends(require_role(ROLE_MERCHANT, ROLE_ADMIN, ROLE_SUPER_ADMIN)),
    db: Session = Depends(get_db),
):
    """取得商家帳號管理的所有店家清單（多店切換用）"""
    from app.model.merchant import MerchantClaim

    mappings = db.query(AdminRetailerMapping).filter(
        AdminRetailerMapping.adminId == admin.id
    ).all()
    retailer_ids = [m.retailerId for m in mappings]

    # 向下相容
    if not retailer_ids and admin.retailerId:
        retailer_ids = [admin.retailerId]

    if not retailer_ids:
        return []

    retailers = db.query(Retailer).filter(Retailer.id.in_(retailer_ids)).all()
    result = []
    for r in retailers:
        claim = db.query(MerchantClaim).filter(
            MerchantClaim.retailerId == r.id,
            MerchantClaim.status == "approved",
        ).first()
        result.append({
            "id": r.id,
            "name": r.name,
            "address": r.address,
            "merchantTier": r.merchantTier,
            "tierExpireAt": r.tierExpireAt.isoformat() if getattr(r, 'tierExpireAt', None) else None,
            "proExpiresAt": claim.proExpiresAt.isoformat() if claim and claim.proExpiresAt else None,
        })
    return result


@router.get("/merchant/my-store")
async def get_my_store(
    retailer_id: int | None = None,
    admin: AdminUser = Depends(require_role(ROLE_MERCHANT, ROLE_ADMIN, ROLE_SUPER_ADMIN)),
    db: Session = Depends(get_db),
):
    """取得商家自己關聯的店家（給商家後台看板與設定使用）"""
    rid = _resolve_retailer_id(admin, db, retailer_id)
    retailer = db.query(Retailer).filter(Retailer.id == rid).first()
    if not retailer:
        raise HTTPException(status_code=404, detail="關聯的店家記錄不存在")

    # 查找該店家的 claim_id（用於 PRO 升級付款連結）
    from app.model.merchant import MerchantClaim
    claim = db.query(MerchantClaim).filter(
        MerchantClaim.retailerId == retailer.id,
        MerchantClaim.status == "approved",
    ).first()

    return {
        "id": retailer.id,
        "claimId": claim.id if claim else None,
        "name": retailer.name,
        "address": retailer.address,
        "city": retailer.city,
        "district": retailer.district,
        "source": retailer.source,
        "lat": retailer.lat,
        "lng": retailer.lng,
        "isActive": retailer.isActive,
        "isClaimed": retailer.isClaimed,
        "merchantTier": retailer.merchantTier,
        "tierExpireAt": retailer.tierExpireAt.isoformat() if getattr(retailer, 'tierExpireAt', None) else None,
        "announcement": retailer.announcement,
        "description": retailer.description or "",
        "bannerUrl": retailer.bannerUrl or "",
        "contactLine": retailer.contactLine or "",
        "contactFb": retailer.contactFb or "",
        "contactPhone": retailer.contactPhone or "",
        "businessHours": retailer.businessHours or "",
        "mapClickCount": retailer.mapClickCount or 0,
        "nearbyInventoryCount": retailer.nearbyInventoryCount or 0,
        "hasAC": getattr(retailer, 'hasAC', False),
        "hasToilet": getattr(retailer, 'hasToilet', False),
        "hasSeats": getattr(retailer, 'hasSeats', False),
        "hasWifi": getattr(retailer, 'hasWifi', False),
        "hasAccessibility": getattr(retailer, 'hasAccessibility', False),
        "hasEPay": getattr(retailer, 'hasEPay', False),
        "hasStrategy": getattr(retailer, 'hasStrategy', False),
        "hasNumberPick": getattr(retailer, 'hasNumberPick', False),
        "hasScratchBoard": getattr(retailer, 'hasScratchBoard', False),
        "hasMagnifier": getattr(retailer, 'hasMagnifier', False),
        "hasReadingGlasses": getattr(retailer, 'hasReadingGlasses', False),
        "hasNewspaper": getattr(retailer, 'hasNewspaper', False),
        "hasSportTV": getattr(retailer, 'hasSportTV', False),
    }


@router.get("/merchant/claim/{claim_id}/checkout-url")
async def get_checkout_url(
    claim_id: int,
    admin: AdminUser = Depends(require_role(ROLE_MERCHANT, ROLE_ADMIN, ROLE_SUPER_ADMIN)),
    db: Session = Depends(get_db),
):
    """取得 Lemonsqueezy 結帳連結（帶 claim_id）"""
    from app.model.merchant import MerchantClaim
    from app.service.lemonsqueezy import LemonsqueezyService

    claim = db.query(MerchantClaim).filter(MerchantClaim.id == claim_id).first()
    if not claim:
        raise HTTPException(status_code=404, detail="申請不存在")
    if claim.status != "approved":
        raise HTTPException(status_code=403, detail="申請尚未核准")

    checkout_url = LemonsqueezyService.get_checkout_url_with_claim(claim_id)
    if not checkout_url:
        raise HTTPException(status_code=500, detail="支付系統未設定")

    return {
        "checkoutUrl": checkout_url,
        "productId": LemonsqueezyService.PRODUCT_ID,
        "price": "NT$1,680",
    }


@router.put("/merchant/my-store")
async def update_my_store(
    data: dict,
    retailer_id: int | None = None,
    admin: AdminUser = Depends(require_role(ROLE_MERCHANT, ROLE_ADMIN, ROLE_SUPER_ADMIN)),
    db: Session = Depends(get_db),
):
    """更新商家自己關聯的店家（公告與設施標籤）"""
    rid = _resolve_retailer_id(admin, db, retailer_id)
    retailer = db.query(Retailer).filter(Retailer.id == rid).first()
    if not retailer:
        raise HTTPException(status_code=404, detail="關聯的店家記錄不存在")

    allowed_fields = [
        "announcement", "hasAC", "hasToilet", "hasSeats", "hasWifi",
        "hasAccessibility", "hasEPay", "hasStrategy", "hasNumberPick",
        "hasScratchBoard", "hasMagnifier", "hasReadingGlasses",
        "hasNewspaper", "hasSportTV"
    ]
    for field in allowed_fields:
        if field in data:
            setattr(retailer, field, data[field])
            
    db.commit()
    logger.info(f"商家 {admin.username} 更新了店舖資訊")
    return {"status": "ok"}


# ─── 商家庫存管理 ──────────────────────────────────────

@router.get("/merchant/inventory")
async def get_merchant_inventory(
    retailer_id: int | None = None,
    admin: AdminUser = Depends(require_role(ROLE_MERCHANT, ROLE_ADMIN, ROLE_SUPER_ADMIN)),
    db: Session = Depends(get_db),
):
    """取得商家自己的庫存清單"""
    rid = _resolve_retailer_id(admin, db, retailer_id)

    from app.model.merchant_inventory import MerchantInventory

    items = db.query(MerchantInventory).filter(
        MerchantInventory.retailerId == rid,
    ).order_by(MerchantInventory.itemPrice.desc()).all()

    return [
        {
            "id": item.id,
            "itemName": item.itemName,
            "itemPrice": item.itemPrice,
            "status": item.status,
            "scratchcardId": item.scratchcardId,
            "gameId": item.scratchcard.gameId if item.scratchcard else None,
            "imageUrl": item.scratchcard.imageUrl if item.scratchcard else None,
            "updatedAt": item.updatedAt.isoformat() if item.updatedAt else None,
        }
        for item in items
    ]


@router.put("/merchant/inventory")
async def update_merchant_inventory(
    items: list[dict],
    retailer_id: int | None = None,
    admin: AdminUser = Depends(require_role(ROLE_MERCHANT, ROLE_ADMIN, ROLE_SUPER_ADMIN)),
    db: Session = Depends(get_db),
):
    """批量更新商家庫存狀態"""
    rid = _resolve_retailer_id(admin, db, retailer_id)

    from app.model.merchant_inventory import MerchantInventory

    for item_data in items:
        if item_data.get("id"):
            # 更新現有品項
            existing = db.query(MerchantInventory).filter(
                MerchantInventory.id == item_data["id"],
                MerchantInventory.retailerId == rid,
            ).first()
            if existing:
                existing.status = item_data.get("status", existing.status)
                existing.updatedAt = datetime.now(timezone.utc)
        else:
            # 新增品項
            new_item = MerchantInventory(
                retailerId=rid,
                scratchcardId=item_data.get("scratchcardId"),
                itemName=item_data.get("itemName", ""),
                itemPrice=item_data.get("itemPrice", 0),
                status=item_data.get("status", "未設定"),
            )
            db.add(new_item)

    db.commit()
    logger.info(f"商家 {admin.username} 更新了庫存 ({len(items)} 品項)")
    return {"status": "ok"}


@router.delete("/merchant/inventory/{item_id}")
async def delete_merchant_inventory_item(
    item_id: int,
    retailer_id: int | None = None,
    admin: AdminUser = Depends(require_role(ROLE_MERCHANT, ROLE_ADMIN, ROLE_SUPER_ADMIN)),
    db: Session = Depends(get_db),
):
    """刪除庫存品項"""
    rid = _resolve_retailer_id(admin, db, retailer_id)

    from app.model.merchant_inventory import MerchantInventory

    item = db.query(MerchantInventory).filter(
        MerchantInventory.id == item_id,
        MerchantInventory.retailerId == rid,
    ).first()
    if not item:
        raise HTTPException(status_code=404, detail="品項不存在")

    db.delete(item)
    db.commit()
    return {"status": "ok"}


@router.get("/merchant/scratchcards/search")
async def search_scratchcards_for_merchant(
    q: str = "",
    admin: AdminUser = Depends(require_role(ROLE_MERCHANT, ROLE_ADMIN, ROLE_SUPER_ADMIN)),
    db: Session = Depends(get_db),
):
    """搜尋可用的刮刮樂款式（排除已過兌獎期限）"""
    import re

    all_cards = db.query(Scratchcard).all()
    now = datetime.now()
    results = []

    for card in all_cards:
        # 排除過期款式
        if card.redeemDeadline:
            match = re.match(r"(\d+)年(\d+)月(\d+)日", card.redeemDeadline)
            if match:
                roc_year = int(match.group(1))
                m = int(match.group(2))
                d = int(match.group(3))
                try:
                    deadline = datetime(roc_year + 1911, m, d)
                    if deadline < now:
                        continue
                except ValueError:
                    pass

        # 關鍵字篩選
        if q:
            kw = q.lower()
            if kw not in card.name.lower() and kw not in card.gameId.lower():
                continue

        results.append({
            "id": card.id,
            "gameId": card.gameId,
            "name": card.name,
            "price": card.price,
            "imageUrl": card.imageUrl or "",
            "redeemDeadline": card.redeemDeadline or "",
        })

    results.sort(key=lambda x: x["price"], reverse=True)
    return results[:50]


@router.get("/merchant/photos")
async def get_merchant_photos(
    retailer_id: int | None = None,
    admin: AdminUser = Depends(require_role(ROLE_MERCHANT, ROLE_ADMIN, ROLE_SUPER_ADMIN)),
    db: Session = Depends(get_db),
):
    """取得商家自己的所有圖片"""
    rid = _resolve_retailer_id(admin, db, retailer_id)

    from app.model.merchant_photo import MerchantPhoto

    photos = (
        db.query(MerchantPhoto)
        .filter(MerchantPhoto.retailerId == rid)
        .order_by(MerchantPhoto.category, MerchantPhoto.sortOrder, MerchantPhoto.createdAt.desc())
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

    return {"gallery": gallery, "winningWall": winning_wall}

