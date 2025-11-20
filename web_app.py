# web_app.py
from flask import Flask, render_template_string, request, redirect, url_for
from league_core import (
    elo, update_elo_with_score,
    get_ranking, get_recent_matches, get_simple_stats
)

app = Flask(__name__)

HTML = """
<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">

  <title>FIFA ELO 리그</title>

  <!-- 구글 폰트 -->
  <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;600;700&display=swap" rel="stylesheet">

  <style>
    body {
      font-family: 'Poppins', sans-serif;
      margin: 0;
      background: #0A0A23;
      color: white;
      padding: 20px;
    }

    h1 {
      text-align: center;
      font-weight: 700;
      font-size: 38px;
      color: #9b59ff;
      text-shadow: 0 0 10px rgba(155, 89, 255, 0.7);
    }

    .container {
      max-width: 900px;
      margin: auto;
    }

    .card {
      background: #151537;
      border-radius: 12px;
      padding: 20px;
      margin-top: 25px;
      box-shadow: 0 0 15px rgba(155, 89, 255, 0.2);
    }

    table {
      width: 100%;
      border-collapse: collapse;
      margin-top: 15px;
    }

    th {
      background: #9b59ff;
      padding: 12px;
      text-align: left;
      border-radius: 8px;
    }

    td {
      padding: 10px;
      border-bottom: 1px solid #2e2e50;
    }

    tr:hover {
      background: rgba(155, 89, 255, 0.15);
    }

    input, select, button {
      padding: 10px;
      margin: 5px 0;
      border-radius: 8px;
      border: none;
      font-size: 15px;
    }

    button {
      background: #9b59ff;
      font-weight: 600;
      cursor: pointer;
      transition: 0.2s;
    }

    button:hover {
      background: #b57dff;
      transform: scale(1.04);
    }

    .log-box {
      padding-left: 15px;
    }
  </style>
</head>

<body>
  <h1>⚽ FIFA ELO 리그</h1>

  <div class="container">

    <div class="card">
      <h2>📒 경기 입력</h2>
      <form method="post" action="{{ url_for('add_match') }}">
        <select name="p1">
          {% for name in players %}
          <option value="{{name}}">{{name}}</option>
          {% endfor %}
        </select>
        <input type="number" name="g1" placeholder="점수1">

        <br>

        <select name="p2">
          {% for name in players %}
          <option value="{{name}}">{{name}}</option>
          {% endfor %}
        </select>
        <input type="number" name="g2" placeholder="점수2">

        <br>

        <button type="submit">경기 기록</button>
      </form>
    </div>

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

    <div class="card">
      <h2>📊 통계</h2>
      <div class="log-box">
        <p>총 경기 수: {{stats.total_matches}}</p>
        <p>평균 Elo: {{stats.avg_elo}}</p>
        <p>최고 Elo: {{stats.max_player}} ({{stats.max_rating}})</p>
        <p>최저 Elo: {{stats.min_player}} ({{stats.min_rating}})</p>
      </div>
    </div>

    <div class="card">
      <h2>🕘 최근 경기 로그</h2>
      <div class="log-box">
        <ul>
        {% for rec in recent %}
          <li>[{{rec.time}}] {{rec.p1}} {{rec.score1}} : {{rec.score2}} {{rec.p2}} → {{rec.result}}</li>
        {% endfor %}
        </ul>
      </div>
    </div>

  </div>

</body>
</html>
"""

@app.route("/")
def index():
    ranking = list(enumerate(get_ranking(), start=1))
    recent = get_recent_matches(15)
    stats = get_simple_stats()

    # dict를 객체처럼 사용
    class S: pass
    s = S()
    for k, v in stats.items():
        setattr(s, k, v)

    return render_template_string(
        HTML,
        players=list(elo.keys()),
        ranking=ranking,
        recent=recent,
        stats=s
    )


@app.route("/add", methods=["POST"])
def add_match():
    p1 = request.form.get("p1")
    p2 = request.form.get("p2")
    g1 = int(request.form.get("g1"))
    g2 = int(request.form.get("g2"))

    if p1 != p2:
        update_elo_with_score(p1, p2, g1, g2)

    return redirect(url_for("index"))

if __name__ == "__main__":
    app.run(debug=True)

@app.route("/player/<name>")
def player_profile(name):
    from league_core import match_log

    # 해당 선수 경기만 필터
    games = [g for g in match_log if g["p1"] == name or g["p2"] == name]

    # 통계 계산
    wins = 0
    draws = 0
    losses = 0
    goals_for = 0
    goals_against = 0

    for g in games:
        if g["p1"] == name:
            gf = g["score1"]
            ga = g["score2"]
        else:
            gf = g["score2"]
            ga = g["score1"]

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

    return render_template_string("""
    <h1>{{name}} 선수 프로필</h1>
    <p>총 경기: {{total}}</p>
    <p>승: {{wins}}, 무: {{draws}}, 패: {{losses}}</p>
    <p>득점: {{goals_for}}, 실점: {{goals_against}}</p>
    <p>승률: {{win_rate}}%</p>

    <h2>최근 경기 기록</h2>
    <ul>
    {% for g in games[-10:] %}
        <li>[{{g.time}}] {{g.p1}} {{g.score1}} : {{g.score2}} {{g.p2}}</li>
    {% endfor %}
    </ul>

    <br>
    <a href="/">← 메인으로</a>
    """,
    name=name,
    games=games,
    wins=wins, draws=draws, losses=losses,
    goals_for=goals_for, goals_against=goals_against,
    total=total, win_rate=win_rate)
