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


def get_pg_conn():
    """解析 DATABASE_URL 並建立 PostgreSQL 連線"""
    # postgresql://user:pass@host:port/dbname
    url = PG_URL.replace("postgresql://", "")
    user_pass, host_db = url.split("@")
    user, password = user_pass.split(":")
    host_port, dbname = host_db.split("/")
    if ":" in host_port:
        host, port = host_port.split(":")
    else:
        host, port = host_port, "5432"
    return psycopg2.connect(host=host, port=port, dbname=dbname, user=user, password=password)


def migrate_table(sqlite_cur, pg_conn, table_name, columns):
    """搬遷單一表格"""
    sqlite_cur.execute(f"SELECT * FROM {table_name}")
    rows = sqlite_cur.fetchall()

    if not rows:
        print(f"  ⏭️  {table_name}: 無資料，跳過")
        return 0

    pg_cur = pg_conn.cursor()

    # 清空目標表格
    pg_cur.execute(f"DELETE FROM {table_name}")

    # 建立 INSERT 語句
    placeholders = ", ".join(["%s"] * len(columns))
    col_names = ", ".join([f'"{c}"' for c in columns])
    insert_sql = f'INSERT INTO {table_name} ({col_names}) VALUES ({placeholders})'

    count = 0
    for row in rows:
        try:
            pg_cur.execute(insert_sql, row)
            count += 1
        except Exception as e:
            print(f"  ⚠️  {table_name} 行 {count}: {e}")
            pg_conn.rollback()
            continue

    pg_conn.commit()

    # 重設 sequence（auto increment）
    try:
        pg_cur.execute(f"SELECT MAX(id) FROM {table_name}")
        max_id = pg_cur.fetchone()[0]
        if max_id:
            pg_cur.execute(f"SELECT setval(pg_get_serial_sequence('{table_name}', 'id'), {max_id})")
            pg_conn.commit()
    except Exception:
        pg_conn.rollback()

    print(f"  ✅ {table_name}: {count} 筆")
    return count


def main():
    print("=" * 50)
    print("🚀 SQLite → PostgreSQL 資料搬遷")
    print("=" * 50)

    # 連接 SQLite
    if not os.path.exists(SQLITE_PATH):
        print(f"❌ 找不到 {SQLITE_PATH}")
        exit(1)

    sqlite_conn = sqlite3.connect(SQLITE_PATH)
    sqlite_cur = sqlite_conn.cursor()

    # 連接 PostgreSQL
    pg_conn = get_pg_conn()
    print("✅ PostgreSQL 連線成功")

    # 先用 SQLAlchemy 建立所有表格
    print("\n📦 建立 PostgreSQL 表格結構...")
    os.environ["DATABASE_URL"] = PG_URL
    from app.model.database import init_db
    init_db()
    print("✅ 表格建立完成")

    # 取得 SQLite 所有表格
    sqlite_cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
    sqlite_tables = [row[0] for row in sqlite_cur.fetchall()]
    print(f"\n📋 找到 {len(sqlite_tables)} 個表格: {', '.join(sqlite_tables)}")

    # 搬遷每個表格
    print("\n📤 開始搬遷資料...")
    total = 0

    for table_name in sqlite_tables:
        try:
            # 取得欄位名稱
            sqlite_cur.execute(f"PRAGMA table_info({table_name})")
            columns = [row[1] for row in sqlite_cur.fetchall()]

            # 確認 PostgreSQL 表格存在
            pg_cur = pg_conn.cursor()
            pg_cur.execute(
                "SELECT EXISTS(SELECT 1 FROM information_schema.tables WHERE table_name=%s)",
                (table_name,),
            )
            exists = pg_cur.fetchone()[0]

            if not exists:
                print(f"  ⏭️  {table_name}: PostgreSQL 中不存在，跳過")
                continue

            # 取得 PostgreSQL 欄位
            pg_cur.execute(
                "SELECT column_name FROM information_schema.columns WHERE table_name=%s",
                (table_name,),
            )
            pg_columns = {row[0] for row in pg_cur.fetchall()}

            # 只搬遷兩邊都有的欄位
            common_columns = [c for c in columns if c in pg_columns]
            if not common_columns:
                print(f"  ⏭️  {table_name}: 無共同欄位，跳過")
                continue

            # 重新查詢只選共同欄位
            col_select = ", ".join([f'"{c}"' for c in common_columns])
            sqlite_cur.execute(f"SELECT {col_select} FROM {table_name}")
            rows = sqlite_cur.fetchall()

            if not rows:
                print(f"  ⏭️  {table_name}: 無資料，跳過")
                continue

            pg_cur2 = pg_conn.cursor()
            pg_cur2.execute(f"DELETE FROM {table_name}")

            placeholders = ", ".join(["%s"] * len(common_columns))
            col_names = ", ".join([f'"{c}"' for c in common_columns])
            insert_sql = f'INSERT INTO {table_name} ({col_names}) VALUES ({placeholders})'

            count = 0
            for row in rows:
                try:
                    pg_cur2.execute(insert_sql, row)
                    count += 1
                except Exception as e:
                    pg_conn.rollback()
                    if count == 0:
                        print(f"  ⚠️  {table_name} 第一筆錯誤: {e}")
                    continue

            pg_conn.commit()

            # 重設 auto increment sequence
            if "id" in common_columns:
                try:
                    pg_cur2.execute(f"SELECT MAX(id) FROM {table_name}")
                    max_id = pg_cur2.fetchone()[0]
                    if max_id:
                        pg_cur2.execute(
                            f"SELECT setval(pg_get_serial_sequence('{table_name}', 'id'), {max_id})"
                        )
                        pg_conn.commit()
                except Exception:
                    pg_conn.rollback()

            print(f"  ✅ {table_name}: {count} 筆")
            total += count

        except Exception as e:
            print(f"  ❌ {table_name}: {e}")
            pg_conn.rollback()

    print(f"\n{'=' * 50}")
    print(f"🎉 搬遷完成！共 {total} 筆資料")
    print("=" * 50)

    sqlite_conn.close()
    pg_conn.close()


if __name__ == "__main__":
    main()
