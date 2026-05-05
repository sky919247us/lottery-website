# SHOPLINE Payments 串接進度紀錄

> 最後更新：2026-05-05

## 整體狀態
**95% 完成** — Server API + Webhook 驗章皆已 end-to-end 跑通，剩 `trade.refund.succeeded` 退款 webhook 自動降級驗收。

---

## 已完成 ✅

### 1. 後端骨架
- `backend/app/service/slp_client.py`
  - SLP API client (POST 結帳 / 查詢 / 退款)
  - Webhook 驗章（已確認演算法 — 見下節）
- `backend/app/api/payment_slp.py`
  - `GET  /api/payment/slp/claim/{id}/checkout-url` 取結帳連結
  - `POST /api/payment/slp/create` 進階建單（備用）
  - `POST /api/payment/slp/webhook` 接事件 + 升級/降級邏輯
- `app/main.py` 已掛載 router

### 2. 前端整合
- `frontend/src/admin/api.ts` `fetchCheckoutUrl()` 改打 SLP endpoint
  - 注意：因 SLP endpoint 在 `/api/payment/slp/...` 而非 `/api/admin/...` 下，
    繞過 adminApi baseURL prefix，用絕對路徑呼叫
- `frontend/src/components/PlanCard.tsx` 同步更新（雖然實際入口在 MerchantDashboard）

### 3. 商家權限分級（PRO gate）
- 側邊欄「專屬頁面」非 PRO 不顯示
- 「店鋪公告」textarea 非 PRO 鎖定 + 顯示「PRO 限定」徽章
- `/admin/merchant/store-page` 直接 URL 進入也會被 redirect
- 後端 `update_my_store` 拒絕非 PRO 寫入 `announcement`
- `store_page.py` 寫入端點原本就有 PRO check

### 4. SLP API 規格已校準
| 規則 | 確認結果 |
|---|---|
| Server API 認證 | 不需 HMAC，僅 `merchantId / apiKey / requestId` 三個 header |
| `amount.value` | **以「分」為單位**（TWD 也要 ×100，如 1680 元 → 168000） |
| `allowPaymentMethodList` | PascalCase: `CreditCard / ApplePay / ChaileaseBNPL / VirtualAccount / JKOPay` |
| `mode` | `regular` |
| 必填 | `referenceId / amount / returnUrl / mode / allowPaymentMethodList / order(含 products + shipping) / customer(含 type + personalInfo) / billing(含 address) / client.ip` |

### 5. Webhook 驗章演算法已破解
透過 `backend/scripts/slp_sign_solver.py` 暴力比對找到：
```
message = f"{timestamp}.".encode() + raw_body_bytes
sign    = HMAC-SHA256(SLP_SIGN_KEY 字串, message).hexdigest()
```
- header 名稱：`sign / timestamp / requestid / merchantid / idempotentkey`
- timestamp 為**毫秒**（13 位數字）
- payload 內欄位用 `type` 而非 `eventType`
- `data.referenceId` 在 `session.succeeded` 才有；其他事件用 `data.order.customer.referenceCustomerId`（= claim_id）做 fallback

### 6. 真實付款測試已通
| 項目 | 結果 |
|---|---|
| 建立 session | ✅ 200 OK 回 sessionUrl |
| 跳轉 SLP 結帳頁 | ✅ 商品名 + NT$1,680 顯示正確 |
| 真信用卡刷 NT$1,680 + 3DS | ✅ 付款成功 |
| `session.succeeded` webhook | ✅ 進入後升級 claim_id=13 → PRO |
| 前端顯示「專業版 · 到期 2027/5/5」 | ✅ |
| 「店鋪公告」textarea 解鎖 + 側邊欄出現「專屬頁面」 | ✅ |

### 7. 其他附帶處理
- 主爬蟲 cron 由 `01:00 UTC` 改為 `01:10 UTC`（台灣 09:10），避開台彩 09:00 上架的競態
- 麻將大賓果 (5146) / 金鑽999 (5147) 兩款新刮刮樂手動觸發爬蟲後成功入庫

---

## 待完成 ⏳

### 1. ⏳ 退款 webhook 自動降級驗收（等 SLP 送）
- 已申請退刷（NT$1,680，台灣時間 2026-05-05 13:56:59）
- SLP 後台顯示「退款中」（13:56 至少 1 hr 後仍同狀態）
- 卡別 Visa BUSINESS / 發卡行 CHINATRUST，預期數小時 ~ 1 工作日內完成
- 等 `trade.refund.succeeded` 進來
- 預期看到 log：
  ```
  SLP webhook event=trade.refund.succeeded ...
  從 customer.referenceCustomerId 解析 claim_id=13
  [SLP] ⚠️ PRO 已退款降級 claim=13
  ```
- DB 應自動變回 `tier=basic, paymentStatus=refunded`

### 2. 待修小雜訊（不影響服務）
- log 重複報 `column "isactive" does not exist`（索引建立 case 錯誤）
- log 訊息「APScheduler 已啟動，每日 09:00 (台灣時間)」未跟著 cron 改成 09:10

### 3. `.env` 設定 `FRONTEND_URL=https://i168.win`
- 目前付完款導回 `localhost:5173`（VPS 的 .env 沒設或寫錯）
- 不影響功能（升級依賴 webhook 不依賴 returnUrl），僅 UX

### 4. 完成後保險措施（建議）
- 把 `slp_sign_solver.py` 從 git 移除或加 `.gitignore`（含 prod sign_key）
- 寫一份小 README 說明 webhook 簽章演算法（給未來的自己 / 同事）

---

## 環境變數（VPS `.env`）
```
SLP_MERCHANT_ID=7499895708842198260
SLP_API_KEY=sk_product_cf4089c4d95b4280b091989c583ca17d
SLP_SIGN_KEY=89e3c467a4cf40178a9743fe4f884b4d
SLP_BASE_URL=https://api.shoplinepayments.com
SLP_SIGN_ALGO=hmac_sha256_sorted_body  # 已棄用，可刪
FRONTEND_URL=https://i168.win  # 待補
```

---

## 重要 commit 記錄
| commit | 內容 |
|---|---|
| `dfd420b` | 新增 SLP 串接骨架 |
| `7ba9420` | 對齊 MerchantClaim 架構 |
| `a7d2851` | 對齊官方 PHP 範例（移除多餘 sign / 補欄位） |
| `1989c52` | 補 order.shipping + billing.address |
| `3999b18` | amount.value 改用 cents |
| `e473d0a` | MerchantDashboard 升級按鈕改打 SLP |
| `75997ab` | 商家專屬頁面 / 店鋪公告 PRO gate |
| `e7f7b4c` | webhook debug dump（已還原） |
| `4ece98d` | webhook 簽章演算法確定 + 還原強制驗章 |

---

## 已知 SLP webhook 事件結構

### `session.succeeded` (含 referenceId 主索引)
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
      "customer": {"referenceCustomerId": "13"},  // = claim_id
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
