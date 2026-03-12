"""
YouTube 開箱影片 API 路由
Phase 1：從 JSON seed 檔案讀取
"""

import json
from pathlib import Path

from fastapi import APIRouter

from app.schema.scratchcard import YouTubeLinkSchema

router = APIRouter(prefix="/api/videos", tags=["YouTube 影片"])

# seed 資料路徑
VIDEOS_JSON_PATH = Path(__file__).parent.parent.parent / "data" / "videos.json"


@router.get("", response_model=list[YouTubeLinkSchema])
def get_videos():
    """取得 YouTube 開箱影片列表"""
    if not VIDEOS_JSON_PATH.exists():
        return []

    with open(VIDEOS_JSON_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    return data
