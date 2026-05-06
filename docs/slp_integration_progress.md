# SHOPLINE Payments 串接進度紀錄

> 最後更新：2026-05-06

## 整體狀態
**98% 完成** — V1-V10 + V7 + 多店帳號管理全部驗收 OK。剩 V11 退款 webhook 自動降級（等 SLP 退款流程完成 1-3 工作日）+ V12-V18 待用戶有空時驗。

---

## 驗收進度（V1-V18）

| Phase | # | 項目 | 狀態 |
|---|---|---|---|
| 1 | V1 | LINE 登入 | ✅ |
| 1 | V2 | 認領店家 | ✅ |
| 1 | V3 | 超管審核 | ✅ |
| 1 | V4 | 商家後台首登 | ✅ |
| 2 | V5 | 第 1 家升級 PRO（真刷 NT$1,680 + 3DS）| ✅ |
| 2 | V6 | 公開店家頁可訪問 | ✅ |
| 2 | V7 | 公告顯示在地圖 | ✅（修復：地圖 marker 端點原本沒回 announcement / tierExpireAt） |
| 3 | V8 | 多店認領 | ✅ |
| 3 | V9 | 多店切換器顯示 | ✅ |
| 3 | V10 | 第 2 家獨立升級 | ✅ |
| 4 | V11 | 退款 webhook 自動降級 | ⏳ 等 SLP 處理完退款 |
| 4 | V12 | 超管手動升降級 | ⏸ 待驗 |
| 4 | V13 | 過期自動降級排程（每小時 :15）| ⏸ 待驗 |
| 4 | V14 | 續約累加到期日 | ⏸ 待驗 |
| 5 | V15-V18 | 權限與安全（webhook 偽造、403、409、付款取消等）| ⏸ 待驗 |

---

## 已完成功能 ✅

### 1. 後端骨架
- `backend/app/service/slp_client.py` — SLP API client + webhook 驗章
- `backend/app/api/payment_slp.py` — checkout / webhook / refund 端點
- `backend/app/service/tier_service.py` — `is_retailer_pro()` + `expire_overdue_pro()`
- `app/main.py` 已掛載 router + 加每小時 :15 過期降級排程

### 2. 前端整合
- `frontend/src/admin/api.ts` `fetchCheckoutUrl()` 改打 SLP（用絕對路徑繞過 adminApi prefix）
- `frontend/src/admin/utils/tier.ts` `isStorePro()` helper（過期感知）
- `frontend/src/components/PlanCard.tsx` 同步更新
- `frontend/src/admin/pages/MerchantDashboard.tsx` tier 徽章 + 升級按鈕都改用 `isStorePro()`
- `frontend/src/pages/CommunityMap.tsx` 地圖 popup 顯示 PRO 公告（修復 V7）

### 3. 商家權限分級（PRO gate）
| 元件 | 行為 |
|---|---|
| 側邊欄「專屬頁面」 | 非 PRO 不顯示 |
| 「店鋪公告」textarea | 非 PRO 鎖定 + 顯示「PRO 限定」徽章 |
| `/admin/merchant/store-page` 直接 URL | 非 PRO `<Navigate>` 踢回 dashboard |
| 後端 `update_my_store` | 非 PRO 寫入 `announcement` 自動忽略 |
| 後端 `store_page.py` 寫入端點 | 既有 PRO check + 改用 `is_retailer_pro()` 含過期檢查 |

### 4. 多店架構 ✅
- 後端 `_admin_to_dict` 對 MERCHANT 角色多回傳 `stores: [{retailerId, retailerName, tier, proExpiresAt, tierExpireAt}, ...]`
- `AdminUpdateRequest` 新增 `targetRetailerId` 欄位
- `update_admin_user` 收到 targetRetailerId 後，PRO 升降級作用於指定店；做 ownership 檢查
- 前端 AdminAccounts 多店帳號展開為 N 列（`rowId = adminId-retailerId`，DataGrid 用 `getRowId`）
- 「關聯店家」欄顯示 #ID + 店名；「PRO 到期日」欄取該列店家的數值
- 編輯多店行 → 對話框鎖定店家欄位 + 明示「僅作用於此店」+ 隱藏店家搜尋
- payload 帶 `targetRetailerId`，後端僅更新該店

### 5. 過期自動降級
- `tier_service.expire_overdue_pro()` — 物理降級（tier→basic, paymentStatus→expired, expireAt→null）
- 排程每小時 :15 跑一次
- 前端 `isStorePro()` 即時反映過期狀態，不用等排程

### 6. 續約累加（不覆蓋）
- `payment_slp.py` upgrade 改為 `MAX(現有到期日, now) + 方案天數`
- 冪等改為 `lemonsqueezyOrderId == reference_id` 對比（同一筆 webhook 重送會跳過，新訂單會接受）
- 由 webhook amount 反查 `PLAN_TABLE`（未來加方案不用改 webhook）

### 7. SLP API 規格已校準
| 規則 | 確認結果 |
|---|---|
| Server API 認證 | 不需 HMAC，僅 `merchantId / apiKey / requestId` |
| `amount.value` | 以「分」為單位（TWD 也要 ×100） |
| `allowPaymentMethodList` | PascalCase: `CreditCard / ApplePay / ChaileaseBNPL / VirtualAccount / JKOPay` |
| `mode` | `regular` |
| 必填 | `referenceId / amount / returnUrl / mode / allowPaymentMethodList / order(含 products + shipping) / customer(含 type + personalInfo) / billing(含 address) / client.ip` |

