"""
Vietlott Prediction Module
Uses statistical methods to suggest numbers.
DISCLAIMER: Lottery is random. No method can guarantee winning.
These are statistical suggestions based on historical patterns only.
"""

import random
import numpy as np
from collections import Counter
from crawler import load_data
from analyzer import frequency_analysis, hot_cold_analysis, gap_analysis, sum_analysis


def weighted_random_pick(weights: dict[int, float], count: int = 6) -> list[int]:
    """Pick numbers based on weighted probabilities."""
    numbers = list(weights.keys())
    probs = np.array([weights[n] for n in numbers])
    probs = probs / probs.sum()  # normalize

    chosen = set()
    attempts = 0
    while len(chosen) < count and attempts < 1000:
        pick = np.random.choice(numbers, p=probs)
        chosen.add(int(pick))
        attempts += 1

    return sorted(chosen)


def strategy_hot(data: list[dict], max_num: int = 45) -> list[int]:
    """Strategy 1: Pick from hot numbers (trending up recently)."""
    hc = hot_cold_analysis(data, recent_n=30)
    hot_numbers = [r["number"] for r in hc["hot"]]

    # Weight hot numbers higher
    weights = {}
    for n in range(1, max_num + 1):
        weights[n] = 1.0
    for i, n in enumerate(hot_numbers):
        weights[n] = 3.0 - (i * 0.2)  # top hot gets 3x weight

    return weighted_random_pick(weights, 6)


def strategy_cold(data: list[dict], max_num: int = 45) -> list[int]:
    """Strategy 2: Pick from cold/overdue numbers (mean reversion theory)."""
    gaps = gap_analysis(data, max_num)
    overdue = [r["number"] for r in gaps["overdue"]]

    weights = {}
    for n in range(1, max_num + 1):
        weights[n] = 1.0
    for i, n in enumerate(overdue):
        weights[n] = 3.0 - (i * 0.2)

    return weighted_random_pick(weights, 6)


def strategy_balanced(data: list[dict], max_num: int = 45) -> list[int]:
    """Strategy 3: Balanced approach - mix of hot, cold, and statistical constraints."""
    hc = hot_cold_analysis(data, recent_n=30)
    gaps = gap_analysis(data, max_num)
    ss = sum_analysis(data)

    hot_nums = [r["number"] for r in hc["hot"][:15]]
    overdue_nums = [r["number"] for r in gaps["overdue"][:10]]

    # Build weight combining hot trend and overdue status
    weights = {}
    for n in range(1, max_num + 1):
        w = 1.0
        if n in hot_nums:
            w += 1.5
        if n in overdue_nums:
            w += 1.0
        weights[n] = w

    # Try to generate a set that matches historical sum range
    target_sum_low = ss.get("q25", 100)
    target_sum_high = ss.get("q75", 180)

    best = None
    best_score = float("inf")

    for _ in range(500):
        pick = weighted_random_pick(weights, 6)
        s = sum(pick)
        # Score: prefer picks within the typical sum range
        if target_sum_low <= s <= target_sum_high:
            score = 0
        else:
            score = min(abs(s - target_sum_low), abs(s - target_sum_high))

        # Also prefer balanced odd/even (3-3 or 2-4)
        odd_count = sum(1 for n in pick if n % 2 == 1)
        if odd_count in (2, 3, 4):
            score -= 1

        if score < best_score:
            best_score = score
            best = pick

    return best or weighted_random_pick(weights, 6)


def strategy_frequency(data: list[dict], max_num: int = 45) -> list[int]:
    """Strategy 4: Pick based on overall frequency (most common numbers)."""
    freq = frequency_analysis(data)
    weights = {}
    for n, count in freq["frequency"]:
        weights[n] = count

    # Fill missing
    for n in range(1, max_num + 1):
        if n not in weights:
            weights[n] = 0.1

    return weighted_random_pick(weights, 6)


