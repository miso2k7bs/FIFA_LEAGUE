import csv
import os
from datetime import datetime

# --- 선수 목록 & 초기 Elo ---
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

import json

STATS_FILE = "player_info.json"

player_info = {name: {"strength": "", "style": ""} for name in INITIAL_ELO}


LOG_FILE = "match_log.csv"


# ==========================
# Elo 히스토리 딕셔너리 (정상 버전)
# ==========================
elo_history = {name: [] for name in INITIAL_ELO}


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


# ==========================
# CSV 불러오기 (Elo 재계산 포함)
# ==========================

def load_history():
    """CSV를 읽고 Elo/히스토리 모두 복구"""
    if not os.path.isfile(LOG_FILE):
        return

    with open(LOG_FILE, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            row["score1"] = int(row["score1"])
            row["score2"] = int(row["score2"])
            match_log.append(row)

            # Elo 재계산
            update_elo_with_score(row["p1"], row["p2"], row["score1"], row["score2"], log_save=False)


# ==========================
# ELO 계산
# ==========================

def expected(a, b):
    return 1 / (1 + 10 ** ((b - a) / 400))


K = 32


def update_elo_with_score(p1, p2, g1, g2, log_save=True):
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

    # 새 Elo 계산
    E1 = expected(R1, R2)
    E2 = expected(R2, R1)

    elo[p1] = R1 + K * (S1 - E1)
    elo[p2] = R2 + K * (S2 - E2)

    # 로그 생성
    record = {
        "p1": p1,
        "p2": p2,
        "score1": g1,
        "score2": g2,
        "result": result,
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    # 새 경기일 경우만 CSV 저장
    if log_save:
        match_log.append(record)
        save_match_to_csv(record)

    # Elo 히스토리 추가
    elo_history[p1].append((record["time"], int(elo[p1])))
    elo_history[p2].append((record["time"], int(elo[p2])))


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


# 서버 시작 시 CSV 로드 + Elo 재계산
load_history()

def save_player_info():
    with open(STATS_FILE, "w", encoding="utf-8") as f:
        json.dump(player_info, f, ensure_ascii=False, indent=2)


def load_player_info():
    if os.path.isfile(STATS_FILE):
        with open(STATS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            player_info.update(data)

# JSON 데이터 로드 실행
load_player_info()

