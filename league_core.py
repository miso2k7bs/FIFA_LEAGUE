# league_core.py
import csv
import os
from datetime import datetime
import math

# --- 선수 목록 & 초기 Elo (네가 준 서열 + 실력차 반영) ---
INITIAL_ELO = {
    "정진욱": 1700,
    "신지후": 1680,
    "임현수": 1550,
    "김건희": 1450,
    "공수호": 1400,
    "이시원": 1390,
    "이현준": 1380,
    "홍정민": 1320,
    "김민성": 1310,
    "허정민": 1300
}

ELO_FILE = "elo_ratings.csv"
LOG_FILE = "match_log.csv"

# 실행 중 메모리에 담긴 Elo
elo = INITIAL_ELO.copy()
match_log = []

# ================================================
# 저장 / 불러오기
# ================================================
def load_elo():
    global elo
    if not os.path.exists(ELO_FILE):
        elo = INITIAL_ELO.copy()
        return
    temp = {}
    with open(ELO_FILE, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        for row in reader:
            if len(row) != 2:
                continue
            name, rating = row
            temp[name] = float(rating)
    if temp:
        elo = temp


def save_elo():
    with open(ELO_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        for name, rating in elo.items():
            writer.writerow([name, rating])


def load_log():
    global match_log
    match_log = []
    if not os.path.exists(LOG_FILE):
        return
    with open(LOG_FILE, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            match_log.append(row)


def append_log(record):
    file_exists = os.path.exists(LOG_FILE)
    with open(LOG_FILE, "a", newline="", encoding="utf-8") as f:
        fieldnames = [
            "time", "p1", "score1", "p2", "score2",
            "p1_old", "p2_old", "p1_new", "p2_new", "result"
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        writer.writerow(record)

# ================================================
# ELO 계산
# ================================================
def expected(r1, r2):
    return 1 / (1 + 10 ** ((r2 - r1) / 400))

def update_elo_with_score(p1, p2, s1, s2, k=30):
    r1_old = elo[p1]
    r2_old = elo[p2]

    if s1 > s2:
        o1, o2 = 1.0, 0.0
        result = f"{p1} 승"
    elif s1 < s2:
        o1, o2 = 0.0, 1.0
        result = f"{p2} 승"
    else:
        o1, o2 = 0.5, 0.5
        result = "무승부"

    e1 = expected(r1_old, r2_old)
    e2 = expected(r2_old, r1_old)

    elo[p1] = r1_old + k * (o1 - e1)
    elo[p2] = r2_old + k * (o2 - e2)

    # 로그 기록
    rec = {
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "p1": p1,
        "score1": s1,
        "p2": p2,
        "score2": s2,
        "p1_old": round(r1_old, 2),
        "p2_old": round(r2_old, 2),
        "p1_new": round(elo[p1], 2),
        "p2_new": round(elo[p2], 2),
        "result": result
    }
    match_log.append(rec)
    append_log(rec)
    save_elo()
    return rec

# ================================================
# 순위 / 통계
# ================================================
def get_ranking():
    return sorted(elo.items(), key=lambda x: x[1], reverse=True)

def get_recent_matches(n=10):
    return list(reversed(match_log[-n:]))

def get_simple_stats():
    total = len(match_log)
    ratings = list(elo.values())
    avg = sum(ratings) / len(ratings)
    max_player, max_rating = max(elo.items(), key=lambda x: x[1])
    min_player, min_rating = min(elo.items(), key=lambda x: x[1])
    return {
        "total_matches": total,
        "avg_elo": round(avg, 2),
        "max_player": max_player,
        "max_rating": round(max_rating, 2),
        "min_player": min_player,
        "min_rating": round(min_rating, 2)
    }

# ================================================
# 실행 시 파일에서 데이터 불러오기
# ================================================
load_elo()
load_log()
