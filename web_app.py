from db import get_db
import sqlite3

from flask import (
    Flask, render_template_string, request,
    redirect, url_for, send_file, session
)
from league_core import (
    elo, update_elo_with_score, get_ranking,
    get_recent_matches, get_simple_stats,
    elo_history, player_info,
    reset_all, delete_last_match
)
import matplotlib.pyplot as plt
from io import BytesIO

app = Flask(__name__)
app.secret_key = "fifa-secret-key-change-this"


# ============================
# Elo 그래프
# ============================
def generate_elo_graph(player_name):
    times = [t for t, _ in elo_history[player_name]]
    ratings = [r for _, r in elo_history[player_name]]

    plt.figure(figsize=(8, 4))
    plt.plot(times, ratings, marker='o')
    plt.title(f"{player_name} Elo 변화")
    plt.xticks(rotation=45)
    plt.tight_layout()

    img = BytesIO()
    plt.savefig(img, format="png")
    img.seek(0)
    plt.close()

    return img



# ============================
# 메인 HTML
# ============================
HTML_MAIN = """
<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <title>FIFA ELO 리그</title>

  <style>
    body { background:#0A0A23; color:white; padding:20px; }
    .card { background:#151537; padding:20px; border-radius:12px; margin-top:20px; }
    table { width:100%; }
    th { background:#9b59ff; padding:10px; }
    td { padding:10px; border-bottom:1px solid #333; }
  </style>
</head>

<body>

{% if session.username %}
<p style="text-align:right;">
  {{session.badge}} <b style="color:{{session.name_color}};">{{session.username}}</b>
  | 💰 {{session.money}}원
  <a href="/logout" style="color:#9b59ff; margin-left:10px;">로그아웃</a>
</p>
{% else %}
<p style="text-align:right;">
  <a href="/login" style="color:#9b59ff;">로그인</a> /
  <a href="/register" style="color:#9b59ff;">회원가입</a>
</p>
{% endif %}

<h1>⚽ FIFA ELO 리그</h1>

<div class="container">

  <div class="card">
    <h2>📒 경기 입력</h2>

    <form method="post" action="{{ url_for('add_match') }}">
      <select name="p1" onchange="updatePrediction()">
        {% for name in players %}
          <option value="{{name}}">{{name}}</option>
        {% endfor %}
      </select>

      <input type="number" name="g1" placeholder="점수1"><br>

      <select name="p2" onchange="updatePrediction()">
        {% for name in players %}
          <option value="{{name}}">{{name}}</option>
        {% endfor %}
      </select>

      <input type="number" name="g2" placeholder="점수2"><br>

      <button type="submit">경기 기록</button>
    </form>
  </div>


  {% if session.username %}
  <div class="card">
    <h2>💰 베팅하기</h2>

    <form method="post" action="/bet">
      <select name="p1">
        {% for name in players %}
          <option value="{{name}}">{{name}}</option>
        {% endfor %}
      </select>

      <select name="p2">
        {% for name in players %}
          <option value="{{name}}">{{name}}</option>
        {% endfor %}
      </select>

      <select name="pick">
        <option value="p1">왼쪽 승</option>
        <option value="p2">오른쪽 승</option>
      </select>

      <input type="number" name="amount" placeholder="베팅금액">
      <button type="submit">베팅</button>
    </form>
  </div>
  {% endif %}

  <div id="predict_box" style="margin-top:15px; font-size:14px; color:#bbb;">
    두 선수 선택 시 승률이 표시됩니다.
  </div>

  <script>
    function updatePrediction() {
      const p1 = document.querySelector("select[name='p1']").value;
      const p2 = document.querySelector("select[name='p2']").value;

      if (p1 === p2) {
        document.getElementById("predict_box").innerHTML =
          "같은 선수끼리는 경기 불가";
        return;
      }

      fetch(`/predict/${p1}/${p2}`)
        .then(r => r.json())
        .then(data => {
          document.getElementById("predict_box").innerHTML =
            `<b>${data.p1}</b>: ${data.win1}% | <b>${data.p2}</b>: ${data.win2}%`;
        });
    }
  </script>


  <div class="card">
    <h2>🏆 순위표</h2>
    <table>
      <tr><th>순위</th><th>선수</th><th>ELO</th></tr>

      {% for i, (name, rating) in ranking %}
      <tr>
        <td>{{i}}</td>
        <td>
            <a href="/player/{{name}}" style="color:white;">
              {{name}}
            </a>
        </td>
        <td>{{rating}}</td>
      </tr>
      {% endfor %}
    </table>
  </div>


  <div class="card">
    <h2>📊 통계</h2>
    <p>총 경기: {{stats.total_matches}}</p>
    <p>평균 Elo: {{stats.avg_elo}}</p>
    <p>최고 Elo: {{stats.max_player}} ({{stats.max_rating}})</p>
    <p>최저 Elo: {{stats.min_player}} ({{stats.min_rating}})</p>
  </div>


  <div class="card">
    <h2>🕘 최근 경기</h2>
    <ul>
      {% for rec in recent %}
      <li>
        [{{rec.time}}] {{rec.p1}} {{rec.score1}}
        : {{rec.score2}} {{rec.p2}}
        ({{rec.result}})
      </li>
      {% endfor %}
    </ul>
  </div>

  <p style="margin-top:20px; text-align:right; font-size:13px;">
    <a href="/shop" style="color:#9b59ff;">상점</a> |
    <a href="/rich" style="color:#9b59ff;">부자 랭킹</a> |
    <a href="/admin/login" style="color:#9b59ff;">관리자</a>
  </p>

</div>
</body>
</html>
"""

