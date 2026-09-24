import mysql.connector
from mysql.connector import pooling
from config import Config

_pool = None


def get_pool():
    """Lazily create a MySQL connection pool (XAMPP-compatible)."""
    global _pool
    if _pool is None:
        kwargs = dict(
            pool_name="pmdb_pool",
            pool_size=10,
            host=Config.DB_HOST,
            port=Config.DB_PORT,
            user=Config.DB_USER,
            password=Config.DB_PASSWORD,
            database=Config.DB_NAME,
            connection_timeout=5,
        )
        if Config.DB_SSL_CA:
            kwargs["ssl_ca"] = Config.DB_SSL_CA
            kwargs["ssl_verify_cert"] = True
        _pool = pooling.MySQLConnectionPool(**kwargs)
    return _pool


def get_db_connection():
    """Returns a live connection from the pool. Caller must close() it
    (closing returns it to the pool rather than actually disconnecting)."""
    return get_pool().get_connection()


def run_query(query, params=None, fetch=False, fetch_one=False, commit=False):
    """Small helper so route handlers don't repeat connect/cursor/close boilerplate."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(query, params or ())
        result = None
        if fetch_one:
            result = cursor.fetchone()
        elif fetch:
            result = cursor.fetchall()
        if commit:
            conn.commit()
            result = cursor.lastrowid
        cursor.close()
        return result
    finally:
        conn.close()
