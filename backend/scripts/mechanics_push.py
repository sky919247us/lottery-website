"""
把本地 Claude 解析好的玩法結果 push 回線上資料庫（不耗 Gemini 配額）。

兩種用法:
  1. 單筆 (從 stdin 讀 JSON)
     echo '{"id":123,"mechanicTypes":["match3"],...}' | python scripts/mechanics_push.py

  2. 批次 (讀檔，每行一筆 JSON 或一個 JSON array)
     python scripts/mechanics_push.py results.json

每筆 JSON 必填欄位:
  id (int)
  mechanicTypes, parsedTags, layoutTags (list[str])
  complexityScore (1-5)
  resultSpeed ("instant"|"multi_zone"|"sequence"|"multi_step"|"compare")
  aiDescription (str, <=50字繁中)
選填:
  rawText, sourceType ("text"|"image"), sourceUrl
  parseProvider (預設 "claude-manual"), parseModel

環境變數:
  API_BASE   預設 https://i168.win
  ADMIN_TOKEN  必填
"""
from __future__ import annotations
import json
import os
import sys
import time
from pathlib import Path

import requests

API_BASE = os.getenv("API_BASE", "https://i168.win").rstrip("/")
TOKEN = os.getenv("ADMIN_TOKEN", "").strip()

if not TOKEN:
    print("ERROR: 請設定環境變數 ADMIN_TOKEN", file=sys.stderr)
    sys.exit(1)

HEADERS = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}


def push_one(item: dict) -> tuple[bool, str]:
    sid = item.pop("id")
    payload = {
        "mechanicTypes": item.get("mechanicTypes", []),
        "parsedTags": item.get("parsedTags", []),
        "layoutTags": item.get("layoutTags", []),
        "complexityScore": int(item.get("complexityScore", 0)),
        "resultSpeed": item.get("resultSpeed", ""),
        "aiDescription": item.get("aiDescription", ""),
        "rawText": item.get("rawText"),
        "sourceType": item.get("sourceType"),
        "sourceUrl": item.get("sourceUrl"),
        "parseProvider": item.get("parseProvider", "claude-manual"),
        "parseModel": item.get("parseModel", ""),
    }
    url = f"{API_BASE}/api/analytics/scratchcards/{sid}/upsert-mechanic-direct"
    r = requests.post(url, headers=HEADERS, json=payload, timeout=30)
    if r.status_code == 200:
        return True, f"#{sid} ✅"
    return False, f"#{sid} ❌ {r.status_code} {r.text[:200]}"


def load_items() -> list[dict]:
    if len(sys.argv) > 1:
        path = Path(sys.argv[1])
        text = path.read_text(encoding="utf-8").strip()
    else:
        text = sys.stdin.read().strip()

    if not text:
        return []

    if text.startswith("["):
        return json.loads(text)
    # JSONL
    items = []
    for line in text.splitlines():
        line = line.strip()
        if line:
            items.append(json.loads(line))
    return items


def main() -> None:
    items = load_items()
    if not items:
        print("沒有資料", file=sys.stderr)
        sys.exit(1)

    ok = fail = 0
    for it in items:
        success, msg = push_one(dict(it))
        print(msg)
        ok += int(success)
        fail += int(not success)
        time.sleep(0.2)

    print(f"\n=== 完成 push: 成功 {ok} / 失敗 {fail} (總計 {len(items)}) ===")


if __name__ == "__main__":
    main()
