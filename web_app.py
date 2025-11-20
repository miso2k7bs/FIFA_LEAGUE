# web_app.py
import os, sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

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
</head>
<body>
  <h1>FIFA ELO 리그 (웹 버전)</h1>

  <h2>경기 입력</h2>
  <form method="post" action="{{ url_for('add_match') }}">
    선수1:
    <select name="p1">
      {% for name in players %}
      <option value="{{name}}">{{name}}</option>
      {% endfor %}
    </select>
    점수1: <input type="number" name="g1" style="width:50px;">
    <br>
    선수2:
    <select name="p2">
      {% for name in players %}
      <option value="{{name}}">{{name}}</option>
      {% endfor %}
    </select>
    점수2: <input type="number" name="g2" style="width:50px;">
    <br>
    <button type="submit">경기 기록</button>
  </form>

  <h2>현재 순위</h2>
  <table border="1" cellpadding="5">
    <tr><th>순위</th><th>이름</th><th>Elo</th></tr>
    {% for (name, rating) in ranking %}
    <tr>
      <td>{{ loop.index }}</td>
      <td>{{ name }}</td>
      <td>{{ rating|int }}</td>
    </tr>
    {% endfor %}
  </table>

  <h2>통계</h2>
  <ul>
    <li>총 경기 수: {{stats.total_matches}}</li>
    <li>평균 Elo: {{stats.avg_elo}}</li>
    <li>최고 Elo: {{stats.max_player}} ({{stats.max_rating}})</li>
    <li>최저 Elo: {{stats.min_player}} ({{stats.min_rating}})</li>
  </ul>

  <h2>최근 경기 로그</h2>
  <ul>
    {% for rec in recent %}
      <li>[{{rec.time}}] {{rec.p1}} {{rec.score1}} : {{rec.score2}} {{rec.p2}} -> {{rec.result}}</li>
    {% endfor %}
  </ul>

</body>
</html>
"""


@app.route("/")
def index():
    ranking = get_ranking()
    recent = get_recent_matches(15)
    stats = get_simple_stats()

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
