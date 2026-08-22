# 刮刮樂網站（i168.win）

台灣刮刮樂資訊網站。一律用繁體中文回覆與撰寫面向使用者的文字。
全域守則見 `~/.claude/CLAUDE.md`（調度、驗證、備份規則都在那，本檔只放專案事實）。

## 技術棧與結構

- 後端：Python ≥3.12 + FastAPI + SQLAlchemy 2.0，套件管理用 `uv`（backend/pyproject.toml）
- 前端：React 19 + TypeScript + Vite 7 + MUI v7，地圖 Leaflet/MapLibre（frontend/package.json）
- 分層：`backend/app/api`（20 支路由）→ `service`（業務邏輯）→ `model`（ORM）→ `schema`（Pydantic）
- 前端：`frontend/src/pages`（頁面）、`components`（共用元件）、`admin/`（獨立後台子系統）、
  `hooks/api.ts`（API 封裝）

## 常用指令

- 後端啟動：在 backend/ 下 `uv run python -m uvicorn app.main:app --host 0.0.0.0 --port 8000`
- 前端開發：在 frontend/ 下 `npm run dev`；建置 `npm run build`；lint `npm run lint`
- 測試：在 backend/ 下 `uv run pytest`（測試檔在 backend/tests/，用獨立 test_scratchcard.db）
- 部署：`ssh lottery-backend`（GCP VPS，/home/sky919247us/lottery-website）→
  `git pull` → 前端 build → `sudo systemctl restart lottery-api`。
  詳細指令見記憶檔 deployment_paths.md。正式站 https://i168.win/

## 地雷（動手前必讀）

1. **`backend/scratchcard.db` 是被 git 追蹤的生產資料**。跑爬蟲/本機測試會弄髒它，
   這是正常現象。永不 `checkout --` 還原它；動它之前先複製到 backend/backups/；
   commit 前確認 db 變更是「有意提交」的。
2. **無 alembic**。schema 變更靠 `backend/app/model/database.py` 的 `_run_migrations()`
   手刻判斷。新增欄位必須同時寫 SQLite 分支和 PostgreSQL 分支，只寫一邊＝正式站不生效。
3. **Windows console 是 CP950**：腳本不要直接 print 中文到 stdout，
   先寫 UTF-8 檔案再用 Read 讀回（.claude/skills/new-scratchcard-compare/SKILL.md 有同樣警告）。
4. `backend/database.db`（0 bytes）是廢棄空檔，實際用的是 `scratchcard.db`，別搞混。
5. `backend/.env` 含真實密鑰，不要印出內容、不要提交。
6. 搜尋時禁入 node_modules、.venv、`.claude\worktrees`（含 7 萬+檔的殘留 worktree）、dist。
7. `backend/data/` 下底線開頭的 `_*.json` 是新款比對流程的暫存中間產物；
   `mechanics.json` 是 AI 玩法解析快取（相似款查詢依賴它），標籤規範見記憶檔
   mechanic_tag_schema.md。

## 排程任務（backend/app/main.py，APScheduler，cron 都是 UTC）

台灣時間：09:10 主爬蟲（爬完接玩法解析）、03:00 頭獎店家同步、10:05 預告款爬蟲、
04:00 DB 備份、04:30 清 90 天前打卡、10:00 PRO 到期提醒、每小時15分 PRO 降級。
改排程時間時記得 UTC↔台灣 +8 換算。

## 大樣本統計（整本開箱資料）

`/unboxing` 列表 + `/unboxing/:gameId` 詳情。把整本開箱影片的逐張中獎資料結構化公開。

- **資料分級三層**（`backend/app/api/unboxing.py`）：T0 未登入看彙總／T1 登入看逐本明細（流水序號遮蔽）／
  T2 `karmaLevel >= 5` 全開。**分級一定在後端切**，低權限的 payload 裡不會有逐張序號。
- **每本張數依面額查表**：`backend/app/model/ticket_layout.py` 與
  `frontend/src/utils/scratchcard.ts` 兩份要同步（100/200/300→100、500→50、1000→25、2000→19）。
- **熱力圖統一 25 欄、格子固定尺寸**，$2,000 券用 19 欄。不要改成 `1fr`，否則跨款無法比對。
- 上資料的流程（資料先上、影片後上）：
  1. 原始檔丟 `backend/data/unboxing/raw/`
  2. `uv run python scripts/normalize_unboxing.py --src data/unboxing/raw`（各種試算表版面 → 正規化 JSON）
  3. `uv run python scripts/import_unboxing.py --src data/unboxing`（先看報告）→ 加 `--commit` 寫入
  4. 影片上架後 `uv run python scripts/sync_unboxing_videos.py --commit`
     （抓「包本解密」播放清單 RSS，用標題裡的 `#期數` 自動對應）
- 匯入以 `(gameId, 流水序號)` 去重：同一本常同時出現在「3本」與「9本」兩份檔案裡，不去重會樣本灌水。
- 收到同款更完整的來源檔時：換掉 raw/ 舊檔、重跑 normalize，再用 `--replace` 匯入
  （會先刪掉該期既有場次），否則會多出一個殘留場次。
- `_*.txt` / `_*.json` 是各腳本的報告與中間產物，不進版控。

## 專案 skill

- `/new-scratchcard-compare`：新款刮刮樂 vs 資料庫舊款比對（發行量/獎金結構/相似款）。
  使用者貼新款資訊要求比較時用它，不要手刻比對。

## 相關記憶檔（~/.claude/projects/D-------/memory/）

- deployment_paths.md — 伺服器路徑與部署指令
- mechanic_tag_schema.md — 玩法標籤白名單規範
- taiwan_lottery_unclaimed_policy.md — 台彩資料公開政策（別再探索已確認的限制）
