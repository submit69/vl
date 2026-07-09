"""
Smart predictor - Phan tich da tang thoi gian
Ket hop:
- Tan suat dai han (toan bo lich su)
- Xu huong trung han (100 ky gan)
- Hot/cold ngan han (30 ky gan)
- Phan tich gap, cap so, position, sum, odd/even
- Markov transition (so xuat hien sau so nao)
"""
import sys, numpy as np, math
from collections import Counter, defaultdict
sys.stdout.reconfigure(encoding='utf-8')

from crawler import load_data
from analyzer import frequency_analysis, hot_cold_analysis, gap_analysis, sum_analysis


def comprehensive_score(data, max_num):
    """Score each number using multiple time horizons + multiple factors"""
    n_total = len(data)

    # Multi-tier frequency analysis
    full_freq = Counter()       # all history
    recent_100 = Counter()      # last 100
    recent_30 = Counter()       # last 30
    recent_10 = Counter()       # last 10

    for entry in data:
        for n in entry['numbers']:
            full_freq[n] += 1
    for entry in data[-100:]:
        for n in entry['numbers']:
            recent_100[n] += 1
    for entry in data[-30:]:
        for n in entry['numbers']:
            recent_30[n] += 1
    for entry in data[-10:]:
        for n in entry['numbers']:
            recent_10[n] += 1

    # Gap analysis
    last_seen = {}
    for i, entry in enumerate(data):
        for n in entry['numbers']:
            last_seen[n] = i
    gaps = {n: n_total - 1 - last_seen.get(n, -1) for n in range(1, max_num + 1)}

    # Average gap (theoretical: max_num/6 = 55/6 = 9.17 for 655)
    expected_gap = max_num / 6

    scores = {}
    for n in range(1, max_num + 1):
        # Normalize each metric to 0-1
        full_pct = full_freq.get(n, 0) / n_total          # ~6/55 = 10.9%
        r100_pct = recent_100.get(n, 0) / 100             # boost if hot in 100
        r30_pct = recent_30.get(n, 0) / 30                # boost if hot in 30
        r10_pct = recent_10.get(n, 0) / 10                # boost if just-hot
        gap = gaps[n]

        # Weighted sum
        # Long-term frequency provides BASE expectation
        # Recent layers detect TREND (continuing or reversing)
        # Gap measures OVERDUE-ness vs expected
        score = (
            full_pct * 100 * 4.0 +     # base: long-term mean
            r100_pct * 100 * 2.0 +     # 100-draw trend
            r30_pct * 100 * 2.5 +      # 30-draw trend
            r10_pct * 100 * 1.5 +      # very recent
            min(gap / expected_gap, 3.0) * 8  # overdue (capped at 3x expected)
        )
        scores[n] = score

    return scores, full_freq, recent_30, gaps


def pair_strength(data, last_n=200):
    """Find pairs that often appear together (using larger window)"""
    pair_count = Counter()
    for entry in data[-last_n:]:
        nums = sorted(entry['numbers'])
        for i in range(len(nums)):
            for j in range(i+1, len(nums)):
                pair_count[(nums[i], nums[j])] += 1
    return pair_count


def position_analysis(data, max_num):
    """Numbers tend to appear in certain positions when sorted"""
    # When sorted, position 1 (smallest) tends to be small numbers
    pos_freq = [Counter() for _ in range(6)]
    for entry in data:
        nums = sorted(entry['numbers'])
        for i, n in enumerate(nums):
            pos_freq[i][n] += 1
    return pos_freq


