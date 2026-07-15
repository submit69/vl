"""
Static site generator - chay boi GitHub Actions moi ngay.
- Crawl ket qua moi
- Doi chieu du doan cu vs ket qua
- Du doan ky TIEP THEO cua ca 2 game
- Sinh public/index.html (deploy len Netlify)
"""
import sys
import os
from datetime import datetime, timezone, timedelta

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

from crawler import load_data
from app import crawl_latest, check_history, predict_today, load_predictions, GAME_NAMES, balls_html

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PUBLIC_DIR = os.path.join(BASE_DIR, 'public')

VN_TZ = timezone(timedelta(hours=7))


def build_state():
    status = []
    for game in ('645', '655'):
        try:
            new = crawl_latest(game)
            if new:
                status.append(f"{GAME_NAMES[game]}: +{len(new)} ky moi (den #{new[-1]['draw_id']})")
        except Exception as e:
            # Tang 2: mirror xoso.com.vn (ket qua TUOI, cap nhat ngay sau gio quay)
            try:
                from mirror_source import sync_from_mirror
                n = sync_from_mirror(game)
                status.append(f"{GAME_NAMES[game]}: +{n} ky (mirror xoso.com.vn)")
            except Exception as e2:
                # Tang 3: dataset cong khai (cham hon nhung khong bao gio bi chan)
                try:
                    from fallback_source import sync_from_public_dataset
                    n = sync_from_public_dataset(game)
                    status.append(f"{GAME_NAMES[game]}: +{n} ky (dataset cong khai)")
                except Exception as e3:
                    status.append(f"{GAME_NAMES[game]}: loi ca 3 nguon ({e} | {e2} | {e3})")

    check_history()

    # Predict NEXT draw for both games (regardless of weekday)
    next_preds = []
    for g in ('645', '655'):
        p = predict_today(g)
        if p:
            next_preds.append(p)

    history = load_predictions()

    latest = {}
    for game in ('645', '655'):
        data = load_data(game)
        latest[game] = [
            {'draw_id': e['draw_id'], 'date': e['date'], 'numbers': e['numbers'], 'power': e.get('power')}
            for e in data[-5:]
        ][::-1]

    scored = [p for p in history if p.get('actual')]
    match_dist = {}
    for p in scored:
        for s in p['sets']:
            m = s.get('matched', 0)
            match_dist[m] = match_dist.get(m, 0) + 1

    return {
        'now': datetime.now(VN_TZ).strftime('%d/%m/%Y %H:%M'),
        'status': status,
        'next_preds': next_preds,
        'pending': [p for p in history if not p.get('actual')],
        'latest': latest,
        'history': sorted(scored, key=lambda p: p['draw_id'], reverse=True)[:30],
        'stats': {
            'total_predictions': len(scored),
            'total_sets': sum(len(p['sets']) for p in scored),
            'match_dist': match_dist,
            'wins': sum(c for m, c in match_dist.items() if m >= 3),
        },
    }


def render_static(state):
    next_html = ''
    for p in state['next_preds']:
        sets_html = ''
        for i, s in enumerate(p['sets']):
            sets_html += f'''<div class="predset">
              <span class="setlabel">Bo {i+1}</span>
              {balls_html(s['numbers'], s.get('power'))}
              <span class="meta">T={s['sum']} | {s['odd']}L/{6-s['odd']}C</span>
            </div>'''
        power_html = ''
        if p['power_top']:
            power_html = '<div class="meta">Power goi y: ' + ', '.join(f'{n:02d}' for n in p['power_top']) + '</div>'
        next_html += f'''<div class="card">
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

    # Lich su tach theo game -> 2 tab
    hist_by_game = {'645': '', '655': ''}
    for p in state['history']:
        actual_set = set(p['actual'])
        sets_html = ''
        for s in p['sets']:
            m = s.get('matched', 0)
            badge = f'<span class="badge {"good" if m >= 3 else ("ok" if m == 2 else "")}">{m}/6</span>'
            sets_html += f'<div class="predset">{badge} {balls_html(s["numbers"], s.get("power"), hits=actual_set)}</div>'
        hist_by_game[p['game']] += f'''<div class="card">
          <h3>{p['game_name']} #{p['draw_id']} <span class="meta">du doan {p['predicted_at']}</span></h3>
          <div class="predset"><span class="setlabel">Ket qua</span> {balls_html(p['actual'], p.get('actual_power'))}</div>
          {sets_html}
        </div>'''
    for g in hist_by_game:
        if not hist_by_game[g]:
            hist_by_game[g] = '<p class="muted">Chua co lich su doi chieu.</p>'

    hist_html = f'''<div class="tabs">
      <button class="tab-btn active" onclick="showTab('645', this)">Mega 6/45</button>
      <button class="tab-btn" onclick="showTab('655', this)">Power 6/55</button>
    </div>
    <div id="tab-645" class="tab-content">{hist_by_game['645']}</div>
    <div id="tab-655" class="tab-content" style="display:none">{hist_by_game['655']}</div>'''

    st = state['stats']
    dist_html = ' | '.join(f'{m} so: {c} bo' for m, c in sorted(st['match_dist'].items(), reverse=True))
    status_html = '<br>'.join(state['status']) if state['status'] else 'Data da moi nhat'

    return f'''<!DOCTYPE html>
