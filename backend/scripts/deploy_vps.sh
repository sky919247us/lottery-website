#!/bin/bash

# 刮刮樂網站後端 VPS 部署腳本
# 適用於 Ubuntu/Debian 系統

echo "🚀 開始部署刮刮樂網站後端..."

# 1. 更新系統並安裝必要套件
sudo apt update && sudo apt install -y python3-pip python3-venv git curl

# 2. 安裝 uv (更快的 Python 套件管理器)
curl -LsSf https://astral.sh/uv/install.sh | sh
source $HOME/.cargo/env

# 3. 設定 2GB Swap (虛擬記憶體)，防止 1GB RAM 不足
echo "⚙️ 正在設定 2GB Swap 虛擬記憶體..."
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab

# 4. 複製程式碼 (如果資料夾不存在)
if [ ! -d "lottery-website" ]; then
    git clone https://github.com/sky919247us/lottery-website.git
fi

cd lottery-website/backend

# 4. 建立虛擬環境並安裝依賴
uv venv
source .venv/bin/activate
uv pip install -r requirements.txt

# 5. 建立環境變數檔案 (若不存在)
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo "⚠️ 請記得編輯 backend/.env 設定您的 SECRET_KEY 與資料庫路徑"
fi

echo "✅ 部署完成！"
echo "您可以執行 './scripts/start_server.sh' 來啟動伺服器，"
echo "或者將系統服務 (.service) 註冊到 systemd 以實現自動重啟。"
