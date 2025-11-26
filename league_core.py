from db import get_db
from datetime import datetime

# ============================
# Elo 기본 파라미터
# ============================
K = 32   # Elo K-factor

# ============================
# Elo 값 불러오기
# ============================
def get_rating(name):
    db = get_db()
    row = db.execute("SELECT rating FROM elo_ratings WHERE name=?", (name,)).fetchone()

    # 없으면 1200으로 생성
    if row is None:
        db.execute("INSERT INTO elo_ratings(name, rating) VALUES (?, ?)", (name, 1200))
        db.commit()
        return 1200
    
    return round(row["rating"])

# ============================
# Elo 저장
# ============================
def set_rating(name, rating):
    db = get_db()
    db.execute(
        "INSERT OR REPLACE INTO elo_ratings(name, rating) VALUES (?, ?)",
        (name, rating)
    )
    db.commit()


# ============================
# Elo 업데이트
# ============================
def update_elo_with_score(p1, p2, s1, s2):

    R1 = get_rating(p1)
    R2 = get_rating(p2)

    # Expected Win Rate
    E1 = 1 / (1 + 10 ** ((R2 - R1) / 400))
    E2 = 1 - E1

    # 결과값
    if s1 > s2:
        S1, S2 = 1, 0
    elif s1 < s2:
        S1, S2 = 0, 1
    else:
        S1, S2 = 0.5, 0.5

    # 새로운 Elo
    new_R1 = R1 + K * (S1 - E1)
    new_R2 = R2 + K * (S2 - E2)

    # 저장
    set_rating(p1, round(new_R1))
    set_rating(p2, round(new_R2))

    # 경기 기록 저장
    save_match(p1, p2, s1, s2)


# ============================
# 경기 기록 저장
# ============================
def save_match(p1, p2, s1, s2):
    db = get_db()
    db.execute("""
        INSERT INTO matches(p1, p2, score1, score2, time)
        VALUES (?, ?, ?, ?, ?)
    """, (p1, p2, s1, s2, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    db.commit()


# ============================
# 최근 경기 N개
# ============================
def get_recent_matches(limit=20):
    db = get_db()
    rows = db.execute(
        "SELECT * FROM matches ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
    return rows


# ============================
# Elo 랭킹
# ============================
def get_ranking():
    db = get_db()
    rows = db.execute(
        "SELECT name, rating FROM elo_ratings ORDER BY rating DESC"
    ).fetchall()
    return [(row["name"], round(row["rating"])) for row in rows]


# ============================
# 통계정보 (평균, 최고 등)
# ============================
def get_simple_stats():
    db = get_db()

    row = db.execute("SELECT COUNT(*) AS total FROM matches").fetchone()
    total = row["total"]

    avg_row = db.execute("SELECT AVG(rating) AS avg FROM elo_ratings").fetchone()
    avg_elo = round(avg_row["avg"]) if avg_row["avg"] else 0

    max_row = db.execute("SELECT name, rating FROM elo_ratings ORDER BY rating DESC LIMIT 1").fetchone()
    min_row = db.execute("SELECT name, rating FROM elo_ratings ORDER BY rating ASC LIMIT 1").fetchone()

    return {
        "total_matches": total,
        "avg_elo": avg_elo,
        "max_player": max_row["name"] if max_row else "",
        "max_rating": max_row["rating"] if max_row else 0,
        "min_player": min_row["name"] if min_row else "",
        "min_rating": min_row["rating"] if min_row else 0,
    }


# ============================
# 경기 삭제
# ============================
def delete_last_match():
    db = get_db()

    last = db.execute("SELECT * FROM matches ORDER BY id DESC LIMIT 1").fetchone()
    if not last:
        return False

    # 삭제
    db.execute("DELETE FROM matches WHERE id=?", (last["id"],))
    db.commit()

    return True


# ============================
# 전체 초기화
# ============================
def reset_all():
    db = get_db()
    db.execute("DELETE FROM matches")
    db.execute("DELETE FROM elo_ratings")
    db.commit()
