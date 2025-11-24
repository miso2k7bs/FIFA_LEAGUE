import sqlite3

DB_NAME = "fifa.db"

def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cur = conn.cursor()

    # 유저 테이블
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT,
        money INTEGER DEFAULT 100000000,
        is_admin INTEGER DEFAULT 0
    );
    """)

    # 베팅 테이블
    cur.execute("""
    CREATE TABLE IF NOT EXISTS bets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        p1 TEXT,
        p2 TEXT,
        pick TEXT,
        amount INTEGER,
        result TEXT DEFAULT 'pending',
        payout INTEGER DEFAULT 0
    );
    """)

    conn.commit()
    conn.close()
