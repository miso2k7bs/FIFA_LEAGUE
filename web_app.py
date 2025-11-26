from flask import Flask, render_template_string, request, redirect, session, jsonify
from league_core import (
    init_db,
    get_rating,
    get_all_ratings,
    update_elo,
    get_match_history,
    get_player_history,
    save_player_info,
    load_player_info
)

import math

app = Flask(__name__)
app.secret_key = "super_secret_key_abc123"

init_db()

# ------------------------------------------------------------
# HTML 템플릿
# ------------------------------------------------------------
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

<!-- 관리자 경기 입력 -->
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
{% else %}
<p style="color:#bbb;">관리자만 경기 기록을 등록할 수 있습니다.</p>
{% endif %}
</div>

<!-- 승률 예측 -->
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

<!-- 순위 -->
<div class="card">
<h2>🏆 순위표</h2>
<table>
<tr><th>순위</th><th>이름</th><th>ELO</th><th>프로필</th></tr>
{% for i,(name,r) in ranking %}
<tr>
<td>{{i}}</td>
<td>{{name}}</td>
<td>{{r}}</td>
<td><button onclick="location.href='/player/{{name}}'">보기</button></td>
</tr>
{% endfor %}
</table>
</div>

<!-- 최근 경기 -->
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

# ------------------------------------------------------------
# 라우트
# ------------------------------------------------------------

@app.route("/")
def index():
    ratings = get_all_ratings()
    ranking = []
    idx = 1
    for name, r in ratings.items():
        ranking.append((idx, name, round(r)))
        idx += 1

    players = list(ratings.keys())
    recent = get_match_history(20)

    return render_template_string(HTML_MAIN, players=players, ranking=ranking, recent=recent)

@app.route("/predict/<p1>/<p2>")
def predict(p1, p2):
    r1 = get_rating(p1)
    r2 = get_rating(p2)

    e1 = 1 / (1 + 10 ** ((r2 - r1) / 400))
    e2 = 1 - e1

    return jsonify({
        "p1": p1,
        "p2": p2,
        "win1": round(e1 * 100),
        "win2": round(e2 * 100)
    })

@app.route("/add", methods=["POST"])
def add_match():
    if not session.get("admin"):
        return "권한 없음"

    p1 = request.form["p1"]
    p2 = request.form["p2"]
    g1 = int(request.form["g1"])
    g2 = int(request.form["g2"])

    update_elo(p1, p2, g1, g2)

    return redirect("/")

# ------------------------------------------------------------
# 프로필 페이지
# ------------------------------------------------------------

PROFILE_HTML = """
<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>{{player}} 프로필</title>
<style>
body {
  background:#0A0A23;
  color:white;
  padding:20px;
  font-family:'Pretendard';
}
.card {
  background:#151537;
  padding:20px;
  border-radius:14px;
  margin-top:20px;
}
button {
  background:#9b59ff;
  padding:10px 15px;
  border:none;
  border-radius:8px;
  color:white;
  cursor:pointer;
}
</style>
</head>
<body>

<h1 style="color:#9b59ff;">{{player}} 프로필</h1>

<div class="card">
<p><b>현재 Elo:</b> {{elo}}</p>
<p><b>강점:</b> {{strength}}</p>
<p><b>단점:</b> {{weakness}}</p>
<p><b>스타일:</b> {{style}}</p>
</div>

{% if session.get("admin") %}
<div class="card">
<h3>수정하기</h3>
<form method="post">
  강점:<br><input name="strength" value="{{strength}}"><br><br>
  단점:<br><input name="weakness" value="{{weakness}}"><br><br>
  스타일:<br><input name="style" value="{{style}}"><br><br>
  <button>저장</button>
</form>
</div>
{% endif %}

<br>
<button onclick="location.href='/'">⬅ 돌아가기</button>

</body>
</html>
"""

@app.route("/player/<player>", methods=["GET", "POST"])
def player_profile(player):
    if request.method == "POST":
        if not session.get("admin"):
            return "권한 없음"

        strength = request.form["strength"]
        weakness = request.form["weakness"]
        style = request.form["style"]
        save_player_info(player, strength, weakness, style)

    info = load_player_info(player)
    elo = round(get_rating(player))

    return render_template_string(
        PROFILE_HTML,
        player=player,
        elo=elo,
        strength=info.get("strength", ""),
        weakness=info.get("weakness", ""),
        style=info.get("style", "")
    )

# ------------------------------------------------------------
# 관리자 로그인
# ------------------------------------------------------------
@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        if request.form["pw"] == "admin123":
            session["admin"] = True
            return redirect("/")
        return "비밀번호 오류"

    return """
    <form method='post'>
      <input type='password' name='pw' placeholder='관리자 비번'>
      <button>로그인</button>
    </form>
    """

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

# ------------------------------------------------------------
# 시작
# ------------------------------------------------------------
if __name__ == "__main__":
    app.run(debug=True)
