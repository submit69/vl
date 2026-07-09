"""
Vietlott Daily Dashboard
- Tu dong crawl ket qua moi nhat
- Tu nhan biet hom nay quay gi (Mega 645: T4/T6/CN, Power 655: T3/T5/T7)
- Du doan 3 bo cho ky hom nay
- Luu lich su du doan & tu doi chieu ket qua (accuracy tracking)

Chay:  python app.py   ->  mo http://localhost:8686
"""
import sys
import os
import json
import csv
import threading
import webbrowser
from datetime import datetime, date
from http.server import HTTPServer, BaseHTTPRequestHandler

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

from crawler import get_render_info, fetch_draw, save_results, load_data
from predictor_core import generate_predictions

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PRED_FILE = os.path.join(BASE_DIR, 'data', 'predictions.json')
PORT = 8686

# Mega 6/45: Wed(2), Fri(4), Sun(6) | Power 6/55: Tue(1), Thu(3), Sat(5)  (Mon=0)
GAME_DAYS = {'645': {2, 4, 6}, '655': {1, 3, 5}}
GAME_NAMES = {'645': 'Mega 6/45', '655': 'Power 6/55'}


def todays_games():
    wd = date.today().weekday()
    return [g for g, days in GAME_DAYS.items() if wd in days]


