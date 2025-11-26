from flask import Flask, render_template_string, request, redirect, url_for, session, send_file
from league_core import (
    update_elo_with_score,
    get_ranking,
    get_recent_matches,
    get_simple_stats,
    delete_last_match,
    reset_all
)

from io import BytesIO
import matplotlib.pyplot as plt

app = Flask(__name__)
app.secret_key = "admin-secret"

ADMIN_PASSWORD = "spiderman7413!"


# ==========================================================
# Elo 그래프
# ==========================================================
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


# ==========================================================
# 메인 HTML (UI 강화)
# ==========================================================
HTML_MAIN = """
<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>FIFA ELO League</title>

<style>
body {
  background: #0A0A23;
  color: white;
  font-family: 'Pretendard', sans-serif;
  padding: 20px;
  animation: fadeIn 0.5s ease-in-out;
}

@keyframes fadeIn { from {opacity:0;} to {opacity:1;} }

.card {
  background: #151537;
  border-radius: 14px;
  padding: 22px;
  margin-top: 25px;
  box-shadow: 0 0 20px rgba(155, 89, 255, 0.2);
  animation: fadeInUp 0.6s ease;
}

@keyframes fadeInUp {
  from { opacity: 0; transform: translateY(25px); }
  to { opacity: 1; transform: translateY(0); }
}

table { width: 100%; border-collapse: collapse; }
th { background: #9b59ff; padding: 10px; border-radius: 8px; }
td { padding: 10px; border-bottom: 1px solid #333; }

button {
  background: #9b59ff;
  border: none;
  padding: 10px 16px;
  border-radius: 8px;
  color: white;
  font-weight: bold;
  cursor: pointer;
}
button:hover { background: #b37dff; transform: scale(1.04); }

input, select {
  padding: 8px;
  margin-top: 5px;
  border-radius: 6px;
  border: none;
}

a { color: #9b59ff; }
</style>

</head>
<body>

{% if session.get("admin") %}
<p style="text-align:right;">
  <b style="color:#0f0;">관리자 로그인됨</b> |
  <a href="/logout">로그아웃</a>
</p>
{% else %}
<p style="text-align:right;">
  <a href="/admin/login">관리자 로그인</a>
</p>
{% endif %}

<h1 style="text-align:center; color:#9b59ff; font-size:40px;">⚽ FIFA ELO 리그</h1>

<div class="card">
{% if session.get("admin") %}
<h2>📒 경기 입력 (관리자 전용)</h2>

<form method="post" action="/add">
  <select name="p1">
    {% for n in players %}<option>{{n}}</option>{% endfor %}
  </select>
  <input type="number" name="g1" placeholder="점수">

  <select name="p2">
    {% for n in players %}<option>{{n}}</option>{% endfor %}
  </select>
  <input type="number" name="g2" placeholder="점수">

  <button>기록</button>
</form>

<br>
<button onclick="location.href='/delete_last'" style="background:#ff5555;">마지막 경기 삭제</button>
<button onclick="location.href='/reset_all'" style="background:#d9534f;">전체 초기화</button>
{% else %}
<p style="color:#bbb;">관리자만 경기 기록을 등록할 수 있습니다.</p>
{% endif %}
</div>


<div class="card">
<h2>📊 승률 예측</h2>

<select id="p1" onchange="predictRate()">
{% for n in players %}<option>{{n}}</option>{% endfor %}
</select>

<select id="p2" onchange="predictRate()">
{% for n in players %}<option>{{n}}</option>{% endfor %}
</select>

<p id="predict_box" style="margin-top:10px; color:#ccc;">선수를 선택하면 승률이 표시됩니다.</p>

<script>
function predictRate() {
  let p1 = document.getElementById("p1").value;
  let p2 = document.getElementById("p2").value;

  if (p1 === p2) {
    document.getElementById("predict_box").innerHTML = "두 선수는 서로 달라야 함.";
    return;
  }

  fetch(`/predict/${p1}/${p2}`)
    .then(r => r.json())
    .then(d => {
      document.getElementById("predict_box").innerHTML =
        `<b>${d.p1}</b>: ${d.win1}% | <b>${d.p2}</b>: ${d.win2}%`;
    });
}
</script>
</div>


<div class="card">
<h2>🏆 순위표</h2>
<table>
<tr><th>순위</th><th>이름</th><th>ELO</th></tr>
{% for i,(name,r) in ranking %}
<tr>
<td>{{i}}</td>
<td><a href="/player/{{name}}" style="color:white;">{{name}}</a></td>
<td>{{ r|round|int }}</td>
</tr>
{% endfor %}
</table>
</div>


<div class="card">
<h2>🕘 최근 경기</h2>
<ul>
{% for rec in recent %}
  <li>[{{rec.time}}] {{rec.p1}} {{rec.score1}} : {{rec.score2}} {{rec.p2}}</li>
{% endfor %}
</ul>
</div>

</body>
</html>
"""


