import sqlite3
import os
from pathlib import Path

# 設定路徑 (考量雲端與本地端)
SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent
CURRENT_DB = BACKEND_DIR / "scratchcard.db"
BACKUP_DIR = BACKEND_DIR / "backups"

def restore_coords():
    print("開始座標還原程序...")
    if not BACKUP_DIR.exists():
        print("❌ 找不到 backups 目錄！")
        return
        
    backups = list(BACKUP_DIR.glob("scratchcard_*.db"))
    if not backups:
        print("❌ 找不到任何資料庫備份檔案！")
        return
    
    latest_backup = max(backups, key=lambda p: p.stat().st_mtime)
    print(f"📦 找到最新備份檔: {latest_backup.name}")
    
    conn_backup = sqlite3.connect(latest_backup)
    conn_current = sqlite3.connect(CURRENT_DB)
    
    cur_backup = conn_backup.cursor()
    cur_current = conn_current.cursor()
    
    # 從備份讀取座標 (以 address 或 name 為 key)
    cur_backup.execute("SELECT name, address, lat, lng FROM retailers WHERE lat IS NOT NULL AND lng IS NOT NULL")
    backup_data = cur_backup.fetchall()
    
    # 建立以 (name, address) 為 Key 的座標字典
    coords_map = {(row[0], row[1]): (row[2], row[3]) for row in backup_data}
    print(f"🔍 從備份提取了 {len(coords_map)} 筆有效座標")
    
    # 掃描當前 DB 缺失座標的店家
    cur_current.execute("SELECT id, name, address FROM retailers WHERE lat IS NULL OR lng IS NULL")
    current_retailers = cur_current.fetchall()
    print(f"⚠️ 當前資料庫有 {len(current_retailers)} 筆經銷商遺失座標")
    
    updated = 0
    for r_id, name, address in current_retailers:
        if (name, address) in coords_map:
            lat, lng = coords_map[(name, address)]
            cur_current.execute("UPDATE retailers SET lat=?, lng=? WHERE id=?", (lat, lng, r_id))
            updated += 1
            
    conn_current.commit()
    print(f"✅ 成功還原 {updated} 筆坐標到當前資料庫！ (已排除不符的 {len(current_retailers) - updated} 筆)")
    
    conn_backup.close()
    conn_current.close()

if __name__ == "__main__":
    restore_coords()