def load_predictions():
    if os.path.exists(PRED_FILE):
        with open(PRED_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []


def save_predictions(preds):
    os.makedirs(os.path.dirname(PRED_FILE), exist_ok=True)
    with open(PRED_FILE, 'w', encoding='utf-8') as f:
        json.dump(preds, f, ensure_ascii=False, indent=1)


def existing_draw_ids(game):
    path = os.path.join(BASE_DIR, 'data', f'vietlott_{game}.csv')
    ids = set()
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            for row in csv.DictReader(f):
                ids.add(row['draw_id'])
    return ids


def crawl_latest(game, probe_ahead=8):
    """Crawl any new draws after the last saved one. Returns list of new draws."""
    data = load_data(game)
    last_id = int(data[-1]['draw_id']) if data else 0
    ri = get_render_info()
    existing = existing_draw_ids(game)
    new = []
    for num in range(last_id + 1, last_id + 1 + probe_ahead):
        gid = f'{num:05d}'
        r = fetch_draw(game, gid, ri)
        if r:
            if gid not in existing:
                save_results(game, [r])
            new.append(r)
        else:
            break
    return new


def check_history():
    """Match saved predictions against actual results; update matched counts."""
    preds = load_predictions()
    changed = False
    for p in preds:
        if p.get('actual'):
            continue
        data = load_data(p['game'])
        actual = next((e for e in data if e['draw_id'] == p['draw_id']), None)
        if actual:
            p['actual'] = actual['numbers']
            p['actual_power'] = actual.get('power')
            for s in p['sets']:
                s['matched'] = len(set(s['numbers']) & set(actual['numbers']))
                if p['game'] == '655' and s.get('power') is not None:
                    s['power_matched'] = (s['power'] == actual.get('power'))
            p['best_matched'] = max(s['matched'] for s in p['sets'])
            changed = True
    if changed:
        save_predictions(preds)
    return preds


def predict_today(game):
    """Generate + persist today's prediction for the next draw of `game`."""
    data = load_data(game)
    next_id = f"{int(data[-1]['draw_id']) + 1:05d}"
    preds = load_predictions()
    # already predicted this draw?
    for p in preds:
        if p['game'] == game and p['draw_id'] == next_id:
            return p
    result = generate_predictions(game, n_sets=3)
    if 'error' in result:
        return None
    entry = {
        'game': game,
        'game_name': GAME_NAMES[game],
        'draw_id': next_id,
        'predicted_at': datetime.now().strftime('%d/%m/%Y %H:%M'),
        'sets': result['sets'],
        'power_top': result['power_top'],
        'top15': [t['number'] for t in result['top15']],
        'win_prob_pct': result['win_prob_pct'],
        'actual': None,
    }
    preds.append(entry)
    save_predictions(preds)
    return entry


def build_dashboard():
    """Crawl, check history, predict today's games -> full state dict."""
    status = []
    for game in ('645', '655'):
        try:
            new = crawl_latest(game)
            if new:
                status.append(f"{GAME_NAMES[game]}: +{len(new)} ky moi (den #{new[-1]['draw_id']})")
        except Exception as e:
            status.append(f"{GAME_NAMES[game]}: loi crawl ({e})")

    history = check_history()

    today_g = todays_games()
    today_preds = []
    for g in today_g:
        p = predict_today(g)
        if p:
            today_preds.append(p)
        history = load_predictions()

    latest = {}
    for game in ('645', '655'):
        data = load_data(game)
        latest[game] = [
            {'draw_id': e['draw_id'], 'date': e['date'], 'numbers': e['numbers'], 'power': e.get('power')}
            for e in data[-5:]
        ][::-1]

    # accuracy stats
    scored = [p for p in history if p.get('actual')]
    total_sets = sum(len(p['sets']) for p in scored)
    match_dist = {}
    for p in scored:
        for s in p['sets']:
            m = s.get('matched', 0)
            match_dist[m] = match_dist.get(m, 0) + 1
    wins = sum(c for m, c in match_dist.items() if m >= 3)

    return {
        'now': datetime.now().strftime('%d/%m/%Y %H:%M'),
        'weekday': ['Thu 2', 'Thu 3', 'Thu 4', 'Thu 5', 'Thu 6', 'Thu 7', 'Chu nhat'][date.today().weekday()],
        'status': status,
        'today_games': [GAME_NAMES[g] for g in today_g],
        'today_preds': today_preds,
        'latest': latest,
        'history': sorted(scored, key=lambda p: p['draw_id'], reverse=True)[:20],
        'pending': [p for p in history if not p.get('actual')],
        'stats': {
            'total_predictions': len(scored),
            'total_sets': total_sets,
            'match_dist': match_dist,
            'wins': wins,
        },
    }


def balls_html(numbers, power=None, hits=None):
    hits = hits or set()
    parts = []
    for n in numbers:
        cls = 'ball hit' if n in hits else 'ball'
        parts.append(f'<span class="{cls}">{n:02d}</span>')
    if power is not None:
        parts.append(f'<span class="ball power">{power:02d}</span>')
    return ''.join(parts)


def render_html(state):
    today_html = ''
    if not state['today_preds']:
        today_html = '<p class="muted">Hom nay khong co ky quay nao (hoac chua du data).</p>'
    for p in state['today_preds']:
        sets_html = ''
        for i, s in enumerate(p['sets']):
            pw = s.get('power')
            sets_html += f'''<div class="predset">
              <span class="setlabel">Bo {i+1}</span>
              {balls_html(s['numbers'], pw)}
              <span class="meta">T={s['sum']} | {s['odd']}L/{6-s['odd']}C | score {s['avg_score']}</span>
            </div>'''
        power_html = ''
        if p['power_top']:
            power_html = '<div class="meta">Power goi y: ' + ', '.join(f'{n:02d}' for n in p['power_top']) + '</div>'
        today_html += f'''<div class="card">
          <h3>{p['game_name']} - Ky #{p['draw_id']}</h3>
          <div class="meta">Du doan luc {p['predicted_at']} | XS trung Giai 3+ (3 ve): ~{p['win_prob_pct']}%</div>
          {sets_html}{power_html}
        </div>'''

    latest_html = ''
    for game in ('645', '655'):
        rows = ''
        for e in state['latest'][game]:
            rows += f'''<tr><td>#{e['draw_id']}</td><td>{e['date']}</td>
              <td>{balls_html(e['numbers'], e.get('power'))}</td></tr>'''
        latest_html += f'''<div class="card half">
          <h3>{GAME_NAMES[game]}</h3>
          <table>{rows}</table>
        </div>'''

    hist_html = ''
    for p in state['history']:
        actual_set = set(p['actual'])
        sets_html = ''
        for i, s in enumerate(p['sets']):
            m = s.get('matched', 0)
            badge = f'<span class="badge {"good" if m >= 3 else ("ok" if m == 2 else "")}">{m}/6</span>'
            sets_html += f'<div class="predset">{badge} {balls_html(s["numbers"], s.get("power"), hits=actual_set)}</div>'
        hist_html += f'''<div class="card">
          <h3>{p['game_name']} #{p['draw_id']} <span class="meta">du doan {p['predicted_at']}</span></h3>
          <div class="predset"><span class="setlabel">Ket qua</span> {balls_html(p['actual'], p.get('actual_power'))}</div>
          {sets_html}
        </div>'''
    if not hist_html:
        hist_html = '<p class="muted">Chua co lich su doi chieu.</p>'

    pending_html = ''
    for p in state['pending']:
        sets_html = ''.join(
            f'<div class="predset">{balls_html(s["numbers"], s.get("power"))}</div>' for s in p['sets'])
        pending_html += f'''<div class="card">
          <h3>{p['game_name']} #{p['draw_id']} <span class="badge">cho ket qua</span></h3>{sets_html}
        </div>'''

    st = state['stats']
    dist_html = ' | '.join(f'{m} so: {c} bo' for m, c in sorted(st['match_dist'].items(), reverse=True))
    status_html = '<br>'.join(state['status']) if state['status'] else 'Data da moi nhat'

    return f'''<!DOCTYPE html>
<html lang="vi"><head><meta charset="utf-8">
<title>Vietlott Dashboard</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
  body {{ font-family: 'Segoe UI', sans-serif; background: #0f1420; color: #e8eaf0; margin: 0; padding: 20px; }}
  h1 {{ color: #f5c542; }} h2 {{ color: #7ecbff; border-bottom: 1px solid #2a3550; padding-bottom: 6px; }}
  h3 {{ margin: 4px 0 8px; }}
  .card {{ background: #1a2235; border-radius: 10px; padding: 14px 18px; margin: 10px 0; }}
  .half {{ display: inline-block; vertical-align: top; width: 46%; min-width: 340px; margin-right: 1%; }}
  .ball {{ display: inline-block; width: 34px; height: 34px; line-height: 34px; text-align: center;
          background: #2a3550; border-radius: 50%; margin: 2px; font-weight: 600; }}
  .ball.power {{ background: #c0392b; }}
  .ball.hit {{ background: #27ae60; }}
  .predset {{ margin: 6px 0; }}
  .setlabel {{ display: inline-block; width: 60px; color: #f5c542; font-weight: 600; }}
  .meta {{ color: #8a94ad; font-size: 13px; }}
  .muted {{ color: #8a94ad; }}
  .badge {{ background: #2a3550; padding: 2px 10px; border-radius: 12px; font-size: 13px; }}
  .badge.good {{ background: #27ae60; }} .badge.ok {{ background: #e67e22; }}
  table {{ border-collapse: collapse; }} td {{ padding: 4px 10px; }}
  .warn {{ background: #3d2b18; border-left: 4px solid #e67e22; padding: 10px 14px; border-radius: 6px; margin: 14px 0; }}
  button {{ background: #f5c542; border: 0; padding: 10px 22px; border-radius: 8px; font-weight: 700;
           cursor: pointer; font-size: 15px; }}
</style></head><body>
<h1>🎰 Vietlott Dashboard</h1>
<div class="meta">{state['weekday']}, cap nhat {state['now']} — Hom nay quay: <b>{', '.join(state['today_games']) or 'khong co'}</b></div>
<div class="meta">{status_html}</div>
<form method="POST" action="/refresh" style="margin:12px 0"><button>🔄 Crawl + Du doan lai</button></form>

<h2>📊 Thong ke do chinh xac ({st['total_predictions']} ky da doi chieu, {st['total_sets']} bo)</h2>
<div class="card">
  <b>Trung Giai 3+ (3+/6 so): {st['wins']} bo</b><br>
  <span class="meta">{dist_html or 'Chua co du lieu'}</span>
</div>

<h2>🎯 Du doan hom nay</h2>
{today_html}
{('<h2>⏳ Cho ket qua</h2>' + pending_html) if pending_html else ''}

<h2>🆕 Ket qua moi nhat</h2>
{latest_html}

<h2>📜 Lich su du doan vs ket qua</h2>
{hist_html}

<div class="warn">⚠️ Xo so la NGAU NHIEN. Day chi la phan tich thong ke — khong co bo so nao "chac chan trung".
Ky vong dai han la LO ~87% so tien mua ve. Choi vui, dung nghien!</div>
</body></html>'''


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def _send(self, html):
        body = html.encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        try:
            state = build_dashboard()
            self._send(render_html(state))
        except Exception as e:
            self._send(f'<h1>Loi</h1><pre>{e}</pre>')

    def do_POST(self):
        self.send_response(303)
        self.send_header('Location', '/')
        self.end_headers()


def main():
    print(f'Vietlott Dashboard: http://localhost:{PORT}')
    print('Ctrl+C de thoat. Moi lan mo/refresh trang = tu crawl + du doan.')
    threading.Timer(1.0, lambda: webbrowser.open(f'http://localhost:{PORT}')).start()
    HTTPServer(('127.0.0.1', PORT), Handler).serve_forever()


if __name__ == '__main__':
    main()
