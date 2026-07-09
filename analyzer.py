"""
Vietlott Statistical Analyzer
Analyzes historical lottery results for frequency, hot/cold numbers, patterns, gaps.
"""

import numpy as np
from collections import Counter
from datetime import datetime
from crawler import load_data


def frequency_analysis(data: list[dict], last_n: int = 0) -> dict:
    """
    Analyze number frequency.
    last_n: 0 = all data, >0 = last N draws only
    """
    subset = data[-last_n:] if last_n > 0 else data
    total_draws = len(subset)

    counter = Counter()
    for entry in subset:
        for n in entry["numbers"]:
            counter[n] += 1

    # Sort by frequency descending
    freq = sorted(counter.items(), key=lambda x: -x[1])
    avg = total_draws * 6 / 45  # expected frequency for 6/45

    return {
        "total_draws": total_draws,
        "frequency": freq,
        "expected_avg": round(avg, 1),
        "most_common": freq[:10],
        "least_common": freq[-10:],
    }


def hot_cold_analysis(data: list[dict], recent_n: int = 30) -> dict:
    """
    Identify hot (frequent recently) and cold (rare recently) numbers.
    Compares recent_n draws vs overall frequency.
    """
    if len(data) < recent_n:
        recent_n = len(data)

    recent = data[-recent_n:]
    recent_counter = Counter()
    for entry in recent:
        for n in entry["numbers"]:
            recent_counter[n] += 1

    overall = frequency_analysis(data)
    overall_freq = dict(overall["frequency"])
    total = overall["total_draws"]

    results = []
    max_num = 45  # for 6/45
    for n in range(1, max_num + 1):
        recent_count = recent_counter.get(n, 0)
        overall_count = overall_freq.get(n, 0)
        recent_pct = recent_count / recent_n * 100
        overall_pct = overall_count / total * 100 if total > 0 else 0
        delta = recent_pct - overall_pct

        results.append({
            "number": n,
            "recent_count": recent_count,
            "recent_pct": round(recent_pct, 1),
            "overall_pct": round(overall_pct, 1),
            "delta": round(delta, 1),
        })

    # Sort by delta (positive = hot, negative = cold)
    results.sort(key=lambda x: -x["delta"])

    hot = [r for r in results if r["delta"] > 0][:10]
    cold = [r for r in results if r["delta"] < 0]
    cold.sort(key=lambda x: x["delta"])
    cold = cold[:10]

    return {
        "recent_draws": recent_n,
        "hot": hot,
        "cold": cold,
        "all": results,
    }


def gap_analysis(data: list[dict], max_num: int = 45) -> dict:
    """
    Analyze the gap (number of draws since last appearance) for each number.
    """
    last_seen = {}
    total = len(data)

    for i, entry in enumerate(data):
        for n in entry["numbers"]:
            last_seen[n] = i

    gaps = []
    for n in range(1, max_num + 1):
        if n in last_seen:
            gap = total - 1 - last_seen[n]
        else:
            gap = total
        gaps.append({"number": n, "gap": gap, "last_draw_idx": last_seen.get(n, -1)})

    gaps.sort(key=lambda x: -x["gap"])

    return {
        "overdue": gaps[:10],  # numbers with longest gaps (overdue)
        "recent": sorted(gaps, key=lambda x: x["gap"])[:10],  # recently appeared
        "all": gaps,
    }


def pair_analysis(data: list[dict], last_n: int = 0) -> dict:
    """Analyze which number pairs appear together most often."""
    subset = data[-last_n:] if last_n > 0 else data

    pair_counter = Counter()
    for entry in subset:
        nums = sorted(entry["numbers"])
        for i in range(len(nums)):
            for j in range(i + 1, len(nums)):
                pair_counter[(nums[i], nums[j])] += 1

    top_pairs = pair_counter.most_common(20)
    return {
        "total_draws": len(subset),
        "top_pairs": [{"pair": list(p), "count": c} for p, c in top_pairs],
    }


def consecutive_analysis(data: list[dict]) -> dict:
    """Analyze how often consecutive numbers appear together."""
    consec_counts = Counter()  # how many consecutive pairs per draw

    for entry in data:
        nums = sorted(entry["numbers"])
        consec = 0
        for i in range(len(nums) - 1):
            if nums[i + 1] - nums[i] == 1:
                consec += 1
        consec_counts[consec] += 1

    total = len(data)
    return {
        "distribution": {k: {"count": v, "pct": round(v / total * 100, 1)} for k, v in sorted(consec_counts.items())},
        "avg_consecutive": round(sum(k * v for k, v in consec_counts.items()) / total, 2) if total > 0 else 0,
    }


def sum_analysis(data: list[dict]) -> dict:
    """Analyze the sum of drawn numbers."""
    sums = [sum(entry["numbers"]) for entry in data]
    if not sums:
        return {}

    return {
        "mean": round(np.mean(sums), 1),
        "median": round(np.median(sums), 1),
        "std": round(np.std(sums), 1),
        "min": min(sums),
        "max": max(sums),
        "q25": round(np.percentile(sums, 25), 1),
        "q75": round(np.percentile(sums, 75), 1),
        "last_10": sums[-10:],
    }


