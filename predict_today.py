import sys, numpy as np
sys.stdout.reconfigure(encoding='utf-8')
from crawler import load_data, get_render_info, fetch_draw
from analyzer import hot_cold_analysis, gap_analysis, sum_analysis, frequency_analysis, pair_analysis
from predictor import strategy_balanced, strategy_hot, strategy_cold, strategy_frequency, strategy_pattern

data = load_data('655')
hc = hot_cold_analysis(data, recent_n=30)
gaps = gap_analysis(data, 55)
ss = sum_analysis(data)
pairs = pair_analysis(data, last_n=50)

hot_set = set(r['number'] for r in hc['hot'][:12])
overdue_set = set(r['number'] for r in gaps['overdue'][:12])

# Power analysis
pw_counter = {}
pw_last_seen = {}
for i, e in enumerate(data):
    if 'power' in e:
        pw_counter[e['power']] = pw_counter.get(e['power'], 0) + 1
        pw_last_seen[e['power']] = i
pw_recent = [e['power'] for e in data[-15:] if 'power' in e]

print()
print("=" * 62)
print("   POWER 6/55 - DU DOAN KY #01327 (02/04/2026)")
print(f"   Phan tich tu {len(data):,} ky lich su")
print("=" * 62)

print("\n  15 KY GAN NHAT:")
print("  " + "-" * 56)
for e in data[-15:]:
    nums = ' '.join(f'{n:02d}' for n in e['numbers'])
    pw = f'{e["power"]:02d}' if 'power' in e else '--'
    s = sum(e['numbers'])
    odd = sum(1 for n in e['numbers'] if n % 2 == 1)
    print(f'  #{e["draw_id"]} {e["date"]}: {nums} |{pw}  T={s:3d} {odd}L/{6-odd}C')

print("\n  SO NONG (30 ky gan):")
for r in hc['hot'][:10]:
    bar = '#' * r['recent_count']
    print(f'    {r["number"]:02d}: {r["recent_count"]:2d} lan ({r["recent_pct"]:5.1f}% vs TB {r["overall_pct"]:4.1f}%)  {bar}')

print("\n  SO QUA HAN:")
for r in gaps['overdue'][:10]:
    bar = '.' * min(r['gap'], 25)
    print(f'    {r["number"]:02d}: {r["gap"]:3d} ky  {bar}')

print("\n  CAP SO HAY DI CUNG (50 ky gan):")
for p in pairs['top_pairs'][:8]:
    print(f'    ({p["pair"][0]:02d}, {p["pair"][1]:02d}): {p["count"]} lan')

print(f'\n  TONG: TB={ss["mean"]} | Q25-Q75: {ss["q25"]}-{ss["q75"]}')
print(f'  Le/Chan: 3L-3C(33%) > 2L-4C(25%) > 4L-2C(24%)')

print(f'\n  SO POWER 15 ky gan: {" ".join(f"{p:02d}" for p in pw_recent)}')
pw_top = sorted(pw_counter.items(), key=lambda x: -x[1])[:8]
print(f'  Power pho bien: {" ".join(f"{n:02d}({c})" for n,c in pw_top)}')

# PREDICTIONS
print("\n" + "=" * 62)
print("              >>> DU DOAN KY #01327 <<<")
print("=" * 62)

strategies = [
    ('balanced', strategy_balanced),
    ('hot', strategy_hot),
    ('cold', strategy_cold),
    ('frequency', strategy_frequency),
    ('pattern', strategy_pattern),
]

all_preds = []
for name, func in strategies:
    for _ in range(30):
        nums = func(data, 55)
        s = sum(nums)
        odd = sum(1 for n in nums if n % 2 == 1)
        hot_count = len(set(nums) & hot_set)
        overdue_count = len(set(nums) & overdue_set)

        score = 0
        if ss['q25'] <= s <= ss['q75']:
            score += 4
        if odd in (2, 3, 4):
            score += 3
        score += hot_count * 1.5
        score += overdue_count * 1.5
        zones = [0, 0, 0]
        for n in nums:
            if n <= 18: zones[0] += 1
            elif n <= 37: zones[1] += 1
            else: zones[2] += 1
        if min(zones) >= 1:
            score += 2

        all_preds.append((name, nums, s, odd, score, hot_count, overdue_count))

all_preds.sort(key=lambda x: -x[4])

seen = set()
unique = []
for p in all_preds:
    key = tuple(p[1])
    if key not in seen:
        seen.add(key)
        unique.append(p)
    if len(unique) >= 8:
        break

print()
for i, (name, nums, s, odd, score, hc_cnt, ov_cnt) in enumerate(unique[:8]):
    nums_str = '  '.join(f'{n:02d}' for n in nums)
    if i == 0:
        star = '***'
    elif i <= 2:
        star = '** '
    else:
        star = '*  '
    tags = []
    if hc_cnt > 0:
        tags.append(f'{hc_cnt} nong')
    if ov_cnt > 0:
        tags.append(f'{ov_cnt} qua han')
    tag_str = f'  [{" + ".join(tags)}]' if tags else ''
    print(f'  {star} Bo {i+1}: {nums_str}   T={s:3d} {odd}L/{6-odd}C{tag_str}')

# Power suggestions
pw_scores = {}
for n in range(1, 56):
    freq_score = pw_counter.get(n, 0) / max(len(data), 1)
    gap = len(data) - 1 - pw_last_seen.get(n, -1)
    gap_score = gap / 30
    pw_scores[n] = freq_score + gap_score * 0.5
top_pw = sorted(pw_scores.items(), key=lambda x: -x[1])[:5]
print(f'\n  So Power goi y: {", ".join(f"{n:02d}" for n, _ in top_pw)}')

print("\n" + "=" * 62)
print("  N = so nong | Q = so qua han")
print("  T = tong 6 so | L = le | C = chan")
print()
print("  Quay so: 18h00 - TodayTV / SCTV2")
print("  XO SO LA NGAU NHIEN - day chi la GOI Y thong ke!")
print("=" * 62)
