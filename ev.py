"""
EV Calculator - "Jackpot bao nhieu thi dang choi?"

Nguyen ly: xac suat trung KHONG doi duoc, nhung ky vong TIEN (EV) moi ve
thay doi theo jackpot. EV = tong (xac suat giai x tien giai sau thue/chia).
Jackpot cang cao -> EV cang gan gia ve -> "do lo" cang it.

Cong thuc:
  - Xac suat tinh chinh xac bang to hop (khong xap xi).
  - Thue TNCN 10% phan vuot 10 trieu (ap dung moi giai > 10tr).
  - Chia jackpot: so nguoi cung trung ~ Poisson(lambda), lambda = ve_ban / so_to_hop.
    Ky vong phan nhan duoc cua nguoi trung = (1 - e^-lambda) / lambda.
  - Ve ban moi ky uoc tu du lieu THAT: so nguoi trung Giai 3 / P(Giai 3)
    (median cac ky gan nhat trong data/winners_*.csv).

KET LUAN QUAN TRONG: voi co cau giai VN, EV gan nhu KHONG BAO GIO vuot gia ve
(jackpot hoa von ~66 ty cho 6/45 truoc chia giai, cao hon nua sau chia).
Module nay cho biet hom nay "lo it hay lo nhieu" - khong phai "choi la lai".
"""
import csv
import math
import os
import re
import sys
from statistics import median

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'data')

TICKET_PRICE = 10_000
TAX_FREE = 10_000_000
TAX_RATE = 0.10


def _comb(n, k):
    return math.comb(n, k)


# Co cau giai (gia tri GOC truoc thue). None = jackpot (bien doi).
# moi item: (ten, so_cach_trung, tien_giai)  -> P = so_cach_trung / C(N,6)
GAME_SPEC = {
    '645': {
        'name': 'Mega 6/45',
        'combos': _comb(45, 6),                       # 8,145,060
        'fixed': [
            ('Giai 3 (3/6)', _comb(6, 3) * _comb(39, 3), 30_000),
            ('Giai 2 (4/6)', _comb(6, 4) * _comb(39, 2), 300_000),
            ('Giai 1 (5/6)', _comb(6, 5) * _comb(39, 1), 10_000_000),
        ],
        'jackpots': [('Jackpot (6/6)', 1)],
        'g3_ways': _comb(6, 3) * _comb(39, 3),
    },
    '655': {
        'name': 'Power 6/55',
        'combos': _comb(55, 6),                       # 28,989,675
        'fixed': [
            ('Giai 3 (3/6)', _comb(6, 3) * _comb(49, 3), 50_000),
            ('Giai 2 (4/6)', _comb(6, 4) * _comb(49, 2), 500_000),
            ('Giai 1 (5/6, truot power)', _comb(6, 5) * 48, 40_000_000),
        ],
        # JP2 = trung 5 so + so con lai la Power: 6 cach
        'jackpots': [('Jackpot 1 (6/6)', 1), ('Jackpot 2 (5/6 + Power)', 6)],
        'g3_ways': _comb(6, 3) * _comb(49, 3),
    },
}

# Fallback neu khong co winners CSV (uoc luong than trong, ve/ky)
DEFAULT_TICKETS = {'645': 1_200_000, '655': 1_300_000}


def after_tax(amount):
    """Thue TNCN 10% phan vuot 10 trieu."""
    if amount <= TAX_FREE:
        return amount
    return TAX_FREE + (amount - TAX_FREE) * (1 - TAX_RATE)


def estimate_tickets_sold(game, last_n=30):
    """Uoc so ve ban moi ky tu so nguoi trung Giai 3 (du lieu that)."""
    spec = GAME_SPEC[game]
    path = os.path.join(DATA_DIR, f'winners_{game}.csv')
    if not os.path.exists(path):
        return DEFAULT_TICKETS[game], 'mac dinh (chua co winners CSV)'
    rows = []
    try:
        with open(path, encoding='utf-8') as f:
            for row in csv.DictReader(f):
                g3 = int(row.get('g3_w') or 0)
                if g3 > 0:
                    rows.append((row['draw_id'], g3))
    except (OSError, ValueError, KeyError):
        return DEFAULT_TICKETS[game], 'mac dinh (loi doc winners CSV)'
    if not rows:
        return DEFAULT_TICKETS[game], 'mac dinh (winners CSV rong)'
    rows.sort(key=lambda r: r[0])
    recent = [g3 for _, g3 in rows[-last_n:]]
    p_g3 = spec['g3_ways'] / spec['combos']
    est = int(median(recent) / p_g3)
    return est, f'tu G3 winners ({len(recent)} ky gan nhat cua CSV)'


def share_factor(tickets_sold, combos):
    """Ky vong PHAN jackpot nhan duoc khi minh trung (nguoi khac cung trung ~ Poisson)."""
    lam = tickets_sold / combos
    if lam <= 0:
        return 1.0
    return (1 - math.exp(-lam)) / lam


