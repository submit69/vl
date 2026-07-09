"""
Core prediction logic - returns data (no printing).
Used by app.py dashboard and CLI tools.
"""
import numpy as np
import math
from collections import Counter, defaultdict
from crawler import load_data


def comprehensive_score(data, max_num):
    """Score each number using multiple time horizons + gap analysis."""
    n_total = len(data)

    full_freq = Counter()
    recent_100 = Counter()
    recent_30 = Counter()
    recent_10 = Counter()

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

    last_seen = {}
    for i, entry in enumerate(data):
        for n in entry['numbers']:
            last_seen[n] = i
    gaps = {n: n_total - 1 - last_seen.get(n, -1) for n in range(1, max_num + 1)}

    expected_gap = max_num / 6

    scores = {}
    for n in range(1, max_num + 1):
        full_pct = full_freq.get(n, 0) / n_total
        r100_pct = recent_100.get(n, 0) / 100
        r30_pct = recent_30.get(n, 0) / 30
        r10_pct = recent_10.get(n, 0) / 10
        gap = gaps[n]

        score = (
            full_pct * 100 * 4.0 +
            r100_pct * 100 * 2.0 +
            r30_pct * 100 * 2.5 +
            r10_pct * 100 * 1.5 +
            min(gap / expected_gap, 3.0) * 8
        )
        scores[n] = score

    return scores, full_freq, recent_30, gaps


def pair_strength(data, last_n=200):
    pair_count = Counter()
    for entry in data[-last_n:]:
        nums = sorted(entry['numbers'])
        for i in range(len(nums)):
            for j in range(i + 1, len(nums)):
                pair_count[(nums[i], nums[j])] += 1
    return pair_count


def generate_predictions(game='655', n_sets=3, n_trials=8000):
    """Generate top prediction sets. Returns dict with all analysis data."""
    data = load_data(game)
    if not data:
        return {'error': 'No data. Run crawler first.'}

    max_num = 45 if game == '645' else 55
    n_total = len(data)

    scores, full_freq, recent_30, gaps = comprehensive_score(data, max_num)
    pairs = pair_strength(data, last_n=200)

    sums = [sum(e['numbers']) for e in data]
    sum_q25 = np.percentile(sums, 25)
    sum_q75 = np.percentile(sums, 75)

    oe_dist = Counter()
    for e in data:
        odd = sum(1 for n in e['numbers'] if n % 2 == 1)
        oe_dist[(odd, 6 - odd)] += 1
    target_oe = [oe for oe, c in oe_dist.most_common(3)]

    sorted_nums = sorted(scores.keys(), key=lambda n: -scores[n])
    top12 = sorted_nums[:12]

    pair_map = defaultdict(int)
    for (a, b), c in pairs.most_common(50):
        pair_map[(a, b)] = c
        pair_map[(b, a)] = c

    best_combo = None
    best_score = -1

    for trial in range(n_trials):
        sets = []
        for i in range(n_sets):
            s = set()
            pool_top = list(top12)
            np.random.shuffle(pool_top)
            for n in pool_top[:4]:
                s.add(n)
            extra_pool = sorted_nums[12:25]
            np.random.shuffle(extra_pool)
            for n in extra_pool:
                if len(s) >= 6:
                    break
                s.add(n)
            sets.append(sorted(s))

        valid = True
        for s in sets:
            sm = sum(s)
            odd = sum(1 for n in s if n % 2 == 1)
            if not (sum_q25 <= sm <= sum_q75):
                valid = False
            if (odd, 6 - odd) not in target_oe:
                valid = False
        if not valid:
            continue

        if min(sum(1 for n in s if n in top12) for s in sets) < 4:
            continue

        all_diff = True
        for i in range(len(sets)):
            for j in range(i + 1, len(sets)):
                if len(set(sets[i]) & set(sets[j])) >= 5:
                    all_diff = False
                    break
        if not all_diff:
            continue

        union = set()
        for s in sets:
            union.update(s)
        coverage = sum(1 for n in top12 if n in union)
        diversity = len(union)

        pair_bonus = 0
        for s in sets:
            ns = sorted(s)
            for ii in range(len(ns)):
                for jj in range(ii + 1, len(ns)):
                    pair_bonus += pair_map.get((ns[ii], ns[jj]), 0)

        score_total = sum(scores[n] for s in sets for n in s)
        total_score = coverage * 20 + diversity * 3 + pair_bonus * 0.5 + score_total * 0.05

        if total_score > best_score:
            best_score = total_score
            best_combo = sets

    # Power suggestions (655 only)
    power_top = []
    if game == '655':
        pw_full = Counter()
        pw_last = {}
        for i, e in enumerate(data):
            if 'power' in e:
                pw_full[e['power']] += 1
                pw_last[e['power']] = i
        pw_score = {}
        for n in range(1, max_num + 1):
            pw_score[n] = (
                pw_full.get(n, 0) / n_total * 100 * 4 +
                ((n_total - 1 - pw_last.get(n, -1)) / 30) * 8
            )
        power_top = [n for n, _ in sorted(pw_score.items(), key=lambda x: -x[1])[:5]]

    # Build result sets
    result_sets = []
    for i, s in enumerate(best_combo or []):
        result_sets.append({
            'numbers': s,
            'power': power_top[i] if game == '655' and i < len(power_top) else None,
            'sum': sum(s),
            'odd': sum(1 for n in s if n % 2 == 1),
            'avg_score': round(sum(scores[n] for n in s) / 6, 1),
        })

    total_comb = math.comb(max_num, 6)
    p_any = sum(math.comb(6, k) * math.comb(max_num - 6, 6 - k) for k in range(3, 7)) / total_comb * 100
    p_n = (1 - (1 - p_any / 100) ** n_sets) * 100

    top15_detail = []
    for n in sorted_nums[:15]:
        top15_detail.append({
            'number': n,
            'freq': full_freq.get(n, 0),
            'freq_pct': round(full_freq.get(n, 0) / n_total * 100, 1),
            'recent_30': recent_30.get(n, 0),
            'gap': gaps[n],
            'score': round(scores[n], 1),
        })

    return {
        'game': game,
        'n_draws': n_total,
        'first_date': data[0]['date'],
        'last_date': data[-1]['date'],
        'last_draw_id': data[-1]['draw_id'],
        'sets': result_sets,
        'top15': top15_detail,
        'power_top': power_top,
        'top_pairs': [{'pair': list(p), 'count': c} for p, c in pairs.most_common(8)],
        'win_prob_pct': round(p_n, 2),
        'recent_draws': [
            {
                'draw_id': e['draw_id'],
                'date': e['date'],
                'numbers': e['numbers'],
                'power': e.get('power'),
            }
            for e in data[-10:]
        ],
    }
