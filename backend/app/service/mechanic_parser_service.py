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
    """新版使用 google-genai SDK (v1 endpoint), 替代已 deprecated 的 google-generativeai (v1beta)"""
    name = "gemini"

    def __init__(self) -> None:
        self.api_key = os.getenv("GEMINI_API_KEY", "").strip()
        self.model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        if not self.api_key:
            raise RuntimeError("GEMINI_API_KEY 未設定")

        try:
            from google import genai
            from google.genai import types
        except ImportError as e:
            raise RuntimeError("缺少套件 google-genai，請 pip install google-genai") from e

        self._client = genai.Client(api_key=self.api_key)
        self._types = types
        self._gen_config = types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.2,
        )

    def _call(self, contents) -> ParseResult:
        resp = self._client.models.generate_content(
            model=self.model,
            contents=contents,
            config=self._gen_config,
        )
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
        # 下載圖片，包成 Part 給 Gemini
        import requests
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        mime = r.headers.get("content-type", "image/jpeg").split(";")[0]
        image_part = self._types.Part.from_bytes(data=r.content, mime_type=mime)
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


ALLOWED_MECHANIC_TYPES = {
    "match3", "match_any", "bingo_line", "multiplier", "bonus_symbol", "wild",
    "bonus_game", "lucky_number", "extra_chance", "beat_dealer", "higher_lower",
    "sum_target", "word_game", "crossword", "bingo_card", "line_match",
}
ALLOWED_LAYOUT = {"single_zone", "multi_zone", "full_board"}
# parsedTags 允許 mechanicTypes 全集 + 部分子標籤 (但不該含 layout / result_speed)
ALLOWED_PARSED_TAGS = ALLOWED_MECHANIC_TYPES | {"lucky_number", "wild", "bonus_symbol", "multiplier"}

# 同義詞合併 (AI 偶爾發散出非標準命名)
TAG_ALIASES = {
    "bingo_card": "bingo_line",  # 賓果卡 = 賓果連線, 同義合併
}


def _aslist(v) -> list:
    """字串自動包成 [str], None 變 [], 已是 list 原樣回傳.
    避免 list('multi_zone') 把字串拆成字元陣列.
    """
    if v is None:
        return []
    if isinstance(v, str):
        return [v] if v.strip() else []
    if isinstance(v, list):
        return list(v)
    return [str(v)]


def _filter_tags(tags: list, allowed: set) -> list:
    """過濾標籤: 應用同義詞 + 白名單 + 去重 + 保序"""
    seen = set()
    out = []
    for t in tags:
        if not isinstance(t, str):
            continue
        t = t.strip().lower()
        t = TAG_ALIASES.get(t, t)  # 套用同義詞
        if t and t in allowed and t not in seen:
            seen.add(t)
            out.append(t)
    return out


def normalize(result: dict) -> dict:
    """把 AI 回傳結果整形為 DB 欄位 (camelCase) schema:
    - 字串自動包 array (避免 list("multi_zone") 拆字元)
    - 套用同義詞合併
    - 用白名單過濾雜訊 / 串維度錯置
    - 限制 complexityScore 範圍
    """
    def _g(*keys, default=None):
        for k in keys:
            if k in result and result[k] is not None:
                return result[k]
        return default

    raw_mech = _aslist(_g("mechanic_types", "mechanicTypes"))
    raw_parsed = _aslist(_g("parsed_tags", "parsedTags"))
    raw_layout = _aslist(_g("layout_tags", "layoutTags"))

    out = {
        "mechanicTypes": _filter_tags(raw_mech, ALLOWED_MECHANIC_TYPES),
        "parsedTags": _filter_tags(raw_parsed, ALLOWED_PARSED_TAGS),
        "layoutTags": _filter_tags(raw_layout, ALLOWED_LAYOUT),
        "complexityScore": int(_g("complexity_score", "complexityScore", default=0) or 0),
        "resultSpeed": str(_g("result_speed", "resultSpeed", default="") or "").lower(),
        "aiDescription": str(_g("ai_description", "aiDescription", default="") or "").strip(),
    }
    out["complexityScore"] = max(0, min(5, out["complexityScore"]))
    if out["resultSpeed"] not in ALLOWED_RESULT_SPEED:
        out["resultSpeed"] = ""
    return out
