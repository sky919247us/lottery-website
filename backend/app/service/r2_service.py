"""
Cloudflare R2 圖片存儲服務
使用 boto3 S3 相容介面連接 Cloudflare R2
提供圖片上傳（含自動壓縮為 WebP）與刪除功能
"""

import io
import logging
import os
import uuid
from typing import BinaryIO

import boto3
from botocore.config import Config
from PIL import Image

logger = logging.getLogger(__name__)

# 圖片限制常數
MAX_UPLOAD_SIZE = 5 * 1024 * 1024       # 原始檔案最大 5MB
TARGET_MAX_SIZE = 300 * 1024             # 壓縮後目標 ≤ 300KB
MAX_DIMENSION = 1920                     # 最長邊像素上限
WEBP_INITIAL_QUALITY = 85               # WebP 初始壓縮品質
WEBP_MIN_QUALITY = 40                   # WebP 最低品質（避免過度失真）


def _get_r2_client():
    """建立 R2 S3 相容客戶端"""
    account_id = os.getenv("R2_ACCOUNT_ID", "")
    access_key = os.getenv("R2_ACCESS_KEY_ID", "")
    secret_key = os.getenv("R2_SECRET_ACCESS_KEY", "")

    if not all([account_id, access_key, secret_key]):
        raise RuntimeError("R2 環境變數未設定 (R2_ACCOUNT_ID / R2_ACCESS_KEY_ID / R2_SECRET_ACCESS_KEY)")

    return boto3.client(
        "s3",
        endpoint_url=f"https://{account_id}.r2.cloudflarestorage.com",
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        config=Config(signature_version="s3v4"),
        region_name="auto",
    )


def _compress_to_webp(file_data: bytes) -> bytes:
    """
    將圖片轉換為 WebP 格式並壓縮至目標大小
    使用逐步降低品質的策略，直到檔案小於 TARGET_MAX_SIZE
    """
    img = Image.open(io.BytesIO(file_data))

    # 移除 EXIF 中的方向資訊並套用正確方向
    from PIL import ImageOps
    img = ImageOps.exif_transpose(img)

    # 轉為 RGB（WebP 不支援 CMYK 等色彩空間）
    if img.mode in ("RGBA", "LA", "P"):
        # 保留透明度
        img = img.convert("RGBA")
    else:
        img = img.convert("RGB")

    # 縮放至最長邊不超過限制
    w, h = img.size
    if max(w, h) > MAX_DIMENSION:
        ratio = MAX_DIMENSION / max(w, h)
        img = img.resize((int(w * ratio), int(h * ratio)), Image.LANCZOS)

    # 逐步降低品質直到滿足目標大小
    quality = WEBP_INITIAL_QUALITY
    while quality >= WEBP_MIN_QUALITY:
        buffer = io.BytesIO()
        img.save(buffer, format="WEBP", quality=quality, method=4)
        data = buffer.getvalue()
        if len(data) <= TARGET_MAX_SIZE:
            return data
        quality -= 5

    # 若仍然超過（極端情況），回傳最低品質版本
    buffer = io.BytesIO()
    img.save(buffer, format="WEBP", quality=WEBP_MIN_QUALITY, method=4)
    return buffer.getvalue()


def upload_image(
    file_data: bytes,
    retailer_id: int,
    category: str,
) -> tuple[str, str]:
    """
    上傳圖片至 Cloudflare R2

    Args:
        file_data: 原始圖片二進位資料
        retailer_id: 關聯的經銷商 ID
        category: 分類 ("gallery" / "winning_wall" / "banner")

    Returns:
        (public_url, r2_key) 元組

    Raises:
        ValueError: 檔案過大或格式不支援
        RuntimeError: R2 上傳失敗
    """
    if len(file_data) > MAX_UPLOAD_SIZE:
        raise ValueError(f"檔案大小超過上限 ({MAX_UPLOAD_SIZE // 1024 // 1024}MB)")

    # 壓縮並轉換為 WebP
    webp_data = _compress_to_webp(file_data)

    # 產生唯一檔名
    filename = f"{uuid.uuid4().hex}.webp"
    r2_key = f"stores/{retailer_id}/{category}/{filename}"

    # 上傳至 R2
    bucket = os.getenv("R2_BUCKET_NAME", "i168-store-images")
    public_url_base = os.getenv("R2_PUBLIC_URL", "").rstrip("/")

    client = _get_r2_client()
    try:
        client.put_object(
            Bucket=bucket,
            Key=r2_key,
            Body=webp_data,
            ContentType="image/webp",
        )
    except Exception as e:
        logger.error(f"R2 上傳失敗: {e}")
        raise RuntimeError(f"圖片上傳失敗: {e}")

    public_url = f"{public_url_base}/{r2_key}"
    logger.info(f"圖片上傳成功: {r2_key} ({len(webp_data)} bytes)")
    return public_url, r2_key


def delete_image(r2_key: str) -> bool:
    """
    從 Cloudflare R2 刪除圖片

    Args:
        r2_key: R2 物件 Key

    Returns:
        是否刪除成功
    """
    if not r2_key:
        return False

    bucket = os.getenv("R2_BUCKET_NAME", "i168-store-images")
    client = _get_r2_client()

    try:
        client.delete_object(Bucket=bucket, Key=r2_key)
        logger.info(f"圖片刪除成功: {r2_key}")
        return True
    except Exception as e:
        logger.error(f"R2 刪除失敗: {e}")
        return False
