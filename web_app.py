from flask import Flask, render_template_string, request, redirect, url_for, session, send_file
from league_core import (
    elo, update_elo_with_score, get_ranking,
    get_recent_matches, get_simple_stats,
    elo_history, player_info,
    reset_all, delete_last_match
)
from io import BytesIO
import matplotlib.pyplot as plt

app = Flask(__name__)
app.secret_key = "admin-secret"

ADMIN_PASSWORD = "spiderman7413!"


# ----------------------------------
# Elo 그래프 생성
# ----------------------------------
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


# ----------------------------------
# 메인 HTML
# ----------------------------------
HTML_MAIN = """
<h1>⚽ FIFA ELO 리그</h1>

{% if session.get("admin") %}
<p style="text-align:right;">
  <b style='color:#0f0;'>관리자 로그인됨</b> |
  <a href="/logout">로그아웃</a>
</p>
{% else %}
<p style="text-align:right;">
  <a href="/admin/login">관리자 로그인</a>
</p>
{% endif %}

<hr>

{% if session.get("admin") %}
<h2>📒 경기 입력 (관리자)</h2>

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

<form method="post" action="/delete_last">
  <button>마지막 경기 삭제</button>
</form>

<form method="post" action="/reset_all">
  <button>전체 초기화</button>
</form>

<hr>
{% endif %}

<h2>🏆 순위표</h2>
<table border="1" cellpadding="6">
<tr><th>순위</th><th>이름</th><th>ELO</th></tr>
{% for i,(name,r) in ranking %}
<tr>
  <td>{{i}}</td>
  <td><a href="/player/{{name}}">{{name}}</a></td>
  <td>{{r}}</td>
</tr>
{% endfor %}
</table>

<hr>

<h2>🕘 최근 경기</h2>
<ul>
{% for rec in recent %}
  <li>[{{rec.time}}] {{rec.p1}} {{rec.score1}} : {{rec.score2}} {{rec.p2}}</li>
{% endfor %}
</ul>
"""


# ----------------------------------
# 메인 페이지
# ----------------------------------
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


# ----------------------------------
# 경기 입력 (관리자)
# ----------------------------------
@app.route("/add", methods=["POST"])
def add_match():
    if not session.get("admin"):
        return "권한 없음"

    p1 = request.form.get("p1")
    p2 = request.form.get("p2")
    g1 = int(request.form.get("g1"))
    g2 = int(request.form.get("g2"))

    if p1 == p2:
        return redirect("/")

    update_elo_with_score(p1, p2, g1, g2)
    return redirect("/")


@app.route("/delete_last", methods=["POST"])
def delete_last():
    if not session.get("admin"):
        return "권한 없음"
    delete_last_match()
    return redirect("/")


@app.route("/reset_all", methods=["POST"])
def reset_all_data():
    if not session.get("admin"):
        return "권한 없음"
    reset_all()
    return redirect("/")


# ----------------------------------
# 선수 프로필 페이지
# ----------------------------------
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
    <h1>{{name}} 선수 프로필</h1>

    <p><b>강점:</b> {{info.strength}}</p>
    <p><b>플레이 스타일:</b> {{info.style}}</p>

    <hr>

    <p>총 경기: {{total}}</p>
    <p>승/무/패: {{wins}} / {{draws}} / {{losses}}</p>
    <p>득점: {{gf}} | 실점: {{ga}}</p>
    <p>승률: {{winrate}}%</p>

    <h3>Elo 그래프</h3>
    <img src="/graph/{{name}}" width="600">

    {% if session.get("admin") %}
    <hr>
    <h3>관리자 프로필 수정</h3>
    <form method="post" action="/admin/edit/{{name}}">
      <textarea name="strength" rows="3" cols="60">{{info.strength}}</textarea><br><br>
      <textarea name="style" rows="3" cols="60">{{info.style}}</textarea><br><br>
      <button>저장</button>
    </form>
    {% endif %}

    <br><a href="/">← 메인으로</a>
    """,
    name=name, info=info,
    total=total, wins=wins, draws=draws, losses=losses,
    gf=gf, ga=ga, winrate=winrate)


# ----------------------------------
# 관리자가 선수 프로필 수정
# ----------------------------------
@app.route("/admin/edit/<name>", methods=["POST"])
def admin_edit(name):
    if not session.get("admin"):
        return "권한 없음"

    player_info[name]["strength"] = request.form["strength"]
    player_info[name]["style"] = request.form["style"]

    return redirect(f"/player/{name}")


# ----------------------------------
# 그래프 PNG 제공
# ----------------------------------
@app.route("/graph/<name>")
def graph(name):
    img = generate_elo_graph(name)
    return send_file(img, mimetype="image/png")


# ----------------------------------
# 관리자 로그인
# ----------------------------------
@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        pw = request.form.get("pw")
        if pw == ADMIN_PASSWORD:
            session["admin"] = True
            return redirect("/")
        return "비밀번호 오류"

    return """
    <h2>관리자 로그인</h2>
    <form method="post">
      <input name="pw" placeholder="비밀번호">
      <button>로그인</button>
    </form>
    """


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


# ----------------------------------
# RUN
# ----------------------------------
if __name__ == "__main__":
    app.run()