def odd_even_analysis(data: list[dict]) -> dict:
    """Analyze odd/even distribution."""
    dist = Counter()
    for entry in data:
        odd_count = sum(1 for n in entry["numbers"] if n % 2 == 1)
        even_count = 6 - odd_count
        dist[f"{odd_count}L-{even_count}C"] += 1  # L=Lẻ(odd), C=Chẵn(even)

    total = len(data)
    return {
        "distribution": {k: {"count": v, "pct": round(v / total * 100, 1)} for k, v in sorted(dist.items())},
    }


def high_low_analysis(data: list[dict], mid: int = 23) -> dict:
    """Analyze high/low number distribution (split at midpoint)."""
    dist = Counter()
    for entry in data:
        low = sum(1 for n in entry["numbers"] if n <= mid)
        high = 6 - low
        dist[f"{low}T-{high}C"] += 1  # T=Thấp(low), C=Cao(high)

    total = len(data)
    return {
        "split_at": mid,
        "distribution": {k: {"count": v, "pct": round(v / total * 100, 1)} for k, v in sorted(dist.items())},
    }


def full_report(game: str = "645", recent_n: int = 30) -> dict:
    """Generate a comprehensive analysis report."""
    data = load_data(game)
    if not data:
        return {"error": "No data. Run crawler first."}

    max_num = 45 if game == "645" else 55

    return {
        "game": "Mega 6/45" if game == "645" else "Power 6/55",
        "total_draws": len(data),
        "date_range": f"{data[0]['date']} - {data[-1]['date']}",
        "frequency": frequency_analysis(data),
        "hot_cold": hot_cold_analysis(data, recent_n),
        "gaps": gap_analysis(data, max_num),
        "pairs": pair_analysis(data),
        "consecutive": consecutive_analysis(data),
        "sum_stats": sum_analysis(data),
        "odd_even": odd_even_analysis(data),
        "high_low": high_low_analysis(data, max_num // 2),
    }


def print_report(game: str = "645", recent_n: int = 30):
    """Print a formatted analysis report."""
    report = full_report(game, recent_n)
    if "error" in report:
        print(report["error"])
        return

    print(f"\n{'='*60}")
    print(f"  THONG KE XO SO {report['game'].upper()}")
    print(f"  Tong so ky: {report['total_draws']} | {report['date_range']}")
    print(f"{'='*60}")

    # Frequency
    freq = report["frequency"]
    print(f"\n--- TOP 10 SO XUAT HIEN NHIEU NHAT ---")
    for n, count in freq["most_common"]:
        bar = "█" * (count // 5)
        print(f"  So {n:02d}: {count:4d} lan ({count/freq['total_draws']*100:.1f}%) {bar}")

    print(f"\n--- TOP 10 SO XUAT HIEN IT NHAT ---")
    for n, count in freq["least_common"]:
        bar = "█" * (count // 5)
        print(f"  So {n:02d}: {count:4d} lan ({count/freq['total_draws']*100:.1f}%) {bar}")

    # Hot/Cold
    hc = report["hot_cold"]
    print(f"\n--- SO NONG (xuat hien nhieu trong {hc['recent_draws']} ky gan) ---")
    for r in hc["hot"][:7]:
        print(f"  So {r['number']:02d}: {r['recent_count']} lan ({r['recent_pct']:.1f}% vs TB {r['overall_pct']:.1f}%) [+{r['delta']:.1f}%]")

    print(f"\n--- SO LANH (it xuat hien trong {hc['recent_draws']} ky gan) ---")
    for r in hc["cold"][:7]:
        print(f"  So {r['number']:02d}: {r['recent_count']} lan ({r['recent_pct']:.1f}% vs TB {r['overall_pct']:.1f}%) [{r['delta']:.1f}%]")

    # Gaps
    gaps = report["gaps"]
    print(f"\n--- SO QUA HAN (lau chua xuat hien) ---")
    for r in gaps["overdue"][:7]:
        print(f"  So {r['number']:02d}: da {r['gap']} ky chua xuat hien")

    # Pairs
    pairs = report["pairs"]
    print(f"\n--- CAP SO HAY DI CUNG NHAU ---")
    for p in pairs["top_pairs"][:10]:
        print(f"  ({p['pair'][0]:02d}, {p['pair'][1]:02d}): {p['count']} lan")

    # Sum
    ss = report["sum_stats"]
    print(f"\n--- PHAN TICH TONG ---")
    print(f"  Trung binh: {ss['mean']} | Trung vi: {ss['median']}")
    print(f"  Do lech chuan: {ss['std']}")
    print(f"  Khoang pho bien: {ss['q25']} - {ss['q75']}")
    print(f"  10 ky gan: {ss['last_10']}")

    # Odd/Even
    oe = report["odd_even"]
    print(f"\n--- PHAN BO LE/CHAN ---")
    for k, v in oe["distribution"].items():
        print(f"  {k}: {v['count']} lan ({v['pct']}%)")

    # Consecutive
    consec = report["consecutive"]
    print(f"\n--- SO LIEN TIEP ---")
    print(f"  Trung binh cap lien tiep moi ky: {consec['avg_consecutive']}")
    for k, v in consec["distribution"].items():
        print(f"  {k} cap lien tiep: {v['count']} lan ({v['pct']}%)")

    print(f"\n{'='*60}")


if __name__ == "__main__":
    import sys
    game = sys.argv[1] if len(sys.argv) > 1 else "645"
    print_report(game)
