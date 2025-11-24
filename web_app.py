from db import get_db
import sqlite3

from flask import Flask, render_template_string, request, redirect, url_for, send_file, session
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


# =======================
# Elo 그래프 생성
# =======================
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


# =======================
# 메인 HTML
# =======================
HTML_MAIN = """
<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <title>FIFA ELO 리그</title>
  <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;600;700&display=swap" rel="stylesheet">

  <style>
  body {
    font-family: 'Poppins', sans-serif;
    margin: 0;
    background: #0A0A23;
    color: white;
    padding: 20px;
    animation: fadeIn 0.8s ease-in-out;
  }

  @keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
  @keyframes fadeInUp {
    from { opacity: 0; transform: translateY(25px); }
    to { opacity: 1; transform: translateY(0); }
  }

  h1 { text-align: center; font-weight: 700; font-size: 38px; color: #9b59ff; }
  .container { max-width: 900px; margin: auto; }

  .card {
    background: #151537;
    border-radius: 12px;
    padding: 20px;
    margin-top: 25px;
    box-shadow: 0 0 15px rgba(155, 89, 255, 0.2);
    animation: fadeInUp 0.6s ease-out;
  }

  table { width: 100%; border-collapse: collapse; margin-top: 15px; }
  th { background: #9b59ff; padding: 12px; text-align: left; border-radius: 8px; }
  td { padding: 10px; border-bottom: 1px solid #2e2e50; }
  tr:hover { background: rgba(155, 89, 255, 0.15); }

  input, select, button {
    padding: 10px; margin: 5px 0;
    border-radius: 8px; border: none; font-size: 15px;
  }
  button {
    background: #9b59ff; font-weight: 600; cursor: pointer;
    transition: 0.25s ease;
  }
  button:hover { background: #b57dff; transform: scale(1.04); }
  </style>
</head>

<body>
{% if session.username %}
<p style="text-align:right; font-size:14px;">
  👤 {{session.username}} | 💰 {{session.money | int}} 원
  <a href="/logout" style="color:#9b59ff; margin-left:10px;">로그아웃</a>
</p>
{% else %}
<p style="text-align:right; font-size:14px;">
  <a href="/login" style="color:#9b59ff;">로그인</a> /
  <a href="/register" style="color:#9b59ff;">회원가입</a>
</p>
{% endif %}

  <h1>⚽ FIFA ELO 리그</h1>

  <div class="container">

    <!-- ================= 경기 입력 ================ -->
    <div class="card">
      <h2>📒 경기 입력</h2>

      <form method="post" action="{{ url_for('add_match') }}">
        <select name="p1" onchange="updatePrediction()">
          {% for name in players %}
          <option value="{{name}}">{{name}}</option>
          {% endfor %}
        </select>

        <input type="number" name="g1" placeholder="점수1">

        <br>

        <select name="p2" onchange="updatePrediction()">
          {% for name in players %}
          <option value="{{name}}">{{name}}</option>
          {% endfor %}
        </select>

        <input type="number" name="g2" placeholder="점수2">

        <br>

        <button type="submit">경기 기록</button>
      </form>

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

    <br>

    <select name="pick">
      <option value="p1">왼쪽 선수 승</option>
      <option value="p2">오른쪽 선수 승</option>
    </select>

    <input type="number" name="amount" placeholder="베팅 금액">

    <br>
    <button type="submit">베팅</button>
  </form>
</div>
{% endif %}

      <!-- 🔥 승률 예측 박스 -->
      <div id="predict_box" style="margin-top:15px; font-size:14px; color:#aaa;">
        상대 선택하면 승률이 표시됩니다.
      </div>

      <script>
      function updatePrediction() {
        const p1 = document.querySelector("select[name='p1']").value;
        const p2 = document.querySelector("select[name='p2']").value;

        if (p1 === p2) {
          document.getElementById("predict_box").innerHTML =
            "두 선수는 서로 다른 선수여야 합니다.";
          return;
        }

        fetch(`/predict/${p1}/${p2}`)
          .then(res => res.json())
          .then(data => {
            document.getElementById("predict_box").innerHTML =
              `예상 승률 → <b>${data.p1}</b>: ${data.win1}% &nbsp; | &nbsp;
               <b>${data.p2}</b>: ${data.win2}%`;
          });
      }
      </script>
    </div>

    <!-- ================= 순위표 ================= -->
    <div class="card">
      <h2>🏆 현재 순위</h2>
      <table>
        <tr><th>순위</th><th>선수</th><th>ELO</th></tr>
        {% for i, (name, rating) in ranking %}
        <tr>
          <td>{{i}}</td>
          <td><a href="/player/{{name}}" style="color:white;">{{name}}</a></td>
          <td>{{rating | int}}</td>
        </tr>
        {% endfor %}
      </table>
    </div>

    <!-- ================= 통계 ================= -->
    <div class="card">
      <h2>📊 통계</h2>
      <p>총 경기 수: {{stats.total_matches}}</p>
      <p>평균 Elo: {{stats.avg_elo}}</p>
      <p>최고 Elo: {{stats.max_player}} ({{stats.max_rating}})</p>
      <p>최저 Elo: {{stats.min_player}} ({{stats.min_rating}})</p>
    </div>

    <!-- ================= 최근 경기 ================= -->
    <div class="card">
      <h2>🕘 최근 경기 로그</h2>
      <ul>
      {% for rec in recent %}
        <li>
          [{{rec.time}}] {{rec.p1}} {{rec.score1}} : {{rec.score2}} {{rec.p2}} → {{rec.result}}
          <a href="/edit_match/{{loop.index0}}" style="color:#9b59ff; margin-left:10px;">수정</a>
        </li>
      {% endfor %}
      </ul>
    </div>

    <p style="margin-top:20px; text-align:right; font-size:12px;">
      <a href="/admin/login" style="color:#666;">관리자 로그인</a>
    </p>

  </div>
</body>
</html>
"""


