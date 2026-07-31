"""
Wheeling System (he thong banh xe) - abbreviated wheel voi dam bao toan hoc.

Nguyen ly: chon K so (pool), sinh so ve toi thieu sao cho MOI bo ba (triple)
trong pool deu nam tron trong it nhat 1 ve. Khi do:

  DAM BAO "3-if-3": neu >= 3 so trong pool xuat hien trong ket qua
  -> chac chan co it nhat 1 ve trung >= 3 so (Giai 3).

Day la bai toan covering design C(K,6,3), giai bang greedy set-cover
nhieu lan khoi dong ngau nhien + kiem chung exhaustive.
"""
import random
from itertools import combinations

# ── Templates tinh san (chi so 0-based, da verify exhaustive) ──
# Pool 8 so, 4 ve: dam bao 3-if-3 (3 so pool ra -> chac chan 1 ve trung >= 3)
WHEEL_8_3IF3 = [
    [0, 2, 3, 5, 6, 7], [0, 1, 3, 4, 5, 6],
    [1, 2, 4, 5, 6, 7], [0, 1, 2, 3, 4, 7],
]
# Pool 12 so, 8 ve: dam bao 3-if-4 (4 so pool ra -> chac chan 1 ve trung >= 3;
# 3 so pool ra -> ~70% co ve trung 3)
WHEEL_12_3IF4 = [
    [0, 4, 5, 8, 10, 11], [0, 1, 2, 3, 6, 7], [1, 3, 4, 7, 9, 11],
    [2, 5, 6, 8, 9, 10], [2, 4, 5, 6, 8, 11], [1, 3, 4, 7, 10, 11],
    [0, 1, 3, 5, 7, 9], [0, 2, 5, 6, 9, 10],
]


def apply_template(pool, template):
    """Map pool so thuc (sorted) vao template chi so -> list ve."""
    pool = sorted(pool)
    return [sorted(pool[i] for i in ticket) for ticket in template]


def generate_wheel(pool, max_restarts=300, seed=42):
    """
    Sinh bo ve wheel tu pool (list so).
    Tra ve list ve (moi ve la list 6 so sorted), it ve nhat tim duoc.
    """
    pool = sorted(pool)
    if len(pool) < 6:
        raise ValueError('Pool can >= 6 so')

    all_triples = list(combinations(pool, 3))
    all_blocks = list(combinations(pool, 6))
    rng = random.Random(seed)

    best = None
    for _ in range(max_restarts):
        uncovered = set(all_triples)
        chosen = []
        blocks = all_blocks[:]
        rng.shuffle(blocks)

        while uncovered:
            # Greedy: chon ve phu nhieu triple chua duoc phu nhat
            best_blk = None
            best_cover = -1
            for b in blocks:
                c = len(uncovered & set(combinations(b, 3)))
                if c > best_cover:
                    best_cover = c
                    best_blk = b
            chosen.append(best_blk)
            uncovered -= set(combinations(best_blk, 3))

        if best is None or len(chosen) < len(best):
            best = chosen

    return [list(b) for b in best]


def verify_wheel(pool, tickets):
    """Kiem chung exhaustive: moi triple cua pool nam tron trong >= 1 ve."""
    pool = sorted(pool)
    ticket_sets = [set(t) for t in tickets]
    for triple in combinations(pool, 3):
        ts = set(triple)
        if not any(ts <= t for t in ticket_sets):
            return False, triple
    return True, None


def score_wheel(tickets, actual_numbers):
    """Doi chieu wheel voi ket qua: tra ve list matched per ve + best."""
    actual = set(actual_numbers)
    matched = [len(set(t) & actual) for t in tickets]
    return matched


if __name__ == '__main__':
    import sys
    if sys.platform == 'win32':
        sys.stdout.reconfigure(encoding='utf-8')

    # Demo voi pool 9 so
    pool = [4, 8, 16, 22, 23, 29, 34, 43, 53]
    tickets = generate_wheel(pool)
    ok, missing = verify_wheel(pool, tickets)
    print(f'Pool {len(pool)} so: {pool}')
    print(f'So ve: {len(tickets)} (chi phi {len(tickets)*10}k/ky)')
    for i, t in enumerate(tickets):
        print(f'  Ve {i+1}: {" ".join(f"{n:02d}" for n in t)}')
    print(f'Kiem chung dam bao 3-if-3: {"DAT" if ok else f"LOI - triple {missing} khong duoc phu"}')

    # Stress test: moi truong hop 3 so pool xuat hien -> phai co ve trung >= 3
    worst = 6
    for triple in combinations(pool, 3):
        best_m = max(len(set(t) & set(triple)) for t in tickets)
        worst = min(worst, best_m)
    print(f'Kiem tra tat ca {len(list(combinations(pool, 3)))} triple: ve tot nhat luon trung >= {worst} so')
