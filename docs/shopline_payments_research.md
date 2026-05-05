# SHOPLINE Payments 串接研究筆記

> 來源：https://faq.shoplinepayments.com/faq/developerManagement/  
> 開發者文件：https://docs.shoplinepayments.com/  
> 研究日期：2026-04-30

---

## 一、平台定位

- **SHOPLINE Payments（簡稱 SLP）**：SHOPLINE 品牌的第三方代收付（金流閘道）
- 適用對象：
  - **特店**（一般商家） → 我們屬於這類
  - **平台 / 子特店** → 代為串接別家商店的場景，不適用
- 商家識別碼：`merchantId`

## 二、串接方式（兩種，我們選一種）

| 方式 | 說明 | 我們適用 |
|---|---|---|
| **導轉式（Redirect）** | 後端 API 建立 session → 拿到 `sessionUrl` → 前端導轉到 SLP 結帳頁 → 付款完成導回 `returnUrl` | ✅ **建議優先**（單純、快速、不需處理卡號 PCI-DSS） |
| **內嵌式（Embedded）** | 前端載入 SLP JS SDK，卡號直接在我們頁面輸入 → 後端 API + Webhook | ❌ 工程量大，且 PCI-DSS 合規負擔重 |

> 結論：**用導轉式（Session-based Redirect）**。我們的會員方案訂閱付款場景剛好就是「按一個按鈕跳到金流頁刷卡，回來解鎖會員」，完全契合。

## 三、認證金鑰（在 SLP 後台「設定 → 開發者管理」取得）

| 金鑰 | 用途 | 存放位置 |
|---|---|---|
| **API Key** | 後端 server → SLP API 認證 | `.env`（VPS 後端，絕對不可入 git） |
| **Client Key** | 前端 SDK 用（內嵌式才需要） | 不需要（我們走導轉式） |
| **Sign Key** | Webhook 驗章用 | `.env` |
| **Merchant ID** | 商家識別碼 | `.env` |

- 金鑰最多 5 組，可隨時新增刪除
- 刪除後 24 小時失效（可做 rotation）
- 查看時眼睛圖示 10 秒自動關閉

## 四、API 端點（導轉式核心）

Base URL（待 sandbox / production 確認，先用 docs 推測）：
- Sandbox：`https://sandbox-api.shoplinepayments.com`
- Production：`https://api.shoplinepayments.com`

| 用途 | 端點 | Method |
|---|---|---|
| 建立結帳 session | `/api/v1/trade/sessions/create` | POST |
| 查詢 session 狀態 | `/api/v1/trade/sessions/query` | POST |
| 申請退款 | `/api/trade/refund/` | POST |
| 查詢退款 | `/api/trade/refundQuery/` | POST |

### Request Header（所有 API 共用）

```
merchantId:    <我方商家 ID>
apiKey:        <API Key>
requestId:     <UUID v4，每次唯一>
timestamp:     <Unix timestamp>
sign:          <HMAC 簽章，演算法待 sandbox 實測確認>
Content-Type:  application/json
```

### 建立 Session — Request Body

```json
{
  "referenceId": "我方訂單編號（自定，需唯一）",
  "mode": "regular",
  "amount": { "value": 199, "currency": "TWD" },
  "returnUrl": "https://i168.win/membership/return",
  "allowPaymentMethodList": ["CREDIT_CARD"],
  "order": { "products": [...], "shipping": {...} },
  "customer": {
    "referenceCustomerId": "我方會員 ID",
    "personalInfo": { "name": "...", "email": "..." }
  },
  "client": { "ip": "<使用者 IP>" },
  "billing": { "personalInfo": {...}, "address": {...} },
  "expireTime": null,
  "language": null,
  "paymentMethodOptions": {}
}
```

### 建立 Session — Response

```json
{
  "sessionId": "...",
  "referenceId": "我方訂單編號",
  "status": "CREATED",
  "sessionUrl": "https://checkout.shoplinepayments.com/...",
  "amount": { "value": 199, "currency": "TWD" },
  "createTime": "..."
}
```

→ **拿到 `sessionUrl` 後直接 302 redirect / 前端 `window.location.href`**

## 五、Webhook 事件

### 註冊方式（已確認：後台自助）
SLP 後台「設定 → 開發者管理 → Webhook 管理 → 新增 Webhook」直接設定，**不用寫信申請**。
建立時需填：
- Webhook 名稱
- 接收 URL（必須 https）
- 訂閱事件（勾選）
- **Sign Key**（16-32 位英數字，這把就是 webhook 驗章用的）— 此 Sign Key 由我方自定後存到 SLP，發送 webhook 時 SLP 用它簽章。

### 訂閱事件清單
| 事件 | 說明 |
|---|---|
| `session.succeeded` | 結帳成功 |
| `session.expired` | session 過期 |
| `trade.succeeded` | 交易成功（payment notification） |
| `refund.*` | 退款結果通知 |

### Webhook 接收要求
- 必須 HTTPS
- 收到後回 200 OK，否則會重試（重試機制細節待確認）
- 用 Sign Key 驗章（具體演算法待 sandbox 階段實測）

## 六、Sandbox 測試資源

| 帳號 | 用途 |
|---|---|
| `slpsandbox2@shopline.com` | 主測試帳號（Merchant ID: 2652289079513847808） |
| `slpsandbox2+001~005@shopline.com` | 多商家場景 |
| 共用密碼 | `shoplinePayments123.` |

### 測試卡號

