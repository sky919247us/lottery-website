import sys
import os

# 將專案目錄加入 Python 路徑
sys.path.append(os.getcwd())

from app.model.database import SessionLocal
from app.model.admin import AdminUser, ROLE_SUPER_ADMIN, hash_password

def reset_admin_password():
    db = SessionLocal()
    try:
        # 尋找名稱為 admin 的管理員
        admin = db.query(AdminUser).filter(AdminUser.username == "admin").first()
        
        new_password = "admin123456"
        hashed, salt = hash_password(new_password)
        
        if admin:
            # 如果存在，重設密碼與權限
            admin.passwordHash = hashed
            admin.passwordSalt = salt
            admin.role = ROLE_SUPER_ADMIN
            admin.isActive = True
            print(f"✅ 已成功重設 '{admin.username}' 的密碼。")
        else:
            # 如果不存在，建立一個新的
            new_admin = AdminUser(
                username="admin",
                passwordHash=hashed,
                passwordSalt=salt,
                displayName="超級管理員",
                role=ROLE_SUPER_ADMIN,
                isActive=True
            )
            db.add(new_admin)
            print(f"✅ 已建立新的超級管理員 '{new_admin.username}'。")
        
        db.commit()
    except Exception as e:
        print(f"❌ 重設失敗: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    reset_admin_password()
