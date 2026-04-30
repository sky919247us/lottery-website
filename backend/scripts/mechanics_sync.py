"""
從線上 i168.win 拉取全部刮刮樂玩法資料 → 存到本地 JSON
用途：
  1. 本地離線查詢 (Claude 對話時讀取本地檔案直接答玩法)
  2. 找出尚未解析的款式 (parsedTags 為空)，交給本地 Claude 解析後再 push 回去

用法:
  python scripts/mechanics_sync.py
  → 寫入 backend/data/mechanics.json

環境變數:
  API_BASE   預設 https://i168.win
  ADMIN_TOKEN  必填 (admin login 取得)
"""
from __future__ import annotations
import json
import os
import sys
from pathlib import Path

import requests

API_BASE = os.getenv("API_BASE", "https://i168.win").rstrip("/")
TOKEN = os.getenv("ADMIN_TOKEN", "").strip()

if not TOKEN:
    print("ERROR: 請設定環境變數 ADMIN_TOKEN", file=sys.stderr)
    sys.exit(1)

OUT = Path(__file__).resolve().parent.parent / "data" / "mechanics.json"
OUT.parent.mkdir(parents=True, exist_ok=True)


def main() -> None:
    url = f"{API_BASE}/api/analytics/mechanics/dump"
    r = requests.get(url, headers={"Authorization": f"Bearer {TOKEN}"}, timeout=60)
    r.raise_for_status()
    items = r.json()

    OUT.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")

    total = len(items)
    has_text = sum(1 for x in items if (x.get("rawText") or "").strip())
    parsed = sum(1 for x in items if x.get("parsedTags"))
    no_text = total - has_text
    unparsed = total - parsed

    print(f"✅ 已寫入 {OUT}")
    print(f"   總數: {total}")
    print(f"   有 rawText: {has_text}")
    print(f"   有 imageUrl 但無 rawText: {no_text}")
    print(f"   已 AI 解析 (parsedTags): {parsed}")
    print(f"   尚未解析: {unparsed}")


if __name__ == "__main__":
    main()
