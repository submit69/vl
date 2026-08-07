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
from app import (crawl_latest, check_history, predict_today, load_predictions,
                 GAME_NAMES, GAMES, balls_html)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PUBLIC_DIR = os.path.join(BASE_DIR, 'public')

VN_TZ = timezone(timedelta(hours=7))


def build_state():
    status = []
    for game in GAMES:
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
    for g in GAMES:
        p = predict_today(g)
        if p:
            next_preds.append(p)

    history = load_predictions()

    latest = {}
    for game in GAMES:
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

    try:
        from budget import compute as budget_compute
        budget_info = budget_compute(history)
    except Exception:
        budget_info = None

    return {
        'budget': budget_info,
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
              <span class="meta">T={s['sum']} | {s['odd']}L/{len(s['numbers'])-s['odd']}C</span>
            </div>'''
        power_html = ''
        if p['power_top']:
            power_html = '<div class="meta">Power goi y: ' + ', '.join(f'{n:02d}' for n in p['power_top']) + '</div>'

        wheel_html = ''
        wheel_defs = [
            ('wheel', '🎡 Wheel 8 so', 'DAM BAO 3-if-3: ≥3 so pool xuat hien → chac chan ≥1 ve trung Giai 3'),
            ('wheel12', '🎡 Wheel 12 so', 'DAM BAO 3-if-4: ≥4 so pool ra → chac chan co giai; dung 3 so ra → ~70% co giai'),
        ]
        for key, title, note in wheel_defs:
            w = p.get(key)
            if not w:
                continue
            wt = ''
            for i, t in enumerate(w['tickets']):
                wt += f'<div class="predset"><span class="setlabel">Ve {i+1}</span> {balls_html(t)}</div>'
            wheel_html += f'''<div class="wheel">
              <h4>{title} ({len(w['tickets'])} ve - {len(w['tickets'])*10}k)</h4>
              <div class="predset"><span class="setlabel">Pool</span> {balls_html(w['pool'])}</div>
              {wt}
              <div class="meta">{note}</div>
            </div>'''

        anti_html = ''
        a = p.get('antishare')
        if a:
            if p['game'] == '535':
                evidence = ('Lotto 5/35 moi ra 06/2025 nen chua co du lieu winner de kiem chung '
                            'hieu ung chia giai. Bo nay van ne ngay sinh / so phong thuy theo mo hinh chung.')
            elif p['game'] == '645':
                evidence = ('Kiem chung TOAN BO 1,542 ky: ky ra nhieu so pho bien co +16% nguoi trung, '
                            'va hieu ung DANG MANH LEN (3 nam gan nhat: +18%). Vi du ky 05-08-09-11-20-29 '
                            'co 72,470 nguoi trung G3 vs 13,945 cua ky toan so cao - chenh 5.2 lan.')
            else:
                evidence = ('Kiem chung 1,378 ky: hieu ung tung manh (+22% giai doan 2017-2020) nhung '
                            'DANG PHAI NHAT (3 nam gan nhat chi +2%) - nguoi choi 6/55 ngay cang chon ngau nhien. '
                            'Bo nay huu ich voi 6/45 hon.')
            anti_html = f'''<div class="wheel">
              <h4>💎 Bo Jackpot thong minh (anti-share)</h4>
              <div class="predset"><span class="setlabel">Ve</span> {balls_html(a['numbers'], a.get('power'))}</div>
              <div class="meta">Bo so IT NGUOI CUNG DANH nhat (ne ngay sinh, so phong thuy, pattern dep).
              Xac suat trung khong doi - nhung NEU trung jackpot thi kha nang an tron cao hon
              (share_score={a['share_score']} vs ~13-18 cua bo pho bien). {evidence}</div>
            </div>'''

        next_html += f'''<div class="card">
          <h3>{p['game_name']} - Ky #{p['draw_id']}</h3>
          <div class="meta">Du doan luc {p['predicted_at']} | XS trung Giai 3+ (3 ve): ~{p['win_prob_pct']}%</div>
          {sets_html}{power_html}{wheel_html}{anti_html}
        </div>'''

    latest_html = ''
    for game in GAMES:
        rows = ''
        for e in state['latest'][game]:
            rows += f'''<tr><td>#{e['draw_id']}</td><td>{e['date']}</td>
              <td>{balls_html(e['numbers'], e.get('power'))}</td></tr>'''
        latest_html += f'''<div class="card half">
          <h3>{GAME_NAMES[game]}</h3>
          <table>{rows}</table>
        </div>'''

    # Lich su tach theo game -> 2 tab
    hist_by_game = {g: '' for g in GAMES}
    for p in state['history']:
        actual_set = set(p['actual'])
        sets_html = ''
        for s in p['sets']:
            m = s.get('matched', 0)
            k = len(s['numbers'])
            badge = f'<span class="badge {"good" if m >= 3 else ("ok" if m == 2 else "")}">{m}/{k}</span>'
            sets_html += f'<div class="predset">{badge} {balls_html(s["numbers"], s.get("power"), hits=actual_set)}</div>'
        wheel_hist = ''
        for key, label in (('wheel', 'Wheel 8'), ('wheel12', 'Wheel 12')):
            w = p.get(key)
            if not (w and 'matched' in w):
                continue
            g_ok = w.get('guarantee_ok', True)
            wt = ''
            for i, t in enumerate(w['tickets']):
                m = w['matched'][i]
                badge = f'<span class="badge {"good" if m >= 3 else ("ok" if m == 2 else "")}">{m}/6</span>'
                wt += f'<div class="predset">{badge} {balls_html(t, hits=actual_set)}</div>'
            g_badge = '' if g_ok else ' <span class="badge">LOI DAM BAO?!</span>'
            wheel_hist += f'''<div class="wheel">
              <h4>🎡 {label}: pool trung {w['pool_hits']}/{len(w['pool'])} so{g_badge}</h4>
              {wt}
            </div>'''
        anti_hist = ''
        a = p.get('antishare')
        if a and 'matched' in a:
            m = a['matched']
            k = len(a['numbers'])
            badge = f'<span class="badge {"good" if m >= 3 else ("ok" if m == 2 else "")}">{m}/{k}</span>'
            anti_hist = f'<div class="predset">{badge} 💎 {balls_html(a["numbers"], a.get("power"), hits=actual_set)}</div>'
        hist_by_game[p['game']] += f'''<div class="card">
          <h3>{p['game_name']} #{p['draw_id']} <span class="meta">du doan {p['predicted_at']}</span></h3>
          <div class="predset"><span class="setlabel">Ket qua</span> {balls_html(p['actual'], p.get('actual_power'))}</div>
          {sets_html}{anti_hist}{wheel_hist}
        </div>'''
    for g in hist_by_game:
        if not hist_by_game[g]:
            hist_by_game[g] = '<p class="muted">Chua co lich su doi chieu.</p>'

    btns, panes = '', ''
    for i, g in enumerate(GAMES):
        active = ' active' if i == 0 else ''
        hidden = '' if i == 0 else ' style="display:none"'
        btns += ('<button class="tab-btn' + active + '" '
                 "onclick=\"showTab('" + g + "', this)\">" + GAME_NAMES[g] + '</button>')
        panes += ('<div id="tab-' + g + '" class="tab-content"' + hidden + '>'
                  + hist_by_game[g] + '</div>')
    hist_html = '<div class="tabs">' + btns + '</div>' + panes

    st = state['stats']
    dist_html = ' | '.join(f'{m} so: {c} bo' for m, c in sorted(st['match_dist'].items(), reverse=True))
    status_html = '<br>'.join(state['status']) if state['status'] else 'Data da moi nhat'

    # ── Budget tracker panel ──
    budget_html = ''
    b = state.get('budget')
    if b and b['total']['draws']:
        t = b['total']
        cfg = b['config']
        rows = ''
        for m in b['months']:
            cls = ' style="color:#e74c3c;font-weight:600"' if m['over'] else ''
            flag = ' ⚠ VUOT TRAN' if m['over'] else ''
            rows += (f"<tr{cls}><td>{m['month']}</td><td>{m['cost_k']}k ({m['limit_pct']}%)</td>"
                     f"<td>{m['prize_k']}k</td><td>{m['net_k']:+}k</td><td>{m['draws']} ky{flag}</td></tr>")
        warn = ''
        if t['yearly_k'] >= 5000:
            warn = ('<div class="warn">⚠ Nhip nay ~%s k/nam. Neu con so nay lam ban giat minh, '
                    'do la tin hieu nen giam xuong 1 ve/tuan.</div>' % f"{t['yearly_k']:,}")
        budget_html = f'''
<h2>💰 Budget Tracker</h2>
<div class="card">
  <div class="meta">Chien luoc theo doi: <b>{b['strategy_label']}</b> | Game: {', '.join(cfg['games'])}
  | Tran thang: <b>{cfg['monthly_limit_k']}k</b> <span class="muted">(sua trong data/budget.json)</span></div>
  <div class="predset" style="margin-top:10px">
    <span class="bstat">Da chi<b>{t['cost_k']}k</b></span>
    <span class="bstat">Thu ve<b>{t['prize_k']}k</b></span>
    <span class="bstat">Net<b style="color:{'#27ae60' if t['net_k'] >= 0 else '#e74c3c'}">{t['net_k']:+}k</b></span>
    <span class="bstat">ROI<b style="color:{'#27ae60' if t['roi_pct'] >= 0 else '#e74c3c'}">{t['roi_pct']:+}%</b></span>
    <span class="bstat">Ve trung giai<b>{t['wins']}/{t['tickets']}</b></span>
  </div>
  <table style="margin-top:10px"><tr><th>Thang</th><th>Chi (% tran)</th><th>Thu</th><th>Net</th><th></th></tr>{rows}</table>
  {warn}
</div>'''

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
  .bstat {{ display: inline-block; background: #2a3550; border-radius: 8px; padding: 8px 16px;
           margin: 4px 6px 4px 0; font-size: 13px; color: #8a94ad; }}
  .bstat b {{ display: block; font-size: 19px; color: #e8eaf0; margin-top: 2px; }}
  th {{ text-align: left; color: #8a94ad; font-weight: 600; font-size: 13px; padding: 4px 10px; }}
  .wheel {{ border-top: 1px dashed #2a3550; margin-top: 10px; padding-top: 8px; }}
  .wheel h4 {{ margin: 4px 0 8px; color: #7ecbff; }}
  .tabs {{ margin: 10px 0 4px; }}
  .tab-btn {{ background: #1a2235; color: #8a94ad; border: 1px solid #2a3550; padding: 8px 22px;
             border-radius: 8px 8px 0 0; cursor: pointer; font-size: 15px; font-weight: 600; margin-right: 4px; }}
  .tab-btn.active {{ background: #2a3550; color: #f5c542; border-bottom-color: #2a3550; }}
</style>
<script>
function showTab(game, btn) {{
  document.querySelectorAll('.tab-content').forEach(el => {{
    el.style.display = (el.id === 'tab-' + game) ? '' : 'none';
  }});
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
{budget_html}

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
