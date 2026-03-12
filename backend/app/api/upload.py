"""
圖片上傳 API 路由
處理商家認領等需上傳圖片之功能
"""
import os
import uuid
from pathlib import Path

from fastapi import APIRouter, File, UploadFile, HTTPException

router = APIRouter(prefix="/api/upload", tags=["上傳"])

# 以專案根目錄下的 uploads 資料夾存放
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png"}

@router.post("", response_model=dict, status_code=201)
async def upload_image(file: UploadFile = File(...)):
    """上傳單一圖片 (限制 5MB 以下之 JPG/PNG)"""
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="只允許上傳 .jpg 或 .png 格式的圖片")
    
    # 讀取檔案以檢查大小
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="檔案大小不能超過 5MB")
        
    # 產生安全且唯一的檔名
    new_filename = f"{uuid.uuid4().hex}{ext}"
    save_path = UPLOAD_DIR / new_filename
    
    with open(save_path, "wb") as f:
        f.write(content)
        
    # 回傳存取路徑，對應 main.py Mount 的 /uploads
    url = f"/uploads/{new_filename}"
    return {"status": "ok", "url": url}