# =======================
# 메인 페이지
# =======================
@app.route("/")
def index():
    ranking = list(enumerate(get_ranking(), start=1))
    recent = get_recent_matches(15)
    stats = get_simple_stats()

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

@app.route("/bet_ratio/<p1>/<p2>")
def bet_ratio(p1, p2):
    db = get_db()
    rows = db.execute(
        "SELECT pick, SUM(amount) AS total FROM bets WHERE p1=? AND p2=? GROUP BY pick",
        (p1, p2)
    ).fetchall()

    t1 = t2 = 0

    for r in rows:
        if r["pick"] == "p1":
            t1 = r["total"]
        else:
            t2 = r["total"]

    total = t1 + t2
    if total == 0:
        return {"p1": 50, "p2": 50}

    return {
        "p1": round(t1 / total * 100, 1),
        "p2": round(t2 / total * 100, 1)
    }

# =======================
# 경기 입력
# =======================
@app.route("/add", methods=["POST"])
def add_match():
    p1 = request.form.get("p1")
    p2 = request.form.get("p2")
    g1 = int(request.form.get("g1"))
    g2 = int(request.form.get("g2"))

    if p1 != p2:
        update_elo_with_score(p1, p2, g1, g2)
# ===== 베팅 정산 =====
db = get_db()
winner = "p1" if g1 > g2 else "p2"

bets = db.execute(
    "SELECT * FROM bets WHERE p1=? AND p2=? AND result='pending'",
    (p1, p2)
).fetchall()

for b in bets:
    if b["pick"] == winner:
        # 승리 → 배당 2배 (원하면 나중에 Elo 기반으로 바꿔줌)
        payout = b["amount"] * 2
        db.execute("UPDATE users SET money = money + ? WHERE id=?",
                   (payout, b["user_id"]))
        db.execute("UPDATE bets SET result='win', payout=? WHERE id=?",
                   (payout, b["id"]))
    else:
        db.execute("UPDATE bets SET result='lose' WHERE id=?", (b["id"],))

