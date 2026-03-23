# Cloudflare Cache Rules 設定指南

## 目標
減少 `/api/retailers/map-markers` 和 `/api/retailers/map-geojson` 的重複查詢，透過 Cloudflare CDN 快取。

## 設定步驟

### 1. 登入 Cloudflare Dashboard
- 進入 https://dash.cloudflare.com
- 選擇 Zone: **i168.win**
- 左側選單 → **Rules** → **Cache Rules**

### 2. 新增 Cache Rule

#### Rule 1: Map Markers 快取（5 分鐘）
```
條件 (If):
  Request Path contains "/api/retailers/map-markers"

動作 (Then):
  Set Cache Level: Cache Everything
  Browser Cache TTL: 5 minutes
  Edge Cache TTL: 5 minutes
```

#### Rule 2: Map GeoJSON 快取（5 分鐘）
```
條件 (If):
  Request Path contains "/api/retailers/map-geojson"

動作 (Then):
  Set Cache Level: Cache Everything
  Browser Cache TTL: 5 minutes
  Edge Cache TTL: 5 minutes
```

#### Rule 3: 排除 Query Params（確保快取有效）
```
條件 (If):
  Request Path contains "/api/retailers/map-"
  AND Query String does NOT contain "lat" OR "lng"

動作 (Then):
  Set Cache Level: Cache Everything
  Browser Cache TTL: 5 minutes
  Edge Cache TTL: 5 minutes
```

### 3. 測試快取
```bash
# 第一次請求（從來源伺服器）
curl -i https://i168.win/api/retailers/map-markers | grep -i "cf-cache-status"
# 預期: HIT or MISS

# 第二次請求（應該是 HIT）
curl -i https://i168.win/api/retailers/map-markers | grep -i "cf-cache-status"
# 預期: HIT
```

### 4. 監控快取
- Dashboard → **Analytics** → **Cache Analytics**
- 查看緩存率（Cache Ratio）應該 > 50%

## 快取 vs 新鮮度的權衡

| 端點 | TTL | 原因 |
|------|-----|------|
| `/api/retailers/map-markers` | 5 min | 即時位置更新不重要，大多數人看幾秒內的舊資料 |
| `/api/retailers/map-geojson` | 5 min | GeoJSON 資料變化不頻繁 |
| `/api/retailers/nearby` | 60 sec | GPS 依賴查詢，快取已有 |

## 費用影響
- Cloudflare Cache Rules 在 Pro 方案以上可用
- 檢查現有方案是否支援

## 驗證快取是否生效
```python
# backend/main.py 中添加 debug log
@app.get("/api/retailers/map-markers")
def get_map_markers(db: Session = Depends(get_db)):
    import logging
    logging.info("GET /api/retailers/map-markers - 快取命中時不會列印此訊息")
    # ...
```

---

**注意**: 若 lat/lng 查詢參數不同，Cloudflare 會視為不同請求，不快取。
如需快取所有 lat/lng 查詢，需修改後端端點 URL 結構。
