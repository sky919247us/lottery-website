#!/bin/bash

# 刮刮樂網站 API 服務註冊腳本
# 執行方式: sudo bash setup_service.sh

SERVICE_FILE="lottery-api.service"
DEST_PATH="/etc/systemd/system/$SERVICE_FILE"

echo "⚙️ 正在註冊系統服務..."

if [ ! -f "scripts/$SERVICE_FILE" ]; then
    echo "❌ 找不到 scripts/$SERVICE_FILE，請確保在 backend 目錄下執行此腳本。"
    exit 1
fi

# 複製服務檔案到系統目錄
sudo cp scripts/$SERVICE_FILE $DEST_PATH

# 重新載入 systemd 並啟動服務
sudo systemctl daemon-reload
sudo systemctl enable lottery-api
sudo systemctl restart lottery-api

echo "✅ 服務註冊完成！"
echo "您可以透過以下指令檢查狀態:"
echo "sudo systemctl status lottery-api"
