#!/bin/bash
# 刮刮研究室 (i168.win) 一鍵部署腳本

set -e

echo "🚀 開始雲端部署程序..."

# 1. 獲取最新內容
echo "📦 同步最新程式碼..."
git pull origin main

# 2. 前端構建
echo "🏗️ 前端編譯中..."
cd frontend
npm install
npm run build
# 假設 Nginx 目錄為 /var/www/html
# sudo cp -r dist/* /var/www/html/
cd ..

# 3. 後端更新
echo "🐍 更新後端環境..."
cd backend
uv sync

# 4. 重啟後端服務
echo "🔄 重啟後端服務 (Uvicorn)..."
# 尋找並結束舊的程序 (根據埠號 8000)
PID=$(lsof -t -i:8000) || true
if [ ! -z "$PID" ]; then
    echo "終止舊程序: $PID"
    kill -9 $PID
fi
# 使用 nohup 在背景執行
nohup uv run python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers > uvicorn.log 2>&1 &
echo "後端已於背景啟動。"

# 5. 資料同步
echo "📊 執行資料同步腳本..."
uv run python sync_all.py

echo "✅ 部署完成！請至 https://i168.win/ 驗證。"
