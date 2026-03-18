"""
SQLite → PostgreSQL 資料搬遷腳本
將 scratchcard.db 的所有資料搬到 PostgreSQL
"""

import os
import sqlite3

import psycopg2
from dotenv import load_dotenv

load_dotenv()

SQLITE_PATH = "scratchcard.db"
PG_URL = os.getenv("DATABASE_URL", "")

if not PG_URL:
    print("❌ 請在 .env 設定 DATABASE_URL")
    exit(1)

# 搬遷順序（先搬被依賴的表）
TABLE_ORDER = [
    "scratchcards",
    "prize_structures",
    "retailers",
    "admin_users",
    "users",
    "checkins",
    "youtube_links",
    "merchant_claims",
    "merchant_announcements",
    "karma_logs",
    "inventory_reports",
    "retailer_ratings",
    "jackpot_stores",
    "merchant_photos",
    "merchant_inventory",
]


def get_pg_conn():
    url = PG_URL.replace("postgresql://", "")
    user_pass, host_db = url.split("@")
    user, password = user_pass.split(":")
    host_port, dbname = host_db.split("/")
    if ":" in host_port:
        host, port = host_port.split(":")
    else:
        host, port = host_port, "5432"
    return psycopg2.connect(host=host, port=port, dbname=dbname, user=user, password=password)


def get_pg_boolean_columns(pg_conn, table_name):
    """取得 PostgreSQL 表格中所有 boolean 欄位"""
    cur = pg_conn.cursor()
    cur.execute(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name=%s AND data_type='boolean'",
        (table_name,),
    )
    return {row[0] for row in cur.fetchall()}


def convert_row(row, columns, bool_cols):
    """將 SQLite 的 0/1 轉換為 PostgreSQL 的 True/False"""
    converted = []
    for i, val in enumerate(row):
        col_name = columns[i]
        if col_name in bool_cols:
            if val is None:
                converted.append(None)
            else:
                converted.append(bool(val))
        else:
            converted.append(val)
    return tuple(converted)


def main():
    print("=" * 50)
    print("🚀 SQLite → PostgreSQL 資料搬遷")
    print("=" * 50)

    if not os.path.exists(SQLITE_PATH):
        print(f"❌ 找不到 {SQLITE_PATH}")
        exit(1)

    sqlite_conn = sqlite3.connect(SQLITE_PATH)
    sqlite_cur = sqlite_conn.cursor()

    pg_conn = get_pg_conn()
    print("✅ PostgreSQL 連線成功")

    # 建立表格結構
    print("\n📦 建立 PostgreSQL 表格結構...")
    os.environ["DATABASE_URL"] = PG_URL
    from app.model.database import init_db
    init_db()
    print("✅ 表格建立完成")

    # 取得 SQLite 所有表格
    sqlite_cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
    sqlite_tables = {row[0] for row in sqlite_cur.fetchall()}

    # 暫時停用外鍵檢查
    pg_cur = pg_conn.cursor()
    pg_cur.execute("SET session_replication_role = 'replica'")
    pg_conn.commit()

    print(f"\n📤 開始搬遷資料...")
    total = 0

    for table_name in TABLE_ORDER:
        if table_name not in sqlite_tables:
            print(f"  ⏭️  {table_name}: SQLite 中不存在，跳過")
            continue

        try:
            # 確認 PostgreSQL 表格存在
            pg_cur.execute(
                "SELECT EXISTS(SELECT 1 FROM information_schema.tables WHERE table_name=%s)",
                (table_name,),
            )
            if not pg_cur.fetchone()[0]:
                print(f"  ⏭️  {table_name}: PostgreSQL 中不存在，跳過")
                continue

            # 取得 SQLite 欄位
            sqlite_cur.execute(f"PRAGMA table_info({table_name})")
            sqlite_columns = [row[1] for row in sqlite_cur.fetchall()]

            # 取得 PostgreSQL 欄位
            pg_cur.execute(
                "SELECT column_name FROM information_schema.columns WHERE table_name=%s",
                (table_name,),
            )
            pg_columns = {row[0] for row in pg_cur.fetchall()}

            # 取得 boolean 欄位
            bool_cols = get_pg_boolean_columns(pg_conn, table_name)

            # 共同欄位
            common_columns = [c for c in sqlite_columns if c in pg_columns]
            if not common_columns:
                print(f"  ⏭️  {table_name}: 無共同欄位，跳過")
                continue

            # 讀取 SQLite 資料
            col_select = ", ".join([f'"{c}"' for c in common_columns])
            sqlite_cur.execute(f"SELECT {col_select} FROM {table_name}")
            rows = sqlite_cur.fetchall()

            if not rows:
                print(f"  ⏭️  {table_name}: 無資料，跳過")
                continue

            # 清空目標表格
            pg_cur.execute(f"DELETE FROM {table_name}")

            # 插入資料
            placeholders = ", ".join(["%s"] * len(common_columns))
            col_names = ", ".join([f'"{c}"' for c in common_columns])
            insert_sql = f'INSERT INTO {table_name} ({col_names}) VALUES ({placeholders})'

            count = 0
            errors = 0
            for row in rows:
                try:
                    converted = convert_row(row, common_columns, bool_cols)
                    pg_cur.execute(insert_sql, converted)
                    count += 1
                except Exception as e:
                    pg_conn.rollback()
                    # 重新停用外鍵
                    pg_cur.execute("SET session_replication_role = 'replica'")
                    errors += 1
                    if errors <= 1:
                        print(f"  ⚠️  {table_name} 錯誤: {e}")

            pg_conn.commit()

            # 重設 sequence
            if "id" in common_columns:
                try:
                    pg_cur.execute(f"SELECT MAX(id) FROM {table_name}")
                    max_id = pg_cur.fetchone()[0]
                    if max_id:
                        pg_cur.execute(
                            f"SELECT setval(pg_get_serial_sequence('{table_name}', 'id'), {max_id})"
                        )
                        pg_conn.commit()
                except Exception:
                    pg_conn.rollback()

            err_msg = f" ({errors} 筆錯誤)" if errors else ""
            print(f"  ✅ {table_name}: {count} 筆{err_msg}")
            total += count

        except Exception as e:
            print(f"  ❌ {table_name}: {e}")
            pg_conn.rollback()

    # 恢復外鍵檢查
    pg_cur.execute("SET session_replication_role = 'origin'")
    pg_conn.commit()

    print(f"\n{'=' * 50}")
    print(f"🎉 搬遷完成！共 {total} 筆資料")
    print("=" * 50)

    sqlite_conn.close()
    pg_conn.close()


if __name__ == "__main__":
    main()
