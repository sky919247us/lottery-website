import sys
import os

# 將專案目錄加入 Python 路徑
sys.path.append(os.getcwd())

from app.model.database import SessionLocal
from app.model.admin import AdminUser

def debug_admin_account():
    db = SessionLocal()
    try:
        admin = db.query(AdminUser).filter(AdminUser.username == "admin").first()
        if admin:
            print(f"--- 帳號資訊 ---")
            print(f"ID: {admin.id}")
            print(f"帳號: {admin.username}")
            print(f"顯示名稱: {admin.displayName}")
            print(f"角色: {admin.role}")
            print(f"是否啟用 (isActive): {admin.isActive} (類型: {type(admin.isActive)})")
            print(f"密碼 Hash (前 10 碼): {admin.passwordHash[:10]}...")
            print(f"密碼 Salt (前 10 碼): {admin.passwordSalt[:10]}...")
        else:
            print("❌ 找不到 'admin' 帳號。")
    finally:
        db.close()

if __name__ == "__main__":
    debug_admin_account()
