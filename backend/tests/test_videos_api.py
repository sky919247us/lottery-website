"""
YouTube 影片 API 端點測試
測試 GET /api/videos
"""

import json
import os
from pathlib import Path


class TestVideosApi:
    """GET /api/videos"""

    def test_videos_returns_list(self, client):
        """影片端點應回傳列表（可能為空或有資料）"""
        resp = client.get("/api/videos")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

    def test_videos_with_seed_data(self, client, tmp_path):
        """有 seed 資料時應回傳影片列表"""
        # NOTE: 此測試依賴 data/videos.json 是否存在
        # 如果檔案存在，驗證回傳格式；不存在則回傳空陣列
        resp = client.get("/api/videos")
        assert resp.status_code == 200
        data = resp.json()

        if len(data) > 0:
            # 驗證欄位結構
            video = data[0]
            assert "url" in video
            assert "title" in video
