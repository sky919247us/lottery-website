# SHOPLINE Payments 串接進度紀錄

> 完成日期：2026-05-07
> 狀態：**100% 完成（V11 退款 code review 驗收，待真實客戶退款再核對）**

---

## 驗收總表（V1-V18）

| Phase | # | 項目 | 狀態 |
|---|---|---|---|
| 1 | V1 | LINE 登入 | ✅ |
| 1 | V2 | 認領店家 | ✅ |
| 1 | V3 | 超管審核 | ✅ |
| 1 | V4 | 商家後台首登 | ✅ |
| 2 | V5 | 第 1 家升級 PRO（真刷 NT$1,680 + 3DS） | ✅ |
| 2 | V6 | 公開店家頁可訪問 | ✅ |
| 2 | V7 | 公告顯示在地圖 | ✅ |
| 3 | V8 | 多店認領 | ✅ |
| 3 | V9 | 多店切換器顯示 | ✅ |
| 3 | V10 | 第 2 家獨立升級 | ✅ |
| 4 | V11 | 退款 webhook 自動降級 | ✅ code review（待真實客戶退款核對） |
| 4 | V12 | 超管手動升降級 | ✅ |
| 4 | V13 | 權限旁路測試（403） | ✅ |
| 5 | V14 | 續約累加到期日 | ✅ |
| 5 | V15 | webhook 偽造拒絕 | ✅ |
| 5 | V16 | 非 PRO 寫專屬頁面被擋 | ✅ |
| 5 | V17 | PRO 中再付款（已修為允許續約） | ✅ |
| 5 | V18 | 取消付款不誤升級 | ✅ code review |

---

## 已交付功能

### 核心金流串接
- SLP API client（`backend/app/service/slp_client.py`）
- Server API：建立 session / 查詢 / 退款
- Webhook：`/api/payment/slp/webhook` 含驗章 + 事件分流

### 商家後台
- 「立即升級 PRO」按鈕（basic / 過期狀態）
- 「續約 PRO」按鈕（PRO 中，含預告新到期日）
- 永久 PRO 不顯示按鈕
- 多店架構（切換器 + 帳號管理一店一列）
- PRO 限定功能 gate（專屬頁面 / 店鋪公告）
- 過期感知 PRO 判斷（前後端一致）

### 排程
- 每小時 :15 — 過期自動物理降級
- 每天 10:00（台灣）— LINE 到期提醒（30/21/14/7/3/1 天前）

### 公開展示
- 地圖泡泡顯示 PRO 商家公告 + 設施標籤
- 公開店家頁（`/store/{id}`，PRO 限定）

---

## SLP API 規格（已校準）

### 建立結帳 session
**Endpoint**: `POST /api/v1/trade/sessions/create`
**Auth headers**（無 HMAC）:
- `merchantId / apiKey / requestId / Content-Type: application/json`

**Body 必填**:
- `referenceId / mode='regular' / amount.value (cents)`
- `returnUrl / allowPaymentMethodList: ['CreditCard', 'ApplePay', ...]`
- `order { products: [...], shipping: {...} }`
- `customer { type:'0', personalInfo:{firstName,lastName,email,phone} }`
- `billing { personalInfo, address }`
- `client.ip`

**注意**：`amount.value` 為**最小單位（cents）**，TWD 也要 ×100（NT$1,680 → 168000）

### Webhook 簽章
```
message = f"{timestamp}.".encode() + raw_body_bytes
sign    = HMAC-SHA256(SLP_SIGN_KEY 字串, message).hexdigest()
```
- header: `sign / timestamp / requestid / merchantid / idempotentkey`
- timestamp 為**毫秒**（13 位）
- payload 用 `type` 而非 `eventType`

### Webhook 事件處理規則
| 事件 | 行為 |
|---|---|
| `trade.succeeded` | 寫入 `claim.slpTradeOrderId`（退款反查用），**不升級** |
| `session.succeeded` | 升級 / 續約（用 `data.referenceId` 解 PRO_CLAIM_X_ts）|
| `trade.refund.succeeded` | 用 `data.tradeOrderId` 反查 claim 降級 |
| `session.expired / trade.failed / trade.cancelled` | fall through 不變更 DB |

### 升級邏輯（含續約累加）
```python
base = MAX(claim.proExpiresAt, now)
new_expire = base + plan_days
```
- 冪等：`lemonsqueezyOrderId == reference_id` 對比（同 webhook 重送跳過）
- 永久 PRO（year >= 9999）擋重複付款 409

---

## 環境變數（VPS `.env`）

```
SLP_MERCHANT_ID=7499895708842198260
SLP_API_KEY=sk_product_xxxxx
SLP_SIGN_KEY=xxxxxxxxxx
SLP_BASE_URL=https://api.shoplinepayments.com
FRONTEND_URL=https://i168.win  # 待補（不影響功能，只影響付款後 returnUrl 跳轉）
```

---

## 重要 commit 時間軸

| commit | 內容 |
|---|---|
| `dfd420b` | 新增 SLP 串接骨架 |
| `7ba9420` | 對齊 MerchantClaim 架構 |
| `a7d2851` | 對齊官方 PHP 範例 |
| `1989c52` | 補 order.shipping + billing.address |
| `3999b18` | amount.value 改用 cents |
| `e473d0a` | MerchantDashboard 升級按鈕改打 SLP |
| `75997ab` | 商家權限分級（PRO gate） |
| `4ece98d` | webhook 簽章演算法確定 |
| `5dbe6af` | PRO 過期自動視為 basic + 排程 |
| `c646136` | 續約累加到期日 |
| `5b1548a` | 地圖顯示 PRO 商家公告 |
| `377ad9a` | 多店帳號改為一店一列 |
| `8c9125c` | 移除 PRO 中再付款 409 阻擋 |
| `5867617` | 拆分 trade.succeeded vs session.succeeded |
| `aa5bd0b` | PRO 中也顯示續約按鈕 |
| `0ee1d26` | LINE 到期提醒 30/21/14/7/3/1 天 |
| `1c33557` | 退款被 session.succeeded 誤吃修復 |

---

## 後續維護建議

1. 客戶第一筆真實退款進來時，到 `/var/log/...journalctl` 確認：
   - `[SLP] ⚠️ PRO 已退款降級 claim=X tradeOrderId=...` 出現
   - DB `merchant_claims.id=X` 變 `tier=basic, paymentStatus=refunded`

2. 補 VPS `.env` 加 `FRONTEND_URL=https://i168.win`，使付款後回跳到正式網域

3. 把 `backend/scripts/slp_sign_solver.py` 加入 `.gitignore`（含 prod sign_key 範例值）

4. 多店帳號的 reset password / delete 操作目前作用於 admin 整體（所有店共用一組密碼），UI 上可加 tooltip 說明

5. 若新增方案（月費 / 半年費等）只需擴 `payment_slp.py` 的 `PLAN_TABLE`，webhook 處理會自動依 amount 反查
