"""
Mirror source: xoso.com.vn - ket qua TUOI (cap nhat ngay sau gio quay).
Tang 2 trong chuoi fallback: vietlott truc tiep -> xoso.com.vn -> dataset cong khai.

Cau truc HTML moi ky:
  ... ngày DD/MM/YYYY ... Kỳ quay thưởng: <strong>#01368</strong> ...
  <span class=btn-results>04</span> x6 ... <span class="btn-results bg_jackpot">08</span>
So co class bg_jackpot = so Power (655). So tren trang co the KHONG sap thu tu -> sort.
"""
import re
import csv
import os

try:
    from curl_cffi import requests
    IMPERSONATE = {'impersonate': 'chrome'}
except ImportError:
    import requests
    IMPERSONATE = {}

from fallback_source import _csv_path, _existing_ids, DATA_DIR

MIRROR_URLS = {
    '645': 'https://xoso.com.vn/xo-so-tu-chon-mega-645.html',
    '655': 'https://xoso.com.vn/xo-so-power-655.html',
}
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'text/html,application/xhtml+xml',
    'Accept-Language': 'vi-VN,vi;q=0.9',
}

DRAW_RE = re.compile(r'K[ỳy]\s*quay\s*th[ưu][ởo]ng:\s*<strong>#(\d{5})</strong>', re.I)
BALL_RE = re.compile(r'<span\s+class="?btn-results(\s+bg_jackpot)?"?>(\d{1,2})</span>', re.I)
DATE_HREF_RE = re.compile(r'ngay-(\d{2})-(\d{2})-(\d{4})\.html')
DATE_TEXT_RE = re.compile(r'ng[àa]y\s+(\d{2}/\d{2}/\d{4})', re.I)


def _find_date_before(html, pos):
    """Tim ngay gan nhat phia truoc vi tri pos (trong header cua block ket qua)."""
    window = html[max(0, pos - 1500):pos]
    hrefs = DATE_HREF_RE.findall(window)
    if hrefs:
        d, m, y = hrefs[-1]
        return f'{d}/{m}/{y}'
    texts = DATE_TEXT_RE.findall(window)
    if texts:
        return texts[-1]
    return ''


def parse_mirror_html(html, game):
    """Parse HTML listing -> list of {date, draw_id, numbers, power}."""
    max_num = 45 if game == '645' else 55
    results = []
    matches = list(DRAW_RE.finditer(html))

    for i, m in enumerate(matches):
        draw_id = m.group(1)
        date_str = _find_date_before(html, m.start())

        # So nam giua ky nay va ky tiep theo (hoac het 2000 ky tu sau match)
        block_end = matches[i + 1].start() if i + 1 < len(matches) else m.end() + 2000
        block = html[m.end():block_end]

        balls = BALL_RE.findall(block)
        main = []
        power = None
        for is_jackpot, num_str in balls:
            n = int(num_str)
            if not (1 <= n <= max_num):
                continue
            if is_jackpot.strip():
                power = n
            else:
                main.append(n)

        # Chi lay 6 so dau (block co the dinh bang thong ke khac)
        main = main[:6]
        if len(main) != 6 or not date_str:
            continue
        if game == '655' and power is None:
            continue

        results.append({
            'date': date_str,
            'draw_id': draw_id,
            'numbers': sorted(main),
            'power': power,
        })

    return results


def sync_from_mirror(game):
    """Fetch mirror, merge cac ky con thieu vao CSV. Tra ve so ky them moi."""
    url = MIRROR_URLS[game]
    resp = requests.get(url, headers=HEADERS, timeout=30, **IMPERSONATE)
    resp.raise_for_status()

    parsed = parse_mirror_html(resp.text, game)
    if not parsed:
        raise ValueError('Mirror parse duoc 0 ky - cau truc trang co the da doi')

    existing = _existing_ids(game)
    new_rows = []
    for r in parsed:
        if r['draw_id'] in existing:
            continue
        row = {'date': r['date'], 'draw_id': r['draw_id']}
        for i, n in enumerate(r['numbers']):
            row[f'n{i+1}'] = f'{n:02d}'
        if game == '655':
            row['power'] = f'{r["power"]:02d}'
        new_rows.append(row)

    if not new_rows:
        return 0

    path = _csv_path(game)
    file_exists = os.path.exists(path)
    fieldnames = ['date', 'draw_id', 'n1', 'n2', 'n3', 'n4', 'n5', 'n6']
    if game == '655':
        fieldnames.append('power')

    os.makedirs(DATA_DIR, exist_ok=True)
    with open(path, 'a', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        for row in sorted(new_rows, key=lambda r: r['draw_id']):
            writer.writerow(row)

    return len(new_rows)


if __name__ == '__main__':
    import sys
    if sys.platform == 'win32':
        sys.stdout.reconfigure(encoding='utf-8')
    for g in ('645', '655'):
        try:
            n = sync_from_mirror(g)
            print(f'{g}: +{n} ky tu mirror xoso.com.vn')
        except Exception as e:
            print(f'{g}: loi - {e}')