db.commit()

    return redirect(url_for("index"))


# =======================
# 예측 API
# =======================
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


# =======================
# 관리자 로그인
# =======================
@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    error = None
    if request.method == "POST":
        pw = request.form.get("password")
        if pw == "spiderman7413!":
            session["is_admin"] = True
            return redirect(url_for("admin_panel"))
        else:
            error = "비밀번호가 틀렸습니다."

    return render_template_string("""
    <h1>관리자 로그인</h1>
    {% if error %}<p style="color:red;">{{error}}</p>{% endif %}
    <form method="post">
      <input type="password" name="password" placeholder="비밀번호">
      <button type="submit">로그인</button>
    </form>
    <a href="/">← 메인으로</a>
    """, error=error)


# =======================
# 관리자 패널
# =======================
@app.route("/admin")
def admin_panel():
    if not session.get("is_admin"):
        return redirect(url_for("admin_login"))

    return render_template_string("""
    <h1>관리자 패널</h1>

    <form method="post" action="{{ url_for('admin_reset') }}">
      <button type="submit" style="background:#e74c3c; color:white; padding:10px 20px; border:none; border-radius:8px;">
        ⚠ 전체 초기화
      </button>
    </form>

    <br>

    <form method="post" action="{{ url_for('admin_delete_last') }}">
      <button type="submit" style="background:#f1c40f; color:black; padding:10px 20px; border:none; border-radius:8px;">
        ⏪ 마지막 경기 삭제
      </button>
    </form>

    <br><br>
    <a href="/">← 메인으로</a>
    """)


@app.route("/admin/reset", methods=["POST"])
def admin_reset():
    if not session.get("is_admin"):
        return redirect(url_for("admin_login"))

    reset_all()
    return redirect(url_for("admin_panel"))


@app.route("/admin/delete_last", methods=["POST"])
def admin_delete_last():
    if not session.get("is_admin"):
        return redirect(url_for("admin_login"))

    delete_last_match()
    return redirect(url_for("admin_panel"))


# =======================
# 선수 프로필
# =======================
@app.route("/player/<name>")
def player_profile(name):
    from league_core import match_log, player_info

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

        if gf > ga: wins += 1
        elif gf < ga: losses += 1
        else: draws += 1

    total = wins + draws + losses
    win_rate = round((wins / total) * 100, 2) if total > 0 else 0

    return render_template_string("""
    <h1>{{name}} 선수 프로필</h1>

    <p>총 경기: {{total}}</p>
    <p>승: {{wins}}, 무: {{draws}}, 패: {{losses}}</p>
    <p>득점: {{goals_for}}, 실점: {{goals_against}}</p>
    <p>승률: {{win_rate}}%</p>

    <h2>강점(Strength)</h2>
    <p>{{info.strength}}</p>

    <h2>플레이스타일(Style)</h2>
    <p>{{info.style}}</p>

    <a href="/edit/{{name}}" style="color:#9b59ff;">✏ 정보 수정</a>

    <h2>Elo 변화</h2>
    <img src="/graph/{{name}}" style="width:100%; max-width:700px;">

    <h2>최근 경기</h2>
    <ul>
    {% for g in games[-15:] %}
      <li>[{{g.time}}] {{g.p1}} {{g.score1}} : {{g.score2}} {{g.p2}}</li>
    {% endfor %}
    </ul>

    <br><a href="/">← 메인으로</a>
    """,
    name=name,
    info=player_info[name],
    games=games,
    wins=wins, draws=draws, losses=losses,
    goals_for=goals_for, goals_against=goals_against,
    total=total, win_rate=win_rate)


