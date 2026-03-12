import sys
import os

# 將專案目錄加入 Python 路徑
sys.path.append(os.getcwd())

from app.model.database import SessionLocal
from app.model.admin import AdminUser, ROLE_SUPER_ADMIN, hash_password, verify_password

def force_reset_and_verify():
    db = SessionLocal()
    try:
        username = "admin"
        password = "admin123456"
        
        # 1. 執行雜湊
        hashed, salt = hash_password(password)
        print(f"--- 重新產生雜湊 ---")
        print(f"Password: {password}")
        print(f"Hashed: {hashed}")
        print(f"Salt: {salt}")
        
        # 2. 更新資料庫
        admin = db.query(AdminUser).filter(AdminUser.username == username).first()
        if not admin:
            admin = AdminUser(username=username)
            db.add(admin)
        
        admin.passwordHash = hashed
        admin.passwordSalt = salt
        admin.role = ROLE_SUPER_ADMIN
        admin.isActive = 1  # 明確設為 1 (int)
        admin.displayName = "超級管理員"
        
        db.commit()
        db.refresh(admin)
        print(f"✅ 資料庫已更新。")
        
        # 3. 立即進行邏輯驗證 (使用 app 內的 verify_password)
        success = verify_password(password, admin.passwordHash, admin.passwordSalt)
        print(f"--- 邏輯驗證測試 ---")
        print(f"測試登入結果: {'成功' if success else '失敗'}")
        
    except Exception as e:
        print(f"❌ 錯誤: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    force_reset_and_verify()
