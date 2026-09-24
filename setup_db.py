"""Creates the database + tables, upgrades an older database in place, and seeds sample data.

    python setup_db.py

Safe to run as many times as you like. Uses the DB_* settings from .env (XAMPP defaults otherwise).
"""
import re
import sys
import mysql.connector
from config import Config

# Columns added after the first version of the schema. (table, column, definition)
MIGRATIONS = [
    ("users", "email", "VARCHAR(120) NULL"),
    ("users", "status", "VARCHAR(20) NOT NULL DEFAULT 'active'"),
    ("equipment", "operating_hours", "FLOAT NOT NULL DEFAULT 0"),
    ("predictions", "created_by", "VARCHAR(100) NULL"),
    ("maintenance_logs", "created_by", "VARCHAR(100) NULL"),
]


def statements_from_schema():
    sql = open("schema.sql", encoding="utf-8").read()
    sql = re.sub(r"--[^\n]*", "", sql)  # strip comments
    for stmt in (s.strip() for s in sql.split(";")):
        if not stmt:
            continue
        # The database is created/selected below from DB_NAME so .env is respected.
        if stmt.upper().startswith(("CREATE DATABASE", "USE ")):
            continue
        yield stmt


def column_exists(cur, table, column):
    cur.execute(
        "SELECT COUNT(*) FROM information_schema.columns "
        "WHERE table_schema = %s AND table_name = %s AND column_name = %s",
        (Config.DB_NAME, table, column),
    )
    return cur.fetchone()[0] > 0


def main():
    try:
        conn = mysql.connector.connect(
            host=Config.DB_HOST, port=Config.DB_PORT,
            user=Config.DB_USER, password=Config.DB_PASSWORD,
            connection_timeout=5,
        )
    except mysql.connector.Error as e:
        sys.exit(f"Could not connect to MySQL at {Config.DB_HOST}:{Config.DB_PORT} as '{Config.DB_USER}'.\n"
                 f"Is MySQL started in XAMPP? Are the DB_* values in .env right?\n  ({e})")

    cur = conn.cursor()
    cur.execute(f"CREATE DATABASE IF NOT EXISTS `{Config.DB_NAME}`")
    cur.execute(f"USE `{Config.DB_NAME}`")

    for stmt in statements_from_schema():
        cur.execute(stmt)

    for table, column, definition in MIGRATIONS:
        if not column_exists(cur, table, column):
            cur.execute(f"ALTER TABLE `{table}` ADD COLUMN `{column}` {definition}")
            print(f"Upgraded: added {table}.{column}")

    # Roles were 'admin'/'staff' in the first version; 'staff' is now 'maintenance_staff'.
    cur.execute("UPDATE users SET role = 'maintenance_staff' WHERE role = 'staff'")
    conn.commit()
    cur.close()
    conn.close()
    print(f"Database '{Config.DB_NAME}' is ready.")

    from seed_data import seed
    seed()


if __name__ == "__main__":
    main()
