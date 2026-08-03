"""
Budget Tracker - bien su tu giac thanh con so nhin thay duoc.

Khai bao trong data/budget.json:
  {
    "monthly_limit_k": 100,        # tran chi moi thang (nghin dong)
    "strategy": "sets",            # ban thuc su mua theo gi:
                                   #   "sets"     = 3 bo thong ke (30k/ky)
                                   #   "wheel"    = wheel 8 so  (40k/ky)
                                   #   "wheel12"  = wheel 12 so (80k/ky)
                                   #   "antishare"= 1 ve anti-share (10k/ky)
                                   #   "one"      = 1 ve dau tien cua 3 bo (10k/ky)
                                   #   "none"     = khong mua, chi theo doi
    "games": ["645"]               # game nao ban mua
  }

Tinh chi/thu THUC TE tu lich su du doan da doi chieu (predictions.json).
Gia ve 10.000d. Giai: 645 = G3 30k / G2 300k / G1 10tr ; 655 = 50k / 500k / 40tr
"""
import json
import os
from collections import defaultdict

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BUDGET_FILE = os.path.join(BASE_DIR, 'data', 'budget.json')
TICKET_PRICE_K = 10  # nghin dong

PRIZE_K = {
    '645': {3: 30, 4: 300, 5: 10_000, 6: None},      # None = jackpot (bien doi)
    '655': {3: 50, 4: 500, 5: 40_000, 6: None},
}

DEFAULTS = {
    'monthly_limit_k': 100,
    'strategy': 'sets',
    'games': ['645'],
}


def load_config():
    cfg = dict(DEFAULTS)
    if os.path.exists(BUDGET_FILE):
        try:
            with open(BUDGET_FILE, 'r', encoding='utf-8') as f:
                cfg.update(json.load(f))
        except (json.JSONDecodeError, OSError):
            pass
    return cfg


def save_config(cfg):
    os.makedirs(os.path.dirname(BUDGET_FILE), exist_ok=True)
    with open(BUDGET_FILE, 'w', encoding='utf-8') as f:
        json.dump(cfg, f, ensure_ascii=False, indent=1)


STRATEGY_LABELS = {
    'sets': '3 bo thong ke (30k)',
    'one': '1 ve (10k)',
    'antishare': '1 ve anti-share (10k)',
    'wheel': 'Wheel 8 so (40k)',
    'wheel12': 'Wheel 12 so (80k)',
    'none': 'Khong mua - chi theo doi',
}


def normalize_strategies(strategy):
    """Chap nhan 1 chuoi hoac list -> luon tra ve list."""
    if isinstance(strategy, str):
        return [strategy]
    return list(strategy or ['sets'])


def _one_strategy_tickets(pred, strategy):
    if strategy == 'none':
        return []
    if strategy == 'sets':
        return [s['matched'] for s in pred.get('sets', []) if 'matched' in s]
    if strategy == 'one':
        sets = [s for s in pred.get('sets', []) if 'matched' in s]
        return [sets[0]['matched']] if sets else []
    if strategy == 'antishare':
        a = pred.get('antishare')
        return [a['matched']] if a and 'matched' in a else []
    if strategy in ('wheel', 'wheel12'):
        w = pred.get(strategy)
        return list(w['matched']) if w and 'matched' in w else []
    return []


def _tickets_of(pred, strategies):
    """Gop ve cua nhieu chien luoc (vd 3 bo + 1 ve anti-share = 4 ve)."""
    out = []
    for s in normalize_strategies(strategies):
        out.extend(_one_strategy_tickets(pred, s))
    return out


def compute(predictions, cfg=None):
    """Tinh chi/thu thuc te theo chien luoc + ngan sach da khai bao."""
    cfg = cfg or load_config()
    strategy = cfg.get('strategy', 'sets')
    games = set(cfg.get('games') or ['645', '655'])
    limit_k = float(cfg.get('monthly_limit_k') or 0)

    by_month = defaultdict(lambda: {'cost_k': 0, 'prize_k': 0, 'draws': 0, 'wins': 0})
    total = {'cost_k': 0, 'prize_k': 0, 'draws': 0, 'tickets': 0, 'wins': 0}

    for p in predictions:
        if not p.get('actual') or p['game'] not in games:
            continue
        matched = _tickets_of(p, strategy)
        if not matched:
            continue
        # thang tu predicted_at "dd/mm/yyyy HH:MM"
        try:
            d, m, y = p['predicted_at'].split()[0].split('/')
            month = f'{y}-{m}'
        except (KeyError, ValueError):
            month = '?'

        cost_k = len(matched) * TICKET_PRICE_K
        prize_k = 0
        wins = 0
        table = PRIZE_K[p['game']]
        for mt in matched:
            val = table.get(mt)
            if val:
                prize_k += val
                wins += 1

        by_month[month]['cost_k'] += cost_k
        by_month[month]['prize_k'] += prize_k
        by_month[month]['draws'] += 1
        by_month[month]['wins'] += wins
        total['cost_k'] += cost_k
        total['prize_k'] += prize_k
        total['draws'] += 1
        total['tickets'] += len(matched)
        total['wins'] += wins

    months = []
    for month in sorted(by_month, reverse=True):
        v = by_month[month]
        pct = (v['cost_k'] / limit_k * 100) if limit_k else 0
        months.append({
            'month': month,
            'cost_k': v['cost_k'],
            'prize_k': v['prize_k'],
            'net_k': v['prize_k'] - v['cost_k'],
            'draws': v['draws'],
            'wins': v['wins'],
            'limit_pct': round(pct, 1),
            'over': limit_k > 0 and v['cost_k'] > limit_k,
        })

    total['net_k'] = total['prize_k'] - total['cost_k']
    total['roi_pct'] = round((total['prize_k'] / total['cost_k'] - 1) * 100, 1) if total['cost_k'] else 0
    # Du bao 1 nam theo nhip hien tai
    total['yearly_k'] = round(total['cost_k'] / max(len(months), 1) * 12) if months else 0

    return {
        'config': cfg,
        'total': total,
        'months': months,
        'strategy_label': ' + '.join(
            STRATEGY_LABELS.get(s, s) for s in normalize_strategies(strategy)
        ),
    }


if __name__ == '__main__':
    import sys
    if sys.platform == 'win32':
        sys.stdout.reconfigure(encoding='utf-8')
    if not os.path.exists(BUDGET_FILE):
        save_config(DEFAULTS)
        print(f'Da tao {BUDGET_FILE} voi mac dinh: {DEFAULTS}')
    with open(os.path.join(BASE_DIR, 'data', 'predictions.json'), encoding='utf-8') as f:
        preds = json.load(f)
    r = compute(preds)
    t = r['total']
    print(f"Chien luoc: {r['strategy_label']} | Game: {', '.join(r['config']['games'])}")
    print(f"Tran thang: {r['config']['monthly_limit_k']}k")
    print(f"Da theo doi {t['draws']} ky, {t['tickets']} ve")
    print(f"Chi: {t['cost_k']}k | Thu: {t['prize_k']}k | Net: {t['net_k']:+}k (ROI {t['roi_pct']:+}%)")
    print(f"Nhip nay 1 nam: ~{t['yearly_k']:,}k")
    for m in r['months']:
        flag = ' [VUOT TRAN]' if m['over'] else ''
        print(f"  {m['month']}: chi {m['cost_k']}k ({m['limit_pct']}% tran), thu {m['prize_k']}k, net {m['net_k']:+}k{flag}")