### 8. Webhook 驗章演算法（已破解）
```
message = f"{timestamp}.".encode() + raw_body_bytes
sign    = HMAC-SHA256(SLP_SIGN_KEY 字串, message).hexdigest()
```
- header：`sign / timestamp / requestid / merchantid / idempotentkey`
- timestamp 為**毫秒**（13 位）
- payload 用 `type` 而非 `eventType`
- `data.referenceId` 在 `session.succeeded` 才有；其他事件用 `data.order.customer.referenceCustomerId`（= claim_id）

### 9. 其他附帶
- 主爬蟲 cron 由 01:00 UTC 改為 01:10 UTC（台灣 09:10）
- log 雜訊清掉（PostgreSQL camelCase 索引 / 啟動訊息字串對齊）
- 麻將大賓果 (5146) / 金鑽999 (5147) 已入庫

---

## 待完成 ⏳

### 1. ⏳ V11 退款 webhook 自動降級（等 SLP）
- 已申請退刷（NT$1,680，2026-05-05 13:56:59）
- SLP 退款流程：「退款中」 → 卡組織 → 發卡行 → 通知 SLP → 觸發 `trade.refund.succeeded` webhook
- 預期 log（驗證點）：
  ```
  ============================================================
  REFUND BODY (xxx bytes): {...}  ← 預留 debug dump
  ============================================================
  SLP webhook event=trade.refund.succeeded ...
  從 customer.referenceCustomerId 解析 claim_id=13
  [SLP] ⚠️ PRO 已退款降級 claim=13
  ```
- 若 webhook body 解析不出 claim_id，會看到 `找不到 claim_id, 忽略` → 用 dump 出來的 body 補解析

### 2. ⏸ V12-V18 待用戶有空時驗
詳細步驟見對話歷史「完整驗證清單」段落。

### 3. 待修小細節
- VPS `.env` 設 `FRONTEND_URL=https://i168.win`（目前付完款導回 localhost:5173）
- 把 `slp_sign_solver.py` 從 git 移除或加 `.gitignore`（含 prod sign_key 範例）
- 寫一份小 README 說明 webhook 簽章演算法
- 多店帳號的 reset password / delete 操作目前作用於 admin 整體（所有店共用一組密碼），UI 上沒顯式說明，未來可加 tooltip

---

## 環境變數（VPS `.env`）
```
SLP_MERCHANT_ID=7499895708842198260
SLP_API_KEY=sk_product_cf4089c4d95b4280b091989c583ca17d
SLP_SIGN_KEY=89e3c467a4cf40178a9743fe4f884b4d
SLP_BASE_URL=https://api.shoplinepayments.com
FRONTEND_URL=https://i168.win  # 待補
```

---

## 重要 commit 時間軸

| commit | 內容 |
|---|---|
| `dfd420b` | 新增 SLP 串接骨架 |
| `7ba9420` | 對齊 MerchantClaim 架構 |
| `a7d2851` | 對齊官方 PHP 範例（移除多餘 sign / 補欄位） |
| `1989c52` | 補 order.shipping + billing.address |
| `3999b18` | amount.value 改用 cents |
| `e473d0a` | MerchantDashboard 升級按鈕改打 SLP |
| `75997ab` | 商家專屬頁面 / 店鋪公告 PRO gate |
| `e7f7b4c` | webhook debug dump（用以反推簽章） |
| `4ece98d` | webhook 簽章演算法確定 + 還原強制驗章 |
| `6a23b96` | 修正手動降級失效 + refund webhook 找不到 claim_id |
| `5dbe6af` | PRO 過期自動視為 basic + 每小時排程物理降級 |
| `f661953` | 索引欄名加引號 + 啟動訊息字串對齊 |
| `c646136` | 續約累加到期日 (#17) |
| `02aaf9d` | merchant-dashboard tier 徽章與升級按鈕加入過期檢查 |
| `5b1548a` | 公開地圖顯示 PRO 商家公告 + 過期感知 |
| `65271cc` | 後台帳號列表顯示所有關聯店家 (多店) |
| `377ad9a` | 多店帳號改為一店一列, 支援逐店 PRO 升降級 |

---

## 已知 SLP webhook 事件結構

### `session.succeeded` (含 referenceId)
```json
{
  "type": "session.succeeded",
  "data": {
    "referenceId": "PRO_CLAIM_13_1777959947",
    "sessionId": "se_22012605057510016054786266211",
    "status": "SUCCEEDED",
    "amount": {"value": 168000, "currency": "TWD"},
    "paidAmount": {"value": 168000, "currency": "TWD"},
    "returnURL": "...",
    "sessionUrl": "...",
    "paymentDetails": [...]
  },
  "id": "...",
  "created": 1777960408000
}
```

### `trade.succeeded` (無 referenceId, 用 customer.referenceCustomerId)
```json
{
  "type": "trade.succeeded",
  "data": {
    "actionType": "SDK",
    "status": "SUCCEEDED",
    "tradeOrderId": "...",
    "referenceOrderId": "RL01...",
    "order": {
      "amount": {...},
      "customer": {"referenceCustomerId": "13"},
      "merchantId": "...",
      "referenceOrderId": "..."
    },
    "payment": {
      "creditCard": {"last4": "1874", "brand": "Visa", ...},
      "paymentMethod": "CreditCard",
      ...
    }
  }
}
```

### `trade.refund.succeeded` (待收到第一筆驗證結構)
- 預留 debug dump，收到時自動 log 完整 body
- 解析策略：先試 `data.referenceId`，再試 `data.order.customer.referenceCustomerId`，再用 `referenceOrderId` 反查
