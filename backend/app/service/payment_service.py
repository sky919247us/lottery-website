import os
import time
import json
import urllib.parse
import hashlib
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad

# 藍新金流 (NewebPay) 環境變數
MERCHANT_ID = os.getenv("NEWEBPAY_MERCHANT_ID", "TEST_MERCHANT_ID")
HASH_KEY = os.getenv("NEWEBPAY_HASH_KEY", "TEST_HASH_KEY_1234567890123456")
HASH_IV = os.getenv("NEWEBPAY_HASH_IV", "TEST_HASH_IV_123")
PAYMENT_URL = os.getenv(
    "NEWEBPAY_URL", "https://ccore.newebpay.com/MPG/mpg_gateway"
)  # 預設為測試環境 ccore

def _get_aes_cipher():
    key = HASH_KEY.encode("utf-8")
    iv = HASH_IV.encode("utf-8")
    return AES.new(key, AES.MODE_CBC, iv)

def encrypt_trade_info(trade_info: str) -> str:
    cipher = _get_aes_cipher()
    padded_data = pad(trade_info.encode("utf-8"), AES.block_size)
    encrypted = cipher.encrypt(padded_data)
    return encrypted.hex()

def decrypt_trade_info(encrypted_hex: str) -> dict:
    cipher = _get_aes_cipher()
    encrypted_bytes = bytes.fromhex(encrypted_hex)
    decrypted_padded = cipher.decrypt(encrypted_bytes)
    decrypted = unpad(decrypted_padded, AES.block_size).decode("utf-8")
    
    # NewebPay 回傳的 TradeInfo 解密後為 Query string 或是 JSON 字串，通常是 Query String，
    # 但依據文件如果傳 Content-Type: application/json 會回傳 JSON。這裡我們嘗試解 JSON。
    try:
        data = json.loads(decrypted)
        return data
    except Exception:
        # Fallback to query string parse
        parsed = urllib.parse.parse_qsl(decrypted)
        return dict(parsed)

def generate_sha256(encrypted_trade_info: str) -> str:
    original = f"HashKey={HASH_KEY}&{encrypted_trade_info}&HashIV={HASH_IV}"
    return hashlib.sha256(original.encode("utf-8")).hexdigest().upper()

def create_mpg_data(order_no: str, amount: int, item_desc: str, email: str, return_url: str, notify_url: str):
    """
    產生傳送給藍新 MPG 頁面所需的表單資料
    """
    trade_info_dict = {
        "MerchantID": MERCHANT_ID,
        "RespondType": "JSON",
        "TimeStamp": str(int(time.time())),
        "Version": "2.0",
        "MerchantOrderNo": order_no,
        "Amt": amount,
        "ItemDesc": item_desc,
        "Email": email,
        "ReturnURL": return_url,
        "NotifyURL": notify_url,
        "LoginType": 0,
        "CREDIT": 1,
    }
    
    # 先將 Dict 轉為 Query String
    trade_info_qs = urllib.parse.urlencode(trade_info_dict)
    
    # AES 加密
    encrypted_trade_info = encrypt_trade_info(trade_info_qs)
    
    # SHA256 雜湊
    trade_sha = generate_sha256(encrypted_trade_info)
    
    return {
        "MerchantID": MERCHANT_ID,
        "TradeInfo": encrypted_trade_info,
        "TradeSha": trade_sha,
        "Version": "2.0",
        "PaymentUrl": PAYMENT_URL
    }
