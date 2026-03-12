"""
庫存回報 API 路由
GPS 地理圍欄驗證 + 信心值計算
"""

import math
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.model.database import get_db
from app.model.retailer import Retailer
from app.model.user import InventoryReport, User, get_level_info
from app.schema.user import InventoryReportCreate, InventoryReportResponse, InventoryStatusResponse
from app.api.user import add_karma

router = APIRouter(prefix="/api/inventory", tags=["庫存回報"])


def haversine_distance(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """
    使用 Haversine 公式計算兩點之間的距離（公尺）
    """
    R = 6371000  # 地球半徑（公尺）
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lng2 - lng1)
    a = (math.sin(delta_phi / 2) ** 2
         + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def get_distance_factor(distance: float) -> float:
    """
    GPS 距離權重因子
    < 50m : 100% (實地回報)
    50~200m : 30% (路人觀察)
    > 200m : 0% (禁止庫存回報)
    """
    if distance <= 50:
        return 1.0
    elif distance <= 200:
        return 0.3
    return 0.0


@router.post("/report", response_model=InventoryReportResponse, status_code=201)
def report_inventory(
    data: InventoryReportCreate,
    db: Session = Depends(get_db),
):
    """
    回報庫存狀態
    含 GPS 距離驗證與 Karma 獎勵
    """
    # 驗證使用者
    user = db.query(User).filter(User.id == data.userId).first()
    if not user:
        raise HTTPException(status_code=404, detail="使用者不存在")
    if user.isBanned:
        raise HTTPException(status_code=403, detail="帳號已被封禁")

    # 驗證店家
    retailer = db.query(Retailer).filter(Retailer.id == data.retailerId).first()
    if not retailer:
        raise HTTPException(status_code=404, detail="經銷商不存在")

    # GPS 距離驗證
    distance = None
    distance_factor = 1.0

    if data.lat is not None and data.lng is not None and retailer.lat is not None and retailer.lng is not None:
        distance = haversine_distance(data.lat, data.lng, retailer.lat, retailer.lng)
        distance_factor = get_distance_factor(distance)

        if distance_factor == 0:
            raise HTTPException(
                status_code=400,
                detail=f"距離過遠（{distance:.0f}m），需在 200m 內才能回報庫存"
            )

    # 計算信心值 = 等級權重 × 距離因子
    _, weight, _ = get_level_info(user.karmaLevel)
    confidence = weight * distance_factor

    # 建立回報
    report = InventoryReport(
        retailerId=data.retailerId,
        userId=data.userId,
        item=data.item,
        status=data.status,
        lat=data.lat,
        lng=data.lng,
        distance=distance,
        confidence=confidence,
    )
    db.add(report)
    db.commit()
    db.refresh(report)

    # 給予 Karma 獎勵
    karma_points = 10 if distance_factor == 1.0 else 3
    add_karma(
        db, data.userId, "report", karma_points,
        f"回報 {retailer.name} 的 {data.item} 庫存",
        data.retailerId,
    )

    return report


@router.get("/{retailer_id}", response_model=InventoryStatusResponse)
def get_inventory_status(retailer_id: int, db: Session = Depends(get_db)):
    """
    取得某店家的最新庫存狀態
    只取最近 24 小時內的回報，依信心值加權
    """
    cutoff = datetime.utcnow() - timedelta(days=7)

    recent_reports = db.query(InventoryReport).filter(
        InventoryReport.retailerId == retailer_id,
        InventoryReport.createdAt >= cutoff,
    ).order_by(InventoryReport.createdAt.desc()).all()

    # 依品項分組，取信心值最高的狀態
    items_map: dict[str, dict] = {}
    for r in recent_reports:
        if r.item not in items_map or r.confidence > items_map[r.item].get("confidence", 0):
            items_map[r.item] = {
                "item": r.item,
                "status": r.status,
                "confidence": r.confidence,
                "updatedAt": r.createdAt.isoformat(),
            }

    return InventoryStatusResponse(
        retailerId=retailer_id,
        items=list(items_map.values()),
    )


@router.get("/{retailer_id}/merchant")
def get_merchant_inventory(retailer_id: int, db: Session = Depends(get_db)):
    """
    取得商家官方庫存狀態（公開 API）
    回傳商家自行標記的各品項庫存狀態
    """
    from app.model.merchant_inventory import MerchantInventory

    items = db.query(MerchantInventory).filter(
        MerchantInventory.retailerId == retailer_id,
        MerchantInventory.status != "未設定",
    ).order_by(MerchantInventory.itemPrice.desc()).all()

    return {
        "retailerId": retailer_id,
        "items": [
            {
                "itemName": item.itemName,
                "itemPrice": item.itemPrice,
                "status": item.effective_status,
                "scratchcardId": item.scratchcardId,
                "updatedAt": item.updatedAt.isoformat() if item.updatedAt else None,
            }
            for item in items
        ],
    }


@router.get("/scratchcard/{scratchcard_id}/nearby")
def get_nearby_stock(
    scratchcard_id: int,
    lat: float = None,
    lng: float = None,
    db: Session = Depends(get_db),
):
    """
    依刮刮樂 ID 查詢有庫存的店家（公開 API）
    傳入使用者座標可依距離排序
    """
    from app.model.merchant_inventory import MerchantInventory

    # 查詢所有有此刮刮樂庫存且非「售完」、非「未設定」的紀錄
    stock_records = db.query(MerchantInventory).filter(
        MerchantInventory.scratchcardId == scratchcard_id,
        MerchantInventory.status.in_(["充足", "少量"]),
    ).all()

    # 取得對應的經銷商資訊
    retailer_ids = list(set(r.retailerId for r in stock_records))
    if not retailer_ids:
        return {"scratchcardId": scratchcard_id, "stores": []}

    retailers = db.query(Retailer).filter(
        Retailer.id.in_(retailer_ids),
        Retailer.isActive == True,
    ).all()

    retailer_map = {r.id: r for r in retailers}

    results = []
    for record in stock_records:
        # 動態判斷過濾
        effective_status = record.effective_status
        if effective_status not in ("充足", "少量"):
            continue

        retailer = retailer_map.get(record.retailerId)
        if not retailer:
            continue

        store_info = {
            "retailerId": retailer.id,
            "retailerName": retailer.name,
            "address": retailer.address,
            "city": retailer.city or "",
            "district": retailer.district or "",
            "lat": retailer.lat,
            "lng": retailer.lng,
            "status": effective_status,
            "updatedAt": record.updatedAt.isoformat() if record.updatedAt else None,
            "isClaimed": retailer.isClaimed,
            "merchantTier": getattr(retailer, "merchantTier", "basic"),
        }

        # 計算距離（若有使用者座標）
        if lat is not None and lng is not None and retailer.lat and retailer.lng:
            store_info["distance"] = round(haversine_distance(lat, lng, retailer.lat, retailer.lng))
        else:
            store_info["distance"] = None

        results.append(store_info)

    # 依距離排序（有距離的在前，無距離的在後）
    results.sort(key=lambda x: (x["distance"] is None, x["distance"] or 0))

    return {
        "scratchcardId": scratchcard_id,
        "stores": results,
    }


@router.get("/scratchcards/search")
def search_scratchcards_public(
    q: str = "",
    db: Session = Depends(get_db),
):
    """
    公開搜尋刮刮樂款式（排除已過兌獎期限），
    供一般使用者回報庫存時使用
    """
    import re
    from app.model.database import Scratchcard

    today = datetime.now()
    all_cards = db.query(Scratchcard).all()
    results = []

    for card in all_cards:
        # 排除過期款式（redeemDeadline 為民國年格式如「114年06月30日」）
        if card.redeemDeadline:
            match = re.match(r"(\d+)年(\d+)月(\d+)日", card.redeemDeadline)
            if match:
                roc_year = int(match.group(1))
                m = int(match.group(2))
                d = int(match.group(3))
                western_year = roc_year + 1911
                try:
                    deadline = datetime(western_year, m, d)
                    if deadline < today:
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
        })

    results.sort(key=lambda x: x["price"], reverse=True)
    return results[:50]


@router.post("/retailer/{retailer_id}/exposure")
def record_retailer_exposure(retailer_id: int, db: Session = Depends(get_db)):
    """紀錄店家在「附近庫存」被曝光的次數"""
    from app.model.retailer import Retailer
    from fastapi import HTTPException
    
    retailer = db.query(Retailer).filter(Retailer.id == retailer_id).first()
    if not retailer:
        raise HTTPException(status_code=404, detail="店家不存在")
    
    retailer.nearbyInventoryCount = (retailer.nearbyInventoryCount or 0) + 1
    db.commit()
    return {"status": "ok", "exposureCount": retailer.nearbyInventoryCount}

