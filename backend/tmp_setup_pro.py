import sys
import os
sys.path.append(os.getcwd())

from app.model.database import SessionLocal
from app.model.retailer import Retailer

def setup_pro_merchant():
    db = SessionLocal()
    try:
        # 尋找一個已認領的商家
        r = db.query(Retailer).filter(Retailer.isClaimed == True).first()
        if r:
            r.merchantTier = 'pro'
            db.commit()
            print(f"Success: Retailer ID {r.id} ({r.name}) has been upgraded to PRO tier.")
            return r.id
        else:
            print("Error: No claimed retailers found in database.")
            return None
    finally:
        db.close()

if __name__ == "__main__":
    setup_pro_merchant()