# =======================
# 선수 정보 수정
# =======================
@app.route("/edit/<name>", methods=["GET", "POST"])
def edit_player(name):
    from league_core import player_info, save_player_info

    if request.method == "POST":
        player_info[name]["strength"] = request.form.get("strength")
        player_info[name]["style"] = request.form.get("style")
        save_player_info()
        return redirect(url_for("player_profile", name=name))

    return render_template_string("""
    <h1>{{name}} 정보 수정</h1>

    <form method="post">
      <p>강점:</p>
      <textarea name="strength" rows="3" cols="40">{{info.strength}}</textarea>

      <p>플레이스타일:</p>
      <textarea name="style" rows="3" cols="40">{{info.style}}</textarea>

      <br><br>
      <button type="submit">저장</button>
    </form>

    <a href="/player/{{name}}">← 돌아가기</a>
    """,
    name=name,
    info=player_info[name])


# =======================
# Elo 그래프 PNG 제공
# =======================
@app.route("/graph/<name>")
def graph_file(name):
    img = generate_elo_graph(name)
    return send_file(img, mimetype="image/png")


# =======================
# 앱 실행
# =======================
if __name__ == "__main__":
    app.run(debug=True)

# ===============================
# 회원가입
# ===============================
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


# ===============================
# 로그인
# ===============================
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


# ===============================
# 로그아웃
# ===============================
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")
@app.route("/bet", methods=["POST"])
def bet():
    if "user_id" not in session:
        return redirect("/login")

    user_id = session["user_id"]
    p1 = request.form["p1"]
    p2 = request.form["p2"]
    pick = request.form["pick"]
    amount = int(request.form["amount"])

    db = get_db()
    user_money = db.execute(
        "SELECT money FROM users WHERE id=?", (user_id,)
    ).fetchone()["money"]

    if user_money < amount:
        return "잔액 부족!"

    db.execute("INSERT INTO bets(user_id, p1, p2, pick, amount) VALUES (?,?,?,?,?)",
               (user_id, p1, p2, pick, amount))

    db.execute("UPDATE users SET money = money - ? WHERE id=?", (amount, user_id))

    db.commit()

    return redirect("/")
@app.route("/shop")
def shop():
    if "user_id" not in session:
        return redirect("/login")

    return render_template_string("""
    <h1>🏪 상점</h1>

    <p>보유금액: {{session.money}}원</p>

    <div>
        <h3>🎁 럭키박스 - 1,000,000원</h3>
        <form method="post" action="/buy/lucky">
            <button>구매</button>
        </form>
    </div>

    <div>
        <h3>💎 VIP 칭호 - 5,000,000원</h3>
        <form method="post" action="/buy/vip">
            <button>구매</button>
        </form>
    </div>

    <div>
        <h3>🎨 닉네임 색상 변경 - 2,000,000원</h3>
        <form method="post" action="/buy/color">
            <input name="color" placeholder="#ff0000">
            <button>구매</button>
        </form>
    </div>

    <br>
    <a href="/">← 메인으로</a>
    """)
@app.route("/buy/<item>", methods=["POST"])
def buy(item):
    if "user_id" not in session:
        return redirect("/login")

    user_id = session["user_id"]
    db = get_db()
    user = db.execute(
        "SELECT * FROM users WHERE id=?", (user_id,)
    ).fetchone()
    money = user["money"]

    # 아이템 가격 설정
    price = {
        "lucky": 1000000,
        "vip": 5000000,
        "color": 2000000
    }.get(item, None)

    if price is None:
        return "없는 아이템입니다."

    if money < price:
        return "돈 부족!"

    # 돈 차감
    db.execute("UPDATE users SET money = money - ? WHERE id=?", (price, user_id))

    # 아이템 효과 적용
    if item == "lucky":
        import random
        gain = random.randint(0, 3000000)
        db.execute("UPDATE users SET money = money + ? WHERE id=?", (gain, user_id))

    elif item == "vip":
        db.execute("UPDATE users SET is_admin = 1 WHERE id=?", (user_id,))

    elif item == "color":
        color = request.form.get("color")
        db.execute("UPDATE users SET name_color=? WHERE id=?", (color, user_id))

    db.commit()

    return redirect("/shop")
