import sqlite3
import os

db_path = "./scratchcard.db"

def migrate_expire_at():
    if not os.path.exists(db_path):
        print(f"❌ 找不到資料庫檔案: {db_path}")
        return

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 檢查欄位是否存在
        cursor.execute("PRAGMA table_info(admin_users)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if "expireAt" not in columns:
            print("正在新增 'expireAt' 欄位至 'admin_users' 資料表...")
            cursor.execute("ALTER TABLE admin_users ADD COLUMN expireAt DATETIME")
            conn.commit()
            print("✅ 欄位新增成功。")
        else:
            print("ℹ️ 'expireAt' 欄位已存在，無需執行遷移。")
            
        conn.close()
    except Exception as e:
        print(f"❌ 遷移失敗: {e}")

if __name__ == "__main__":
    migrate_expire_at()
