
import sqlite3
import os

db_path = r'c:\刮刮樂網站\backend\scratchcard.db'

if not os.path.exists(db_path):
    print(f"Error: Database not found at {db_path}")
else:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT COUNT(*) FROM scratchcards")
        print(f"Scratchcards count: {cursor.fetchone()[0]}")
        
        cursor.execute("SELECT COUNT(*) FROM retailers")
        print(f"Retailers count: {cursor.fetchone()[0]}")
        
        cursor.execute("SELECT COUNT(*) FROM retailers WHERE lat IS NOT NULL")
        print(f"Retailers with lat/lng: {cursor.fetchone()[0]}")
        
        cursor.execute("SELECT COUNT(*) FROM retailers WHERE jackpotCount > 0")
        print(f"Retailers with jackpot: {cursor.fetchone()[0]}")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.close()