def smart_predict(game='655', n_sets=3):
    data = load_data(game)
    max_num = 45 if game == '645' else 55
    n_total = len(data)

    # Get comprehensive scores
    scores, full_freq, recent_30, gaps = comprehensive_score(data, max_num)
    pairs = pair_strength(data, last_n=200)

    # Sum statistics from FULL history
    sums = [sum(e['numbers']) for e in data]
    sum_mean = np.mean(sums)
    sum_std = np.std(sums)
    sum_q25 = np.percentile(sums, 25)
    sum_q75 = np.percentile(sums, 75)

    # Odd/even distribution from FULL history
    oe_dist = Counter()
    for e in data:
        odd = sum(1 for n in e['numbers'] if n % 2 == 1)
        oe_dist[(odd, 6-odd)] += 1
    most_common_oe = oe_dist.most_common(3)
    target_oe = [oe for oe, c in most_common_oe]

    # Top by score
    sorted_nums = sorted(scores.keys(), key=lambda n: -scores[n])
    top12 = sorted_nums[:12]
    top18 = sorted_nums[:18]

    print('=' * 60)
    print(f'  PHAN TICH TONG HOP - {game.upper()}')
    first_date = data[0]['date']
    print(f'  Tu {n_total:,} ky lich su (tu {first_date})')
    print('=' * 60)

    print('\n  TOP 15 SO MANH NHAT (da tang thoi gian + gap):')
    for i, n in enumerate(sorted_nums[:15]):
        full_pct = full_freq.get(n, 0) / n_total * 100
        r30 = recent_30.get(n, 0)
        gap = gaps[n]
        print(f'    {i+1:2d}. So {n:02d}: TS={full_freq.get(n,0)} ({full_pct:.1f}%) | 30ky={r30} | gap={gap} | score={scores[n]:.1f}')

    # Sum stats
    print(f'\n  TONG (toan lich su):')
    print(f'    TB={sum_mean:.1f} | Std={sum_std:.1f}')
    print(f'    Khoang Q25-Q75: {sum_q25:.0f}-{sum_q75:.0f}')

    # Odd/even
    print(f'\n  PHAN BO LE/CHAN pho bien nhat:')
    for (odd, even), c in most_common_oe:
        print(f'    {odd}L/{even}C: {c}/{n_total} ({c/n_total*100:.1f}%)')

    # Top pairs
    print(f'\n  CAP SO MANH NHAT (200 ky gan):')
    for (a, b), c in pairs.most_common(8):
        print(f'    ({a:02d}, {b:02d}): {c} lan')

    # Generate predictions using comprehensive scoring
    best_combo = None
    best_score = -1

    # Get pair bonus map
    pair_map = defaultdict(int)
    for (a, b), c in pairs.most_common(50):
        pair_map[(a, b)] = c
        pair_map[(b, a)] = c

    for trial in range(8000):
        sets = []
        for i in range(n_sets):
            s = set()
            # 4 from top12
            pool_top = list(top12)
            np.random.shuffle(pool_top)
            for n in pool_top[:4]: s.add(n)
            # 2 from top13-25
            extra_pool = sorted_nums[12:25]
            np.random.shuffle(extra_pool)
            for n in extra_pool:
                if len(s) >= 6: break
                s.add(n)
            sets.append(sorted(s))

        # Validate
        valid = True
        for s in sets:
            sm = sum(s)
            odd = sum(1 for n in s if n % 2 == 1)
            even = 6 - odd
            if not (sum_q25 <= sm <= sum_q75): valid = False
            if (odd, even) not in target_oe: valid = False
        if not valid: continue

        # Each set must have >= 4 from top12
        if min(sum(1 for n in s if n in top12) for s in sets) < 4: continue

        # Sets must be different (no two with 5+ overlap)
        all_diff = True
        for i in range(len(sets)):
            for j in range(i+1, len(sets)):
                if len(set(sets[i]) & set(sets[j])) >= 5:
                    all_diff = False
                    break
        if not all_diff: continue

        # Score: coverage of top12 + sum of pair bonuses + score sum
        union = set()
        for s in sets: union.update(s)
        coverage = sum(1 for n in top12 if n in union)
        diversity = len(union)

        pair_bonus = 0
        for s in sets:
            ns = sorted(s)
            for ii in range(len(ns)):
                for jj in range(ii+1, len(ns)):
                    pair_bonus += pair_map.get((ns[ii], ns[jj]), 0)

        score_total = sum(scores[n] for s in sets for n in s)

        total_score = coverage * 20 + diversity * 3 + pair_bonus * 0.5 + score_total * 0.05

        if total_score > best_score:
            best_score = total_score
            best_combo = sets

    # Power suggestion (for 655)
    pw_score = {}
    if game == '655':
        pw_full = Counter()
        pw_last = {}
        for i, e in enumerate(data):
            if 'power' in e:
                pw_full[e['power']] += 1
                pw_last[e['power']] = i
        for n in range(1, max_num + 1):
            pw_score[n] = (
                pw_full.get(n, 0) / n_total * 100 * 4 +
                ((n_total - 1 - pw_last.get(n, -1)) / 30) * 8
            )

    total = math.comb(max_num, 6)
    p_any = sum(math.comb(6,k)*math.comb(max_num-6,6-k) for k in range(3,7)) / total * 100
    p_n = (1 - (1-p_any/100)**n_sets) * 100

    print('\n' + '=' * 60)
    print(f'  {n_sets} BO TOI UU (DUNG TOAN BO LICH SU)')
    print('=' * 60)

    union = set()
    counter = Counter()
    for i, s in enumerate(best_combo):
        nums_str = '  '.join(f'{n:02d}' for n in s)
        sm = sum(s)
        odd = sum(1 for n in s if n % 2 == 1)
        top_in = sum(1 for n in s if n in top12)
        avg_score = sum(scores[n] for n in s) / 6

        if game == '655':
            sorted_pw = sorted(pw_score.items(), key=lambda x: -x[1])
            pw = sorted_pw[i][0]
            print(f'\n  Bo {i+1}: {nums_str} | {pw:02d}')
        else:
            print(f'\n  Bo {i+1}: {nums_str}')
        print(f'        Tong={sm} | {odd}L/{6-odd}C | {top_in}/6 trong TOP 12 | avg_score={avg_score:.1f}')
        union.update(s)
        for n in s: counter[n] += 1

    multi = [(n, c) for n, c in counter.items() if c >= 2]
    multi.sort(key=lambda x: -x[1])
    print(f'\n  Tong phu {len(union)} so: {sorted(union)}')
    multi_str = ', '.join(f'{n:02d}x{c}' for n, c in multi[:8])
    print(f'  So tin nhat (xuat hien nhieu bo): {multi_str}')

    if game == '655':
        sorted_pw = sorted(pw_score.items(), key=lambda x: -x[1])[:5]
        pw_str = ', '.join(f'{n:02d}' for n, _ in sorted_pw)
        print(f'  Power TOP 5: {pw_str}')

    print(f'\n  XS trung Giai 3+ ({n_sets} ve): ~{p_n:.2f}%')
    print('  XO SO LA NGAU NHIEN - day la PHAN TICH TOI UU NHAT')
    print('=' * 60)


if __name__ == '__main__':
    game = sys.argv[1] if len(sys.argv) > 1 else '655'
    n_sets = int(sys.argv[2]) if len(sys.argv) > 2 else 3
    smart_predict(game, n_sets)
