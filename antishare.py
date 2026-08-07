"""
Anti-Share Optimizer - bo so "jackpot thong minh".

Nguyen ly: xac suat trung jackpot cua MOI to hop la nhu nhau, nhung jackpot
CHIA DEU cho nguoi cung trung. Nguoi choi Viet chon so rat lech:
  - Ngay sinh: 1-31 (dac biet 1-12 vi vua la ngay vua la thang)
  - So "dep" phong thuy: 39/79 (than tai), 68 (loc phat), 86, 38/78, duoi 9
  - Day so lien tiep, cap so chan, boi so cua 5, pattern hinh hoc tren phieu

=> Chon bo so IT NGUOI DANH: neu trung jackpot, xac suat an tron cao hon han.
Day la thuat toan DUY NHAT thay doi duoc ky vong TIEN (khong doi xac suat trung).

Trade-off: bo nay KHONG toi uu tan suat/thong ke cho Giai 3 nhu cac bo khac.
"""
import random

# So "dep" nguoi Viet hay danh (trong khoang 1-55)
VN_LUCKY = {6, 8, 9, 16, 18, 19, 26, 28, 29, 36, 38, 39, 46, 48, 49, 52, 53, 55}
# 39/79 than tai -> 39; 68 loc phat; 86 nguoc; cac duoi 6/8/9 deu duoc ua chuong


def popularity(n):
    """Uoc luong do pho bien cua 1 so (cang cao = cang nhieu nguoi danh)."""
    p = 1.0
    if n <= 12:
        p += 0.9      # vua ngay vua thang sinh
    elif n <= 31:
        p += 0.5      # ngay sinh
    if n in VN_LUCKY:
        p += 0.45     # so phong thuy
    if n % 10 in (8, 9):
        p += 0.15     # duoi 8/9 "phat/truong cuu"
    if n in (4, 13, 14, 44):
        p -= 0.25     # so "xui" (tu/thap tu) - it nguoi danh
    return p


def set_penalty(nums):
    """Phat cac pattern to hop nhieu nguoi danh."""
    nums = sorted(nums)
    pen = 0.0
    # Chuoi lien tiep (1-2-3..., 40-41-42...): cuc ky pho bien
    consec = sum(1 for i in range(len(nums) - 1) if nums[i + 1] - nums[i] == 1)
    pen += consec * 0.6
    # Cap so cong (buoc deu): 5-10-15-20...
    diffs = {nums[i + 1] - nums[i] for i in range(len(nums) - 1)}
    if len(diffs) == 1:
        pen += 2.0
    # Toan bo <= 31 (ai danh ngay sinh cung nam vung nay)
    if all(n <= 31 for n in nums):
        pen += 1.2
    # Toan boi so 5 (5-10-15...): pattern phieu
    if all(n % 5 == 0 for n in nums):
        pen += 2.0
    # Qua nhieu so lucky trong 1 bo
    lucky_cnt = sum(1 for n in nums if n in VN_LUCKY)
    if lucky_cnt >= 3:
        pen += (lucky_cnt - 2) * 0.4
    return pen


def set_share_score(nums):
    """Tong diem 'de bi chia': cang THAP cang tot."""
    return sum(popularity(n) for n in nums) + set_penalty(nums)


def generate_antishare(max_num, pick=6, n_candidates=8000, seed=None):
    """
    Sinh bo 6 so toi thieu do pho bien (it nguoi cung danh nhat).
    Random search co trong so nghieng ve so cao/khong dep.
    """
    rng = random.Random(seed)
    numbers = list(range(1, max_num + 1))
    # Trong so nghich dao popularity -> uu tien so it nguoi danh
    weights = [1.0 / popularity(n) ** 2 for n in numbers]

    best = None
    best_score = float('inf')
    for _ in range(n_candidates):
        chosen = set()
        while len(chosen) < pick:
            chosen.add(rng.choices(numbers, weights=weights)[0])
        nums = sorted(chosen)
        score = set_share_score(nums)
        if score < best_score:
            best_score = score
            best = nums

    return {
        'numbers': best,
        'share_score': round(best_score, 2),
        'avg_random_score': round(sum(set_share_score(sorted(random.Random(1).sample(numbers, 6))) for _ in range(1)) , 2),
    }


def antishare_power(max_num, exclude=(), seed=None):
    """
    Chon so phu (Power 1-55 cua 655 / so dac biet 1-12 cua 535) it nguoi danh.
    Uu tien nua tren cua dai so (khong phai ngay sinh) va tranh so 'dep'.
    """
    rng = random.Random(seed)
    lo = max_num // 2 + 1          # 655 -> tu 28; 535 (1-12) -> tu 7
    cands = [n for n in range(lo, max_num + 1)
             if n not in VN_LUCKY and n not in exclude]
    if not cands:
        cands = [n for n in range(1, max_num + 1) if n not in exclude]
    return rng.choice(cands)


if __name__ == '__main__':
    import sys
    if sys.platform == 'win32':
        sys.stdout.reconfigure(encoding='utf-8')
    for max_num, name in ((45, 'Mega 6/45'), (55, 'Power 6/55')):
        r = generate_antishare(max_num, seed=42)
        nums = ' '.join(f'{n:02d}' for n in r['numbers'])
        print(f'{name}: {nums}  (share_score={r["share_score"]})')
        # So sanh voi bo pho bien
        popular_set = [8, 9, 18, 19, 28, 29] if max_num >= 29 else list(range(1, 7))
        print(f'  Doi chieu bo "dep" 08 09 18 19 28 29: score={set_share_score(popular_set):.2f} (cang cao cang de bi chia)')
        if max_num == 55:
            pw = antishare_power(55, exclude=r['numbers'], seed=42)
            print(f'  Power anti-share: {pw:02d}')
