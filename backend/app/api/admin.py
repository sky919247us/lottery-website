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


def _admin_to_dict(admin: AdminUser) -> dict:
    """將 AdminUser 物件轉為前端需要的字典"""
    return {
        "id": admin.id,
        "username": admin.username,
        "displayName": admin.displayName or admin.username,
        "role": admin.role,
        "retailerId": admin.retailerId,
        "isActive": admin.isActive,
        "expireAt": admin.expireAt.isoformat() if admin.expireAt else None,
        "lastLoginAt": admin.lastLoginAt.isoformat() if admin.lastLoginAt else None,
        "createdAt": admin.createdAt.isoformat() if admin.createdAt else None,
    }


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
        user=_admin_to_dict(admin),
    )


@router.get("/auth/me")
async def admin_me(admin: AdminUser = Depends(get_current_admin)):
    """取得當前管理員資料"""
    return _admin_to_dict(admin)


# ─── 帳號管理（僅超級管理員）───────────────────────────

@router.get("/users")
async def list_admin_users(
    admin: AdminUser = Depends(require_role(ROLE_SUPER_ADMIN)),
    db: Session = Depends(get_db),
):
    """列出所有管理員帳號"""
    admins = db.query(AdminUser).order_by(AdminUser.createdAt.desc()).all()
    return [_admin_to_dict(a) for a in admins]


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
    return _admin_to_dict(new_admin)


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

    db.commit()
    db.refresh(target)
    logger.info(f"超級管理員 [{admin.username}] 更新帳號: {target.username}")
    return _admin_to_dict(target)


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

    total_retailers = db.query(Retailer).count()
    active_retailers = db.query(Retailer).filter(Retailer.isActive == True).count()
    claimed_retailers = db.query(Retailer).filter(Retailer.isClaimed == True).count()
    
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
    query = db.query(MerchantClaim)
    if status:
        query = query.filter(MerchantClaim.status == status)
    return query.order_by(MerchantClaim.createdAt.desc()).all()


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

    db.commit()
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