def compute_ev(game, jackpot_values, tickets_sold=None):
    """
    EV 1 ve (VND) tai jackpot cho truoc.
    jackpot_values: list tien jackpot GOC theo thu tu GAME_SPEC[game]['jackpots'].
    """
    spec = GAME_SPEC[game]
    combos = spec['combos']
    if tickets_sold is None:
        tickets_sold, _ = estimate_tickets_sold(game)

    parts = []
    ev_fixed = 0.0
    for name, ways, prize in spec['fixed']:
        p = ways / combos
        ev = p * after_tax(prize)
        ev_fixed += ev
        parts.append({'name': name, 'p': p, 'odds': round(combos / ways), 'ev': ev})

    sf = share_factor(tickets_sold, combos)
    ev_jp = 0.0
    for (name, ways), jp in zip(spec['jackpots'], jackpot_values):
        p = ways / combos
        ev = p * after_tax(jp or 0) * sf
        ev_jp += ev
        parts.append({'name': name, 'p': p, 'odds': round(combos / ways),
                      'ev': ev, 'jackpot': jp})

    total = ev_fixed + ev_jp
    return {
        'game': game,
        'game_name': spec['name'],
        'tickets_sold_est': tickets_sold,
        'share_factor': sf,
        'ev_fixed': ev_fixed,
        'ev_jackpot': ev_jp,
        'ev_total': total,
        'loss_pct': (1 - total / TICKET_PRICE) * 100,
        'parts': parts,
    }


def break_even_jackpot(game, tickets_sold=None):
    """Jackpot 1 can bao nhieu de EV = gia ve (giai su JP2 cua 655 = 3 ty san)."""
    spec = GAME_SPEC[game]
    combos = spec['combos']
    if tickets_sold is None:
        tickets_sold, _ = estimate_tickets_sold(game)
    sf = share_factor(tickets_sold, combos)
    ev_fixed = sum(ways / combos * after_tax(prize) for _, ways, prize in spec['fixed'])
    base_jp2 = 0.0
    if game == '655':
        base_jp2 = 6 / combos * after_tax(3_000_000_000) * sf
    need = TICKET_PRICE - ev_fixed - base_jp2
    p_jp1 = 1 / combos
    # after_tax nguoc: net = 10tr + 0.9*(gross-10tr) -> gross = (net-1tr)/0.9
    net_needed = need / (p_jp1 * sf)
    gross = (net_needed - TAX_FREE * TAX_RATE) / (1 - TAX_RATE)
    return gross


def fetch_jackpots():
    """
    Crawl gia tri jackpot hien tai tu trang ket qua vietlott.vn.
    Tra ve {'645': [jp], '655': [jp1, jp2]} - game loi thi bo qua (khong raise).
    """
    import crawler  # dung chung session/impersonate voi crawler
    out = {}
    urls = {
        '645': 'https://vietlott.vn/vi/trung-thuong/ket-qua-trung-thuong/645',
        '655': 'https://vietlott.vn/vi/trung-thuong/ket-qua-trung-thuong/655',
    }
    for game, url in urls.items():
        try:
            r = None
            for attempt in range(3):  # vietlott.vn hay timeout chap chon
                try:
                    r = crawler.requests.get(
                        url, headers={'User-Agent': crawler.HEADERS['User-Agent']},
                        timeout=20, **crawler.IMPERSONATE)
                    break
                except Exception:
                    if attempt == 2:
                        raise
            r.raise_for_status()
            text = re.sub(r'<[^>]+>', ' ', r.text)
            # "Gia tri Jackpot 28.975.123.500 VND" / "Gia tri Jackpot 1 ... Jackpot 2 ..."
            vals = re.findall(
                r'Giá trị Jackpot(?:\s*\d)?\s+([\d.]{7,})\s*VN',
                text)
            jps = [int(v.replace('.', '')) for v in vals]
            expected = len(GAME_SPEC[game]['jackpots'])
            if len(jps) >= expected:
                out[game] = jps[:expected]
        except Exception:
            continue
    return out


def fmt_b(vnd):
    """Format ty dong."""
    return f'{vnd / 1e9:.2f} ty'


def print_report():
    jps = fetch_jackpots()
    if not jps:
        print('Khong lay duoc jackpot hien tai (mang/chan). Thu lai sau.')
        return
    for game, jackpots in jps.items():
        tickets, src = estimate_tickets_sold(game)
        r = compute_ev(game, jackpots, tickets)
        be = break_even_jackpot(game, tickets)
        print(f"\n=== {r['game_name']} ===")
        for (name, _), jp in zip(GAME_SPEC[game]['jackpots'], jackpots):
            print(f'  {name}: {fmt_b(jp)}')
        print(f'  Ve ban/ky uoc tinh: {tickets:,} ({src})')
        print(f'  EV moi ve 10k: {r["ev_total"]:,.0f} d '
              f'(giai co dinh {r["ev_fixed"]:,.0f} + jackpot {r["ev_jackpot"]:,.0f})')
        print(f'  => Ky vong LO {r["loss_pct"]:.1f}% moi ve')
        print(f'  Jackpot 1 hoa von (EV = gia ve): {fmt_b(be)}')
        pct = jackpots[0] / be * 100
        print(f'  Jackpot hien tai = {pct:.0f}% muc hoa von')


if __name__ == '__main__':
    if sys.platform == 'win32':
        sys.stdout.reconfigure(encoding='utf-8')
    print_report()