# ============================
# 메인 페이지 라우트
# ============================
@app.route("/")
def index():
    ranking = list(enumerate(get_ranking(), start=1))
    recent = get_recent_matches(15)
    stats = get_simple_stats()

    # 유저 세션 업데이트
    if "user_id" in session:
        db = get_db()
        row = db.execute("SELECT * FROM users WHERE id=?", (session["user_id"],)).fetchone()
        if row:
            session["money"] = row["money"]
            session["badge"] = row["badge"]
            session["name_color"] = row["name_color"]

    class S: pass
    s = S()
    for k, v in stats.items():
        setattr(s, k, v)

    return render_template_string(
        HTML_MAIN,
        players=list(elo.keys()),
        ranking=ranking,
        recent=recent,
        stats=s
    )


# ============================
# 승률 예측 API
# ============================
@app.route("/predict/<p1>/<p2>")
def predict(p1, p2):
    R1 = elo[p1]
    R2 = elo[p2]

    E1 = 1 / (1 + 10 ** ((R2 - R1) / 400))
    E2 = 1 - E1

    return {
        "p1": p1,
        "p2": p2,
        "win1": round(E1 * 100, 1),
        "win2": round(E2 * 100, 1)
    }


# ============================
# 경기 입력 + 베팅 정산
# ============================
# ============================
# 경기 입력 + 베팅 정산
# ============================
@app.route("/add", methods=["POST"])
def add_match():
    p1 = request.form.get("p1")
    p2 = request.form.get("p2")
    g1 = int(request.form.get("g1") or 0)
    g2 = int(request.form.get("g2") or 0)

    if not p1 or not p2 or p1 == p2:
        return redirect("/")

    update_elo_with_score(p1, p2, g1, g2)

    db = get_db()

    if g1 > g2:
        winner = "p1"
    elif g2 > g1:
        winner = "p2"
    else:
        winner = "draw"

    bets = db.execute(
        "SELECT * FROM bets WHERE p1=? AND p2=? AND result='pending'",
        (p1, p2)
    ).fetchall()

    for b in bets:
    user = db.execute(
        "SELECT * FROM users WHERE id=?",
        (b["user_id"],)
    ).fetchone()

    payout = b["amount"] * 2

    if winner == b["pick"]:
        # 승리
        db.execute(
            "UPDATE users SET money = money + ? WHERE id=?",
            (payout, user["id"])
        )
        db.execute(
            "UPDATE bets SET result='win', payout=? WHERE id=?",
            (payout, b["id"])
        )
    else:
        # 패배
        db.execute(
            "UPDATE bets SET result='lose', payout=0 WHERE id=?",
            (b["id"],)
        )

db.commit()
return redirect("/")



