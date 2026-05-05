"""
SLP webhook 簽章演算法暴力求解器
拿 log 中真實 webhook 的 (sign_key / timestamp / requestid / body / 預期 sign)
逐一測試候選演算法，找出哪個吻合。
"""

import hmac
import hashlib
import json

# ========== 從 log 抓的真實值 (修改成你的) ==========
SIGN_KEY = "89e3c467a4cf40178a9743fe4f884b4d"
TIMESTAMP = "1777961280608"   # ms
REQUEST_ID = "00012605057510038408027445739202605"
MERCHANT_ID = "7499895708842198260"
EXPECTED_SIGN = "9e88d5bc5d0158b5f56a179440f5af5043655ae1265ed842a810798b687ff2f8"
# 這是 trade.succeeded 那筆完整 JSON body
RAW_BODY = b'{"data":{"actionType":"SDK","order":{"amount":{"currency":"TWD","value":168000},"createTime":1777960408,"customer":{"referenceCustomerId":"13"},"merchantId":"7499895708842198260","referenceOrderId":"RL0126050506275100237192390734"},"passthrough":"{\\"merchantId\\":\\"7499895708842198260\\",\\"linkOrderId\\":\\"se_22012605057510016054786266211\\",\\"linkPaymentId\\":\\"RL0126050506275100237192390734\\",\\"acquirerType\\":\\"Session\\"}","payment":{"autoCapture":true,"autoConfirm":false,"autoSettle":null,"channelDealId":"7510023734137457196","creditCard":{"bin":"43045187","brand":"Visa","category":"BUSINESS","issuer":"CHINATRUST COMMERCIAL BANK","issuerCountry":"TW","last4":"1874","type":"CREDIT"},"isSettle":false,"paidAmount":{"currency":"TWD","value":168000},"paymentBehavior":"Regular","paymentInstrument":{"savePaymentInstrument":false},"paymentMethod":"CreditCard","paymentSuccessTime":"1777960405137"},"paymentMsg":{"code":"","msg":""},"referenceOrderId":"RL0126050506275100237192390734","sessionId":"se_22012605057510016054786266211","status":"SUCCEEDED","tradeOrderId":"10012605057510023719893602975"},"id":"00012605057510023770242030249202605","type":"trade.succeeded","created":1777960408000}'
# =================================================

def h(msg_bytes: bytes, key_bytes: bytes) -> str:
    return hmac.new(key_bytes, msg_bytes, hashlib.sha256).hexdigest()

key_str = SIGN_KEY.encode()
key_hex = bytes.fromhex(SIGN_KEY)  # 32 hex chars = 16 bytes

body_compact = json.dumps(json.loads(RAW_BODY), separators=(",", ":"), ensure_ascii=False).encode()
body_sorted = json.dumps(json.loads(RAW_BODY), separators=(",", ":"), sort_keys=True, ensure_ascii=False).encode()

candidates = {
    # 純 body
    "key_str + body(raw)": h(RAW_BODY, key_str),
    "key_str + body(compact)": h(body_compact, key_str),
    "key_str + body(sorted)": h(body_sorted, key_str),
    "key_hex + body(raw)": h(RAW_BODY, key_hex),
    "key_hex + body(compact)": h(body_compact, key_hex),
    "key_hex + body(sorted)": h(body_sorted, key_hex),

    # timestamp + body
    "key_str + ts + body(raw)": h(TIMESTAMP.encode() + RAW_BODY, key_str),
    "key_str + ts + body(compact)": h(TIMESTAMP.encode() + body_compact, key_str),
    "key_str + ts.body(raw)": h(f"{TIMESTAMP}.".encode() + RAW_BODY, key_str),
    "key_hex + ts + body(raw)": h(TIMESTAMP.encode() + RAW_BODY, key_hex),
    "key_hex + ts.body(raw)": h(f"{TIMESTAMP}.".encode() + RAW_BODY, key_hex),

    # requestId + body
    "key_str + reqid + body(raw)": h(REQUEST_ID.encode() + RAW_BODY, key_str),
    "key_hex + reqid + body(raw)": h(REQUEST_ID.encode() + RAW_BODY, key_hex),

    # ts + reqid + body
    "key_str + ts + reqid + body(raw)": h((TIMESTAMP + REQUEST_ID).encode() + RAW_BODY, key_str),
    "key_str + reqid + ts + body(raw)": h((REQUEST_ID + TIMESTAMP).encode() + RAW_BODY, key_str),
    "key_hex + ts + reqid + body(raw)": h((TIMESTAMP + REQUEST_ID).encode() + RAW_BODY, key_hex),
    "key_hex + reqid + ts + body(raw)": h((REQUEST_ID + TIMESTAMP).encode() + RAW_BODY, key_hex),

    # merchantId 加進去
    "key_str + mid + ts + body(raw)": h((MERCHANT_ID + TIMESTAMP).encode() + RAW_BODY, key_str),
    "key_str + ts + mid + body(raw)": h((TIMESTAMP + MERCHANT_ID).encode() + RAW_BODY, key_str),
    "key_hex + mid + ts + body(raw)": h((MERCHANT_ID + TIMESTAMP).encode() + RAW_BODY, key_hex),

    # merchantId + requestId + timestamp + body 排列組合
    "key_str + mid + reqid + ts + body": h((MERCHANT_ID + REQUEST_ID + TIMESTAMP).encode() + RAW_BODY, key_str),
    "key_str + mid + ts + reqid + body": h((MERCHANT_ID + TIMESTAMP + REQUEST_ID).encode() + RAW_BODY, key_str),
    "key_str + ts + mid + reqid + body": h((TIMESTAMP + MERCHANT_ID + REQUEST_ID).encode() + RAW_BODY, key_str),
    "key_hex + mid + reqid + ts + body": h((MERCHANT_ID + REQUEST_ID + TIMESTAMP).encode() + RAW_BODY, key_hex),
    "key_hex + mid + ts + reqid + body": h((MERCHANT_ID + TIMESTAMP + REQUEST_ID).encode() + RAW_BODY, key_hex),
    "key_hex + ts + mid + reqid + body": h((TIMESTAMP + MERCHANT_ID + REQUEST_ID).encode() + RAW_BODY, key_hex),

    # 用點 / 換行 / 冒號 分隔
    "key_str + ts:reqid:body": h(f"{TIMESTAMP}:{REQUEST_ID}:".encode() + RAW_BODY, key_str),
    "key_str + reqid:ts:body": h(f"{REQUEST_ID}:{TIMESTAMP}:".encode() + RAW_BODY, key_str),
    "key_str + ts.reqid.body": h(f"{TIMESTAMP}.{REQUEST_ID}.".encode() + RAW_BODY, key_str),
}

print(f"目標 sign: {EXPECTED_SIGN}\n")
for name, sig in candidates.items():
    mark = " ★ MATCH ★" if sig == EXPECTED_SIGN else ""
    print(f"{sig}  <- {name}{mark}")
