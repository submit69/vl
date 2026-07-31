"""
Kiem chung thuc nghiem model Anti-Share bang so lieu nguoi trung THAT.

Gia thuyet: ky nao ket qua chua nhieu so "pho bien" (theo model popularity)
-> nhieu nguoi chon trung so do -> so nguoi trung Giai 2/3 cao hon.

Phuong phap:
- mean_pop = trung binh popularity cua 6 so ket qua moi ky
- winners_norm = so nguoi trung / median truot 50 ky (loai bo anh huong
  doanh so ve thay doi theo thoi gian/jackpot lon)
- Tinh tuong quan Spearman + so sanh quartile pho bien nhat vs it pho bien nhat
"""
import sys
import csv
import os
import numpy as np

from antishare import popularity
from crawler import load_data

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')


def rolling_median(values, window=50):
    out = []
    for i in range(len(values)):
        lo = max(0, i - window // 2)
        hi = min(len(values), i + window // 2)
        out.append(np.median(values[lo:hi]))
    return np.array(out)


def spearman(x, y):
    """Spearman rank correlation (khong can scipy)."""
    x, y = np.asarray(x, dtype=float), np.asarray(y, dtype=float)
    rx = np.argsort(np.argsort(x)).astype(float)
    ry = np.argsort(np.argsort(y)).astype(float)
    rx = (rx - rx.mean()) / (rx.std() or 1)
    ry = (ry - ry.mean()) / (ry.std() or 1)
    return float((rx * ry).mean())


def analyze(game):
    # Load winner counts
    path = os.path.join(DATA_DIR, f'winners_{game}.csv')
    if not os.path.exists(path):
        print(f'[{game}] Chua co winners CSV - chay winners.py truoc')
        return None
    winners = {}
    with open(path, 'r', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            try:
                winners[row['draw_id']] = {
                    'g2': int(row['g2_w']),
                    'g3': int(row['g3_w']),
                }
            except (ValueError, KeyError):
                continue

    # Join voi ket qua
    data = load_data(game)
    rows = []
    for e in data:
        w = winners.get(e['draw_id'])
        if not w:
            continue
        mean_pop = float(np.mean([popularity(n) for n in e['numbers']]))
        rows.append({
            'draw_id': e['draw_id'],
            'mean_pop': mean_pop,
            'g2': w['g2'],
            'g3': w['g3'],
            'numbers': e['numbers'],
        })

    if len(rows) < 50:
        print(f'[{game}] Chi co {len(rows)} ky co du lieu - can them')
        return None

    rows.sort(key=lambda r: r['draw_id'])
    n = len(rows)
    print(f'=== {("Mega 6/45" if game == "645" else "Power 6/55")} - {n} ky co winner data ===')

    # Normalize theo rolling median (loai trend doanh so)
    for tier in ('g2', 'g3'):
        vals = np.array([r[tier] for r in rows], dtype=float)
        med = rolling_median(vals, 50)
        med[med == 0] = 1
        norm = vals / med
        pops = np.array([r['mean_pop'] for r in rows])

        rho = spearman(pops, norm)

        # Quartile comparison
        idx = np.argsort(pops)
        q_low = norm[idx[:n // 4]]     # 25% ky co so IT pho bien nhat
        q_high = norm[idx[-n // 4:]]   # 25% ky co so PHO BIEN nhat
        lift = (q_high.mean() / q_low.mean() - 1) * 100

        tier_name = 'Giai Nhi (4/6)' if tier == 'g2' else 'Giai Ba (3/6)'
        print(f'  {tier_name}:')
        print(f'    Spearman(mean_pop, winners_norm) = {rho:+.3f}')
        print(f'    Ky nhieu so pho bien co trung binh {lift:+.1f}% nguoi trung so voi ky it so pho bien')

    # Vi du minh hoa: 3 ky pop cao nhat vs 3 ky thap nhat
    rows_sorted = sorted(rows, key=lambda r: r['mean_pop'])
    print('  Vi du:')
    for r in rows_sorted[:3]:
        nums = ' '.join(f'{x:02d}' for x in r['numbers'])
        print(f'    [pop thap {r["mean_pop"]:.2f}] #{r["draw_id"]} {nums}: G3={r["g3"]:,} nguoi')
    for r in rows_sorted[-3:]:
        nums = ' '.join(f'{x:02d}' for x in r['numbers'])
        print(f'    [pop CAO  {r["mean_pop"]:.2f}] #{r["draw_id"]} {nums}: G3={r["g3"]:,} nguoi')
    print()
    return rows


def analyze_by_era(game, n_eras=3):
    """Chia lich su thanh cac thoi ky -> hanh vi nguoi choi co doi khong?"""
    path = os.path.join(DATA_DIR, f'winners_{game}.csv')
    if not os.path.exists(path):
        return
    winners = {}
    with open(path, 'r', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            try:
                winners[row['draw_id']] = int(row['g3_w'])
            except (ValueError, KeyError):
                continue

    data = load_data(game)
    rows = []
    for e in data:
        g3 = winners.get(e['draw_id'])
        if g3 is None:
            continue
        rows.append((int(e['draw_id']), float(np.mean([popularity(n) for n in e['numbers']])), g3, e['date']))
    rows.sort()
    if len(rows) < n_eras * 60:
        print(f'[{game}] Chua du data cho phan tich thoi ky ({len(rows)} ky)')
        return

    print(f'=== {("Mega 6/45" if game == "645" else "Power 6/55")} - PHAN TICH THEO THOI KY ({len(rows)} ky) ===')
    chunk = len(rows) // n_eras
    for i in range(n_eras):
        part = rows[i * chunk: (i + 1) * chunk if i < n_eras - 1 else len(rows)]
        pops = np.array([r[1] for r in part])
        g3s = np.array([r[2] for r in part], dtype=float)
        med = rolling_median(g3s, 50)
        med[med == 0] = 1
        norm = g3s / med
        rho = spearman(pops, norm)
        idx = np.argsort(pops)
        q = len(part) // 4
        lift = (norm[idx[-q:]].mean() / norm[idx[:q]].mean() - 1) * 100
        print(f'  {part[0][3]} -> {part[-1][3]} ({len(part)} ky): Spearman={rho:+.3f}, lift={lift:+.1f}%')
    print()


if __name__ == '__main__':
    if sys.platform == 'win32':
        sys.stdout.reconfigure(encoding='utf-8')
    for g in ('645', '655'):
        analyze(g)
    for g in ('645', '655'):
        analyze_by_era(g)