# ==========================================================
# 메인 페이지
# ==========================================================
@app.route("/")
def index():
    ranking = list(enumerate(get_ranking(), start=1))
    recent = get_recent_matches(20)
    stats = get_simple_stats()
    return render_template_string(
        HTML_MAIN,
        players=list(elo.keys()),
        ranking=ranking,
        recent=recent,
        stats=stats
    )


# ==========================================================
# 경기 등록 (관리자)
# ==========================================================
@app.route("/add", methods=["POST"])
def add_match():
    if not session.get("admin"):
        return "권한 없음"

    p1 = request.form["p1"]
    p2 = request.form["p2"]
    g1 = int(request.form["g1"])
    g2 = int(request.form["g2"])

    if p1 == p2:
        return redirect("/")

    update_elo_with_score(p1, p2, g1, g2)
    return redirect("/")


@app.route("/delete_last")
def admin_delete_last():
    if not session.get("admin"):
        return "권한 없음"
    delete_last_match()
    return redirect("/")


@app.route("/reset_all")
def admin_reset():
    if not session.get("admin"):
        return "권한 없음"
    reset_all()
    return redirect("/")


# ==========================================================
# 승률 API
# ==========================================================
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


# ==========================================================
# 선수 프로필
# ==========================================================
@app.route("/player/<name>")
def player_profile(name):
    from league_core import match_log

    games = [g for g in match_log if g["p1"] == name or g["p2"] == name]

    wins = draws = losses = 0
    gf = ga = 0

    for g in games:
        if g["p1"] == name:
            s1, s2 = g["score1"], g["score2"]
        else:
            s1, s2 = g["score2"], g["score1"]

        gf += s1
        ga += s2

        if s1 > s2: wins += 1
        elif s1 < s2: losses += 1
        else: draws += 1

    total = wins + draws + losses
    winrate = round(wins / total * 100, 1) if total > 0 else 0

    info = player_info[name]

    return render_template_string("""
    <h1 style="color:#9b59ff;">{{name}} 선수 프로필</h1>

    <div class="card">
        <p><b>강점:</b> {{info.strength}}</p>
        <p><b>플레이 스타일:</b> {{info.style}}</p>
    </div>

    <div class="card">
        <p>총 경기: {{total}}</p>
        <p>승/무/패: {{wins}} / {{draws}} / {{losses}}</p>
        <p>득점: {{gf}} | 실점: {{ga}}</p>
        <p>승률: {{winrate}}%</p>
    </div>

    <div class="card">
        <h3>Elo 그래프</h3>
        <img src="/graph/{{name}}" width="600">
    </div>

    {% if session.get("admin") %}
    <div class="card">
        <h3>관리자 프로필 수정</h3>
        <form method="post" action="/admin/edit/{{name}}">
            <textarea name="strength" rows="3" cols="60">{{info.strength}}</textarea><br><br>
            <textarea name="style" rows="3" cols="60">{{info.style}}</textarea><br><br>
            <button>저장</button>
        </form>
    </div>
    {% endif %}

    <a href="/">← 메인으로</a>
    """,
    name=name, info=info,
    total=total, wins=wins, draws=draws, losses=losses,
    gf=gf, ga=ga, winrate=winrate)


# ==========================================================
# 프로필 수정 (관리자 전용)
# ==========================================================
@app.route("/admin/edit/<name>", methods=["POST"])
def admin_edit_profile(name):
    if not session.get("admin"):
        return "권한 없음"

    player_info[name]["strength"] = request.form["strength"]
    player_info[name]["style"] = request.form["style"]
    return redirect(f"/player/{name}")


# ==========================================================
# 그래프 이미지 제공
# ==========================================================
@app.route("/graph/<name>")
def graph(name):
    return send_file(generate_elo_graph(name), mimetype="image/png")


# ==========================================================
# 관리자 로그인
# ==========================================================
@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        if request.form["pw"] == ADMIN_PASSWORD:
            session["admin"] = True
            return redirect("/")
        return "비밀번호 오류"

    return """
    <h2>관리자 로그인</h2>
    <form method="post">
      <input name="pw" type="password" placeholder="비밀번호">
      <button>로그인</button>
    </form>
    """


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


# ==========================================================
# Run
# ==========================================================
if __name__ == "__main__":
    app.run(debug=True)