<html lang="vi"><head><meta charset="utf-8">
<title>Vietlott Dashboard</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
  body {{ font-family: 'Segoe UI', sans-serif; background: #0f1420; color: #e8eaf0; margin: 0; padding: 20px; max-width: 900px; margin: 0 auto; }}
  h1 {{ color: #f5c542; }} h2 {{ color: #7ecbff; border-bottom: 1px solid #2a3550; padding-bottom: 6px; }}
  h3 {{ margin: 4px 0 8px; }}
  .card {{ background: #1a2235; border-radius: 10px; padding: 14px 18px; margin: 10px 0; }}
  .half {{ display: inline-block; vertical-align: top; width: 46%; min-width: 320px; margin-right: 1%; }}
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
  .tabs {{ margin: 10px 0 4px; }}
  .tab-btn {{ background: #1a2235; color: #8a94ad; border: 1px solid #2a3550; padding: 8px 22px;
             border-radius: 8px 8px 0 0; cursor: pointer; font-size: 15px; font-weight: 600; margin-right: 4px; }}
  .tab-btn.active {{ background: #2a3550; color: #f5c542; border-bottom-color: #2a3550; }}
</style>
<script>
function showTab(game, btn) {{
  document.getElementById('tab-645').style.display = game === '645' ? '' : 'none';
  document.getElementById('tab-655').style.display = game === '655' ? '' : 'none';
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
}}
</script>
</head><body>
<h1>🎰 Vietlott Dashboard</h1>
<div class="meta">Cap nhat tu dong: {state['now']} (gio VN) — {status_html}</div>

<h2>🎯 Du doan ky tiep theo</h2>
{next_html or '<p class="muted">Chua co du doan.</p>'}

<h2>📊 Do chinh xac tich luy ({st['total_predictions']} ky, {st['total_sets']} bo)</h2>
<div class="card">
  <b>Trung Giai 3+ (3+/6 so): {st['wins']} bo</b><br>
  <span class="meta">{dist_html or 'Chua co du lieu doi chieu'}</span>
</div>

<h2>🆕 Ket qua moi nhat</h2>
{latest_html}

<h2>📜 Lich su du doan vs ket qua</h2>
{hist_html}

<div class="warn">⚠️ Xo so la NGAU NHIEN. Trang nay chi la phan tich thong ke tu dong — khong co bo so nao
"chac chan trung". Ky vong dai han la LO ~87% tien ve. Choi vui co trach nhiem, 18+!</div>
</body></html>'''


def main():
    state = build_state()
    os.makedirs(PUBLIC_DIR, exist_ok=True)
    out = os.path.join(PUBLIC_DIR, 'index.html')
    with open(out, 'w', encoding='utf-8') as f:
        f.write(render_static(state))
    print(f'Generated {out}')
    for s in state['status']:
        print(' ', s)
    print(f"  Du doan: {[p['game_name'] + ' #' + p['draw_id'] for p in state['next_preds']]}")
    print(f"  Lich su doi chieu: {state['stats']['total_predictions']} ky")


if __name__ == '__main__':
    main()
