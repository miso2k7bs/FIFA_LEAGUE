# league_core.py
import csv
import os
from datetime import datetime
import math

# --- 선수 목록 & 초기 Elo (네 서열 + 실력차 반영) ---
INITIAL_ELO = {
    "정진욱": 1700,
    "신지후": 1680,
    "임현수": 1550,
    "김건희": 1450,
    "공수호": 1400,
    "이시원": 1390,
    "이현준": 1380,
    "홍정민": 1320,
    "김민성": 1300,
    "허정민": 1290,
}

elo = INITIAL_ELO.copy()
match_log = []

LOG_FILE = "match_log.csv"


# ==========================
# CSV 저장 기능
# ==========================

def save_match_to_csv(record):
    file_exists = os.path.isfile(LOG_FILE)

    with open(LOG_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=record.keys())
        if not file_exists:
            writer.writeheader()
        writer.writerow(record)


def load_history():
    """Render 재부팅 시 CSV에서 다시 불러오기"""
    if not os.path.isfile(LOG_FILE):
        return

    with open(LOG_FILE, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # 문자열을 정수로 변환
            row["score1"] = int(row["score1"])
            row["score2"] = int(row["score2"])
            match_log.append(row)


# ==========================
# ELO 계산
# ==========================

def expected(a, b):
    return 1 / (1 + 10 ** ((b - a) / 400))


K = 32


def update_elo_with_score(p1, p2, g1, g2):
    R1 = elo[p1]
    R2 = elo[p2]

    # 실제 경기 결과
    if g1 > g2:
        S1, S2 = 1, 0
        result = f"{p1} 승"
    elif g1 < g2:
        S1, S2 = 0, 1
        result = f"{p2} 승"
    else:
        S1, S2 = 0.5, 0.5
        result = "무승부"

    # 새로운 Elo 계산
    E1 = expected(R1, R2)
    E2 = expected(R2, R1)

    elo[p1] = R1 + K * (S1 - E1)
    elo[p2] = R2 + K * (S2 - E2)

    # 로그 기록
    record = {
        "p1": p1,
        "p2": p2,
        "score1": g1,
        "score2": g2,
        "result": result,
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    match_log.append(record)
    save_match_to_csv(record)


# ==========================
# 랭킹/로그/통계
# ==========================

def get_ranking():
    return sorted(elo.items(), key=lambda x: x[1], reverse=True)


def get_recent_matches(n=20):
    return match_log[-n:][::-1]


def get_simple_stats():
    ratings = list(elo.values())
    total = len(match_log)

    return {
        "total_matches": total,
        "avg_elo": round(sum(ratings) / len(ratings), 2),
        "max_player": max(elo.items(), key=lambda x: x[1])[0],
        "max_rating": max(ratings),
        "min_player": min(elo.items(), key=lambda x: x[1])[0],
        "min_rating": min(ratings)
    }


# 서버 시작 시 기존 CSV 기록 불러오기
load_history()