# ============================
# 회원가입
# ============================
@app.route("/register", methods=["GET","POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        db = get_db()
        try:
            db.execute("INSERT INTO users(username, password) VALUES (?,?)",
                       (username, password))
            db.commit()
            return redirect("/login")
        except:
            return "이미 존재하는 아이디입니다."

    return render_template_string("""
    <h1>회원가입</h1>
    <form method="post">
        <input name="username" placeholder="ID"><br>
        <input name="password" placeholder="PW"><br>
        <button>가입</button>
    </form>
    """)


# ============================
# 로그인
# ============================
@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        db = get_db()
        row = db.execute("SELECT * FROM users WHERE username=? AND password=?",
                         (username, password)).fetchone()

        if row:
            session["user_id"] = row["id"]
            session["username"] = row["username"]
            session["money"] = row["money"]
            session["badge"] = row["badge"]
            session["name_color"] = row["name_color"]
            return redirect("/")
        return "로그인 실패"

    return render_template_string("""
    <h1>로그인</h1>
    <form method="post">
        <input name="username" placeholder="ID"><br>
        <input name="password" placeholder="PW"><br>
        <button>로그인</button>
    </form>
    """)


# ============================
# 로그아웃
# ============================
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


# ============================
# 부자 랭킹
# ============================
@app.route("/rich")
def rich():
    db = get_db()
    rows = db.execute("""
        SELECT username, badge, name_color, money
        FROM users
        ORDER BY money DESC
    """).fetchall()

    return render_template_string("""
    <h1>💰 부자 랭킹</h1>
    <table>
        <tr><th>순위</th><th>유저</th><th>보유금</th></tr>
        {% for i, r in enumerate(rows, 1) %}
        <tr>
            <td>{{i}}</td>
            <td>{{r['badge']}} <b style="color:{{r['name_color']}}">{{r['username']}}</b></td>
            <td>{{r['money']}}</td>
        </tr>
        {% endfor %}
    </table>
    <a href="/">← 메인</a>
    """, rows=rows)

# ============================
# 선수 프로필
# ============================
@app.route("/player/<name>")
def player_profile(name):
    from league_core import match_log

    games = [g for g in match_log if g["p1"] == name or g["p2"] == name]

    wins = draws = losses = 0
    goals_for = goals_against = 0

    for g in games:
        if g["p1"] == name:
            gf, ga = g["score1"], g["score2"]
        else:
            gf, ga = g["score2"], g["score1"]

        goals_for += gf
        goals_against += ga

        if gf > ga:
            wins += 1
        elif gf < ga:
            losses += 1
        else:
            draws += 1

    total = wins + draws + losses
    win_rate = round((wins / total) * 100, 2) if total > 0 else 0

    db = get_db()
    user_has_challenge = False
    if "user_id" in session:
        row = db.execute(
            "SELECT challenge_ticket FROM users WHERE id=?",
            (session["user_id"],)
        ).fetchone()
        if row and row["challenge_ticket"] > 0:
            user_has_challenge = True

    return render_template_string("""
    <h1>{{name}} 선수 프로필</h1>

    <p>총 경기: {{total}}</p>
    <p>승: {{wins}}, 무: {{draws}}, 패: {{losses}}</p>
    <p>득점: {{goals_for}}, 실점: {{goals_against}}</p>
    <p>승률: {{win_rate}}%</p>

    <h2>Elo 변화</h2>
    <img src="/graph/{{name}}" style="width:100%;max-width:700px;">

    {% if session.username %}
    <h2>도전하기</h2>
    {% if user_has_challenge %}
        <form method="post" action="/challenge/{{name}}">
            <label>핸디캡 비율 (예: 1.2 → 상대 Elo ×1.2)</label><br>
            <input name="ratio" placeholder="1.0" value="1.0"><br><br>
            <button>도전장 사용하기</button>
        </form>
    {% else %}
        <p style="color:gray;">도전장을 보유하고 있지 않습니다.</p>
    {% endif %}
    {% endif %}

    <h2>최근 경기</h2>
    <ul>
    {% for g in games[-20:] %}
      <li>[{{g.time}}] {{g.p1}} {{g.score1}} : {{g.score2}} {{g.p2}}</li>
    {% endfor %}
    </ul>

    <br><a href="/">← 돌아가기</a>
    """,
    name=name,
    games=games,
    wins=wins, draws=draws, losses=losses,
    goals_for=goals_for, goals_against=goals_against,
    total=total, win_rate=win_rate,
    user_has_challenge=user_has_challenge)


# ============================
# 도전장 사용
# ============================
@app.route("/challenge/<name>", methods=["POST"])
def challenge(name):
    if "user_id" not in session:
        return redirect("/login")

    ratio = float(request.form.get("ratio", 1.0))

    if ratio < 0.5: ratio = 0.5
    if ratio > 3.0: ratio = 3.0

    db = get_db()
    row = db.execute(
        "SELECT challenge_ticket FROM users WHERE id=?",
        (session["user_id"],)
    ).fetchone()

    if not row or row["challenge_ticket"] <= 0:
        return "도전장이 없습니다."

    # 도전장 차감
    db.execute(
        "UPDATE users SET challenge_ticket = challenge_ticket - 1 WHERE id=?",
        (session["user_id"],)
    )

    # Elo 보정
    original = elo[name]
    modified = original * ratio
    elo[name] = modified

    db.commit()

    return f"{name} Elo가 {original} → {modified} 로 변형됨 (배율 {ratio})"


# ============================
# 선수 정보 수정 (프로필 수정권 필요)
# ============================
@app.route("/edit/<name>", methods=["GET", "POST"])
def edit_player(name):
    if "user_id" not in session:
        return redirect("/login")

    db = get_db()
    ticket_row = db.execute(
        "SELECT profile_ticket FROM users WHERE id=?",
        (session["user_id"],)
    ).fetchone()

    row = db.execute(
        "SELECT * FROM player_profiles WHERE name=?",
        (name,)
    ).fetchone()

    if request.method == "POST":
        if ticket_row["profile_ticket"] <= 0:
            return "프로필 수정권이 없습니다!"

        strength = request.form.get("strength", "")
        style = request.form.get("style", "")

        if row is None:
            db.execute(
                "INSERT INTO player_profiles(name, strength, style) VALUES (?,?,?)",
                (name, strength, style)
            )
        else:
            db.execute(
                "UPDATE player_profiles SET strength=?, style=? WHERE name=?",
                (strength, style, name)
            )

        db.execute(
            "UPDATE users SET profile_ticket = profile_ticket - 1 WHERE id=?",
            (session["user_id"],)
        )

        db.commit()
        return redirect(url_for("player_profile", name=name))

    strength_default = row["strength"] if row else player_info[name]["strength"]
    style_default = row["style"] if row else player_info[name]["style"]

    return render_template_string("""
    <h1>{{name}} 정보 수정</h1>

    {% if ticket_row.profile_ticket <= 0 %}
        <p style="color:red;">⚠ 프로필 수정권이 없습니다!</p>
    {% endif %}

    <form method="post">
        <p>강점:</p>
        <textarea name="strength" rows="3" cols="40">{{strength_default}}</textarea>

        <p>플레이스타일:</p>
        <textarea name="style" rows="3" cols="40">{{style_default}}</textarea>

        <br><br>
        <button type="submit">저장</button>
    </form>

    <a href="/player/{{name}}">← 돌아가기</a>
    """,
    name=name,
    ticket_row=ticket_row,
    strength_default=strength_default,
    style_default=style_default)


# ============================
# Elo 그래프 PNG 제공
# ============================
@app.route("/graph/<name>")
def graph_file(name):
    img = generate_elo_graph(name)
    return send_file(img, mimetype="image/png")


# ============================
# 상점
# ============================
@app.route("/shop")
def shop():
    if "user_id" not in session:
        return redirect("/login")

    db = get_db()
    row = db.execute("SELECT * FROM users WHERE id=?", (session["user_id"],)).fetchone()

    return render_template_string("""
    <h1>🏪 상점</h1>
    <p>보유금액: {{row.money}}원</p>

    <div>
        <h3>🎀 칭호 구매 – {{badge_price}}원</h3>
        <form method="post" action="/buy/badge">
            <input name="badge" placeholder="🔥 👑 💎 등 입력">
            <button>구매</button>
        </form>
    </div><br>

    <div>
        <h3>💰 2배 이득권 – 30,000,000원</h3>
        <form method="post" action="/buy/double">
            <button>구매</button>
        </form>
    </div><br>

    <div>
        <h3>🛡 손실 최소화권 – 30,000,000원</h3>
        <form method="post" action="/buy/risk">
            <button>구매</button>
        </form>
    </div><br>

    <div>
        <h3>⚔ 도전장 – 10,000,000원</h3>
        <form method="post" action="/buy/challenge">
            <button>구매</button>
        </form>
    </div><br>

    <div>
        <h3>📝 프로필 수정권 – 5,000,000원</h3>
        <form method="post" action="/buy/profile_ticket">
            <button>구매</button>
        </form>
    </div><br>

    <div>
        <h3>🎁 럭키박스 – 1,000,000원</h3>
        <form method="post" action="/buy/lucky">
            <button>구매</button>
        </form>
    </div>

    <br><br>
    {% if session.get("is_admin_price") %}
    <h2>관리자: 칭호 가격 수정</h2>
    <form method="post" action="/admin/badge_price">
        <input name="price" placeholder="새 가격 입력">
        <button>변경</button>
    </form>
    {% endif %}

    <a href="/">← 메인</a>
    """,
    row=row,
    badge_price=BADGE_PRICE)


# ============================
# 아이템 구매 처리
# ============================
BADGE_PRICE = 10000000  # 기본가


@app.route("/admin/badge_price", methods=["POST"])
def admin_price():
    global BADGE_PRICE
    if not session.get("is_admin"):
        return "권한 없음"

    BADGE_PRICE = int(request.form.get("price", BADGE_PRICE))
    return redirect("/shop")


@app.route("/buy/<item>", methods=["POST"])
def buy(item):
    if "user_id" not in session:
        return redirect("/login")

    db = get_db()
    user = db.execute(
        "SELECT * FROM users WHERE id=?", (session["user_id"],)
    ).fetchone()

    prices = {
        "badge": BADGE_PRICE,
        "double": 30000000,
        "risk": 30000000,
        "challenge": 10000000,
        "profile_ticket": 5000000,
        "lucky": 1000000
    }

    if item not in prices:
        return "잘못된 아이템"

    if user["money"] < prices[item]:
        return "돈 부족!"

    # 돈 차감
    db.execute("UPDATE users SET money = money - ? WHERE id=?",
               (prices[item], user["id"]))

    # 효과
    if item == "badge":
        badge = request.form.get("badge", "🔥")
        db.execute("UPDATE users SET badge=? WHERE id=?", (badge, user["id"]))

    elif item == "double":
        db.execute(
            "UPDATE users SET double_profit = double_profit + 1 WHERE id=?",
            (user["id"],)
        )

    elif item == "risk":
        db.execute(
            "UPDATE users SET risk_cancel = risk_cancel + 1 WHERE id=?",
            (user["id"],)
        )

    elif item == "challenge":
        db.execute(
            "UPDATE users SET challenge_ticket = challenge_ticket + 1 WHERE id=?",
            (user["id"],)
        )

    elif item == "profile_ticket":
        db.execute(
            "UPDATE users SET profile_ticket = profile_ticket + 1 WHERE id=?",
            (user["id"],)
        )

    elif item == "lucky":
        import random
        gain = random.randint(0, 5000000)
        db.execute(
            "UPDATE users SET money = money + ? WHERE id=?",
            (gain, user["id"])
        )

    db.commit()
    return redirect("/shop")
# ============================
# player_info 저장 함수 (누락된 부분 보완)
# ============================
import json

def save_player_info():
    with open("player_info.json", "w", encoding="utf-8") as f:
        json.dump(player_info, f, ensure_ascii=False, indent=2)


# ============================
# 관리자 로그인 (가격 수정 권한)
# ============================
@app.route("/admin/login_price", methods=["GET", "POST"])
def admin_login_price():
    if request.method == "POST":
        pw = request.form.get("password")
        if pw == "spiderman7413!":   # 가격 수정용 관리자 비번
            session["is_admin"] = True
            session["is_admin_price"] = True
            return redirect("/shop")
        return "비밀번호 오류"

    return """
    <h2>관리자 가격 수정 로그인</h2>
    <form method='post'>
        <input name='password' placeholder='비밀번호'>
        <button>로그인</button>
    </form>
    """


# ============================
# 플라스크 실행
# ============================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