def strategy_pattern(data: list[dict], max_num: int = 45) -> list[int]:
    """Strategy 5: Pattern-based - follow common structural patterns."""
    # Analyze zones: low(1-15), mid(16-30), high(31-45)
    zone_size = max_num // 3

    # Count typical zone distributions
    zone_dist = Counter()
    for entry in data:
        zones = [0, 0, 0]
        for n in entry["numbers"]:
            if n <= zone_size:
                zones[0] += 1
            elif n <= zone_size * 2:
                zones[1] += 1
            else:
                zones[2] += 1
            zone_dist[tuple(zones)] = zone_dist.get(tuple(zones), 0)
        zone_dist[tuple(zones)] += 1

    # Pick the most common zone distribution
    most_common_zone = max(zone_dist, key=zone_dist.get)

    # Generate numbers following this zone pattern
    result = []
    for zone_idx, count in enumerate(most_common_zone):
        low = zone_idx * zone_size + 1
        high = min((zone_idx + 1) * zone_size, max_num)
        zone_nums = list(range(low, high + 1))

        # Weight by frequency within zone
        freq = frequency_analysis(data)
        freq_dict = dict(freq["frequency"])

        zone_weights = {n: freq_dict.get(n, 1) for n in zone_nums}
        for _ in range(count):
            if zone_nums:
                pick = weighted_random_pick(zone_weights, 1)[0]
                if pick not in result:
                    result.append(pick)
                    if pick in zone_weights:
                        del zone_weights[pick]

    # Fill if needed
    all_nums = set(range(1, max_num + 1)) - set(result)
    while len(result) < 6:
        result.append(random.choice(list(all_nums)))
        all_nums -= set(result)

    return sorted(result[:6])


STRATEGIES = {
    "hot": ("So Nong - Chon so dang len trend", strategy_hot),
    "cold": ("So Lanh/Qua Han - Chon so lau chua xuat hien", strategy_cold),
    "balanced": ("Can Bang - Ket hop nhieu yeu to thong ke", strategy_balanced),
    "frequency": ("Tan Suat - Chon so xuat hien nhieu nhat", strategy_frequency),
    "pattern": ("Mau Hinh - Theo phan bo vung so pho bien", strategy_pattern),
}


def predict(game: str = "645", num_sets: int = 5, strategy: str = "all") -> list[dict]:
    """
    Generate prediction sets.
    game: '645' or '655'
    num_sets: number of prediction sets to generate
    strategy: 'hot', 'cold', 'balanced', 'frequency', 'pattern', or 'all'
    """
    data = load_data(game)
    if not data:
        return [{"error": "No data. Run crawler first."}]

    max_num = 45 if game == "645" else 55
    predictions = []

    if strategy == "all":
        # One from each strategy
        for key, (desc, func) in STRATEGIES.items():
            numbers = func(data, max_num)
            predictions.append({
                "strategy": key,
                "description": desc,
                "numbers": numbers,
                "sum": sum(numbers),
                "odd_count": sum(1 for n in numbers if n % 2 == 1),
                "even_count": sum(1 for n in numbers if n % 2 == 0),
            })
    else:
        if strategy not in STRATEGIES:
            strategy = "balanced"
        desc, func = STRATEGIES[strategy]
        for i in range(num_sets):
            numbers = func(data, max_num)
            predictions.append({
                "strategy": strategy,
                "description": desc,
                "numbers": numbers,
                "sum": sum(numbers),
                "odd_count": sum(1 for n in numbers if n % 2 == 1),
                "even_count": sum(1 for n in numbers if n % 2 == 0),
            })

    return predictions


def print_predictions(game: str = "645", num_sets: int = 5, strategy: str = "all"):
    """Print formatted predictions."""
    predictions = predict(game, num_sets, strategy)

    game_name = "Mega 6/45" if game == "645" else "Power 6/55"
    print(f"\n{'='*60}")
    print(f"  DU DOAN {game_name.upper()}")
    print(f"  Luu y: Xo so la ngau nhien. Day chi la goi y thong ke!")
    print(f"{'='*60}")

    for i, p in enumerate(predictions):
        if "error" in p:
            print(p["error"])
            return

        nums_str = " ".join(f"{n:02d}" for n in p["numbers"])
        print(f"\n  Bo {i+1} [{p['strategy'].upper()}]: {nums_str}")
        print(f"    {p['description']}")
        print(f"    Tong: {p['sum']} | Le: {p['odd_count']} | Chan: {p['even_count']}")

    print(f"\n{'='*60}")
    print(f"  Chuc ban may man! 🍀")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    import sys
    game = sys.argv[1] if len(sys.argv) > 1 else "645"
    strategy = sys.argv[2] if len(sys.argv) > 2 else "all"
    num_sets = int(sys.argv[3]) if len(sys.argv) > 3 else 5
    print_predictions(game, num_sets, strategy)