| 網路 | 卡號 | 期限 | CVC |
|---|---|---|---|
| JCB | 3565586700000200 | 03/30 | 484 |
| Visa | 4147633700198405 | 03/30 | 638 |
| MasterCard | 5149147700000300 | 03/30 | 231 |

### 測試規則
- **金額為 3 倍數** → 進入 3DS 流程（會跳模擬頁讓你選成功/失敗）
- **奇數金額** → 直接成功
- **偶數金額**（非 3 倍數）→ 直接失敗

> 開發階段刻意用「99 / 199」這種奇數金額測試成功路徑、用「100 / 200」測失敗路徑、用「99 → 198」中的 3 倍數值測 3DS。

## 七、未抓到 / 待 sandbox 實測確認

1. **簽章 `sign` 演算法**：HMAC SHA256? 欄位排序規則？base64 還是 hex？
2. **錯誤碼清單**
3. **`status` enum 完整值**
4. **Webhook payload 完整結構與簽章驗證範例**
5. **退款 API 完整欄位**
6. **session 建立後的有效時間 / 取消方式**

→ 申請完 sandbox 帳號後，第一支 API 打通後即可從 response 反推。

## 八、本站串接規劃（高階流程）

### 資料表新增
```
payment_orders
├─ id (PK)
├─ user_id          → users
├─ plan_code        → 訂閱方案代碼（free / monthly / yearly）
├─ amount           → INT (TWD)
├─ status           → enum: pending / succeeded / failed / expired / refunded
├─ slp_session_id   → SLP sessionId
├─ slp_reference_id → 我方產生的 UUID（= referenceId 傳給 SLP）
├─ slp_response     → JSON（建立 session 的完整回應）
├─ slp_webhook_log  → JSON 陣列（每次 webhook 的 payload）
├─ created_at
├─ paid_at
└─ expired_at
```

### 端點規劃（FastAPI 後端）
| 端點 | 用途 |
|---|---|
| `POST /api/payments/checkout` | 建立訂單 + 呼叫 SLP create session → 回傳 `sessionUrl` |
| `GET /api/payments/return` | 使用者付完款 SLP 導回的 returnUrl（顯示結果頁） |
| `POST /api/payments/webhook/slp` | SLP 主動推送付款結果（驗章後更新 status + 升級會員） |
| `GET /api/payments/orders/me` | 查我自己的付款紀錄 |
| `POST /api/admin/payments/refund` | 管理員觸發退款 |

### 升級會員流程
1. 使用者點「訂閱年費 NT$1,200」
2. 前端 `POST /api/payments/checkout` → 後端建立 `payment_orders`（status=pending）+ 呼叫 SLP create session
3. 拿到 `sessionUrl` → 前端 redirect
4. 使用者在 SLP 頁面付款
5. **兩條路同時發生**：
   - SLP 導使用者回 `returnUrl`（這條只能信顯示效果，不能信付款結果）
   - SLP 推 webhook 到 `/api/payments/webhook/slp`（**唯一可信來源**）
6. webhook 收到 `session.succeeded` → 驗章 → 更新 status → 升級 `users.plan` 與到期日
7. 使用者重新整理頁面就看到付費功能解鎖

### 安全要點
- **絕不信任 returnUrl 的 query string** — 一律以 webhook 為準
- **webhook 接收做冪等處理**（同一 sessionId 處理過就跳過）
- **referenceId 必須唯一**，且我方產生（防止重放）
- **金額 server 端寫死**（前端不能傳金額，否則被改成 1 元）
- **API Key / Sign Key** 只放 VPS `.env`，絕不送前端，不入 git
- **timestamp 與我方 server 時間差異 > 5 分鐘的 webhook 拒收**

## 九、實作里程碑（建議）

| Phase | 工作 | 預估 |
|---|---|---|
| P1 | 寫信給 SLP 對接申請 sandbox webhook 接收 URL | 0.5h（等對方回） |
| P2 | 拿到 sandbox 帳號 → 後台抓 API Key/Sign Key/Merchant ID | 0.5h |
| P3 | DB migration（payment_orders 表） | 1h |
| P4 | 後端 `/api/payments/checkout` + SLP client（含簽章） | 3h |
| P5 | 後端 `/api/payments/webhook/slp` + 驗章 + 升級會員 | 2h |
| P6 | 前端訂閱頁 + return 頁 | 2h |
| P7 | sandbox 測試（3DS、3 倍數、奇偶金額） | 2h |
| P8 | 申請 production webhook + 切 production 環境變數 | 0.5h |
| P9 | 真實小額測試（NT$1） | 0.5h |

合計約 **12 小時**，分 2-3 天完成。

## 十、開工前確認清單

1. ✅ **Merchant ID**：`7499895708842198260`
2. ✅ **API Key**：`sk_****a17d`（後台複製完整值，存 VPS `.env`）
3. ✅ **Client Key**：`pk_****ebae`（導轉式可暫時用不到）
4. ⏳ **Sign Key**：建立 webhook 時自訂（建議用 `openssl rand -hex 24` 產 48 字元）
5. ⏳ **Webhook URL**：實作完成後在後台新增，URL = `https://api.i168.win/api/payments/webhook/slp`
6. ❓ **Sign 演算法**：仍需從文件 / sandbox 反推（HMAC SHA256 機率最高）— 第一支 API 打通後立刻能驗證

---

> 下一步等你在 SLP 後台抓到 **Merchant ID / API Key / Sign Key** 並把 sandbox webhook 申請寄出後，我們就可以開始 P3 DB migration。
