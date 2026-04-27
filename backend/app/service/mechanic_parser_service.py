"""
玩法 AI 解析服務（可插拔多供應商）
- 預設使用 Gemini（aistudio.google.com 免費 API）
- 抽象 MechanicParser interface，未來可加 OpenAI / Claude provider
- 支援文字輸入 與 圖片 URL 輸入

環境變數：
  AI_PROVIDER       供應商，預設 "gemini"
  GEMINI_API_KEY    Gemini API key（必填）
  GEMINI_MODEL      模型名稱，預設 "gemini-2.5-flash"

回傳結構（已驗證為合法 JSON）：
{
  "mechanic_types": ["match3", "multiplier"],
  "parsed_tags":    ["match3", "multiplier", "bonus_game", ...],
  "layout_tags":    ["multi_zone"],
  "complexity_score": 3,
  "result_speed":  "instant" | "multi_zone" | "sequence",
  "ai_description": "50 字以內繁中玩法介紹"
}
"""

from __future__ import annotations

import io
import json
import logging
import os
from typing import Any, Optional

logger = logging.getLogger(__name__)


PROMPT = """你是台灣刮刮樂玩法分析師。請分析以下玩法說明，輸出嚴格 JSON。

### 標籤詞彙表
- 配對機制：match3 / match_any / bingo_line
- 特殊符號：multiplier / bonus_symbol / wild
- 附加遊戲：bonus_game / lucky_number / extra_chance
- 比大小：beat_dealer / higher_lower
- 數字加總：sum_target / word_game
- 連線型：crossword / bingo_card / line_match
- 佈局型態：single_zone / multi_zone / full_board
- 結果速度：instant / multi_step / compare

### 輸出 schema（只輸出 JSON，無其他文字）
{
  "mechanic_types": ["..."],         // 主要玩法機制（從前 6 類選擇）
  "parsed_tags":    ["..."],         // 所有適用標籤（含上面任意組合）
  "layout_tags":    ["..."],         // 從佈局型態選 1
  "complexity_score": 1-5,           // 1=刮開即知 5=規則複雜
  "result_speed":  "instant"|"multi_zone"|"sequence",
  "ai_description": "50 字以內繁中介紹"
}
"""


class ParseResult(dict):
    """解析結果（dict 包裝便於 SQLAlchemy 寫入）"""
    pass


# ============================================================
# Provider interface
# ============================================================

class MechanicParser:
    name: str = "base"
    model: str = ""

    def parse_text(self, text: str) -> ParseResult:
        raise NotImplementedError

    def parse_image_url(self, url: str) -> ParseResult:
        raise NotImplementedError


# ============================================================
# Gemini provider
# ============================================================

class GeminiParser(MechanicParser):
    name = "gemini"

    def __init__(self) -> None:
        self.api_key = os.getenv("GEMINI_API_KEY", "").strip()
        self.model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        if not self.api_key:
            raise RuntimeError("GEMINI_API_KEY 未設定")

        try:
            import google.generativeai as genai
        except ImportError as e:
            raise RuntimeError("缺少套件 google-generativeai，請 pip install") from e

        genai.configure(api_key=self.api_key)
        self._genai = genai
        self._model = genai.GenerativeModel(
            self.model,
            generation_config={
                "response_mime_type": "application/json",
                "temperature": 0.2,
            },
        )

    def _call(self, parts: list) -> ParseResult:
        resp = self._model.generate_content(parts)
        text = (resp.text or "").strip()
        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            logger.warning(f"Gemini 回傳非 JSON：{text[:200]}")
            raise RuntimeError(f"AI 回傳格式錯誤：{e}")
        return ParseResult(data)

    def parse_text(self, text: str) -> ParseResult:
        return self._call([PROMPT, "玩法原文：\n" + text])

    def parse_image_url(self, url: str) -> ParseResult:
        # 下載圖片，包成 bytes 給 Gemini
        import requests
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        mime = r.headers.get("content-type", "image/jpeg").split(";")[0]
        image_part = {"mime_type": mime, "data": r.content}
        return self._call([PROMPT, image_part])


# ============================================================
# 工廠
# ============================================================

_PROVIDERS = {
    "gemini": GeminiParser,
}


def get_parser() -> MechanicParser:
    provider = os.getenv("AI_PROVIDER", "gemini").lower()
    cls = _PROVIDERS.get(provider)
    if not cls:
        raise RuntimeError(f"未知 AI_PROVIDER：{provider}")
    return cls()


# ============================================================
# 驗證解析結果
# ============================================================

ALLOWED_RESULT_SPEED = {"instant", "multi_zone", "sequence", "multi_step", "compare"}


def normalize(result: dict) -> dict:
    """把 AI 回傳結果整形為 schema：缺欄補預設、去除多餘欄位、限制範圍"""
    out = {
        "mechanic_types": list(result.get("mechanic_types", []) or []),
        "parsed_tags": list(result.get("parsed_tags", []) or []),
        "layout_tags": list(result.get("layout_tags", []) or []),
        "complexity_score": int(result.get("complexity_score", 0) or 0),
        "result_speed": str(result.get("result_speed", "") or "").lower(),
        "ai_description": str(result.get("ai_description", "") or "").strip(),
    }
    # 限制範圍
    out["complexity_score"] = max(0, min(5, out["complexity_score"]))
    if out["result_speed"] not in ALLOWED_RESULT_SPEED:
        out["result_speed"] = ""
    return out
