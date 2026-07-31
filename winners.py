"""
Crawl SO NGUOI TRUNG tung giai moi ky tu vietlott.vn (bang RetExtraParam2).
Dung de kiem chung thuc nghiem model Anti-Share:
  ky nao ket qua chua nhieu so "pho bien" -> so nguoi trung Giai 1/2/3 phai cao hon.

Output: data/winners_645.csv, data/winners_655.csv
  645: draw_id,date,jackpot_w,g1_w,g2_w,g3_w
  655: draw_id,date,jackpot1_w,jackpot2_w,g1_w,g2_w,g3_w
"""
import sys
import os
import re
import csv
import json
import time
from bs4 import BeautifulSoup

from crawler import get_render_info, GAME_URLS, HEADERS, load_data

try:
    from curl_cffi import requests
    IMPERSONATE = {'impersonate': 'chrome'}
except ImportError:
    import requests
    IMPERSONATE = {}

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')


def _parse_count(text):
    """'1.432' -> 1432, '0' -> 0"""
    t = text.strip().replace('.', '').replace(',', '')
    return int(t) if t.isdigit() else None


def fetch_winners(game, draw_id, render_info):
    """Lay so nguoi trung tung giai cua 1 ky. Tra ve dict hoac None."""
    url = GAME_URLS[game]
    h = {**HEADERS, 'X-AjaxPro-Method': 'ServerSideDrawResult'}
    body = json.dumps({'ORenderInfo': render_info, 'Key': '56779db8', 'DrawId': draw_id})
    resp = requests.post(url, headers=h, data=body, timeout=15, **IMPERSONATE)
    resp.raise_for_status()
    v = resp.json().get('value', {})
    if v.get('Error'):
        return None

    html1 = v.get('RetExtraParam1', '') or ''
    html2 = v.get('RetExtraParam2', '') or ''
    if not html2:
        return None

    # Ngay tu param1
    date_m = re.search(r'ng[àa]y\s+(\d{2}/\d{2}/\d{4})', BeautifulSoup(html1, 'html.parser').get_text(' '))
    date_str = date_m.group(1) if date_m else ''

    soup = BeautifulSoup(html2, 'html.parser')
    counts = {}
    for tr in soup.select('table tr'):
        cells = [c.get_text(' ', strip=True) for c in tr.find_all(['td', 'th'])]
        if len(cells) < 4:
            continue
        name = cells[0].lower()
        cnt = _parse_count(cells[-2])
        if cnt is None:
            continue
        if 'jackpot 2' in name:
            counts['jackpot2_w'] = cnt
        elif 'jackpot' in name:
            counts['jackpot1_w'] = cnt
        elif 'nhất' in name or 'nhat' in name:
            counts['g1_w'] = cnt
        elif 'nhì' in name or 'nhi' in name:
            counts['g2_w'] = cnt
        elif 'ba' in name:
            counts['g3_w'] = cnt

    if 'g3_w' not in counts:
        return None
    counts['draw_id'] = draw_id
    counts['date'] = date_str
    return counts


def csv_path(game):
    return os.path.join(DATA_DIR, f'winners_{game}.csv')


def fieldnames(game):
    if game == '655':
        return ['draw_id', 'date', 'jackpot1_w', 'jackpot2_w', 'g1_w', 'g2_w', 'g3_w']
    return ['draw_id', 'date', 'jackpot1_w', 'g1_w', 'g2_w', 'g3_w']


def existing_ids(game):
    path = csv_path(game)
    ids = set()
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            for row in csv.DictReader(f):
                ids.add(row['draw_id'])
    return ids


def crawl_winners(game, last_n=500, delay=0.25):
    """Crawl winner counts cho last_n ky gan nhat (bo qua ky da co)."""
    data = load_data(game)
    targets = [e['draw_id'] for e in data[-last_n:]]
    done = existing_ids(game)
    todo = [d for d in targets if d not in done]
    print(f'[{game}] Can crawl {len(todo)}/{len(targets)} ky (da co {len(done)})')
    if not todo:
        return 0

    ri = get_render_info()
    path = csv_path(game)
    file_exists = os.path.exists(path)
    added = 0
    fails = 0

    with open(path, 'a', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames(game), extrasaction='ignore')
        if not file_exists:
            writer.writeheader()
        for i, draw_id in enumerate(todo):
            try:
                w = fetch_winners(game, draw_id, ri)
                if w:
                    writer.writerow(w)
                    added += 1
                    fails = 0
                else:
                    fails += 1
            except Exception as e:
                fails += 1
                if fails >= 5:
                    print(f'[{game}] Dung: 5 loi lien tiep ({e})')
                    break
                ri = get_render_info()  # lam moi session
            if (i + 1) % 50 == 0:
                print(f'[{game}] {i+1}/{len(todo)} (them {added})')
                f.flush()
            time.sleep(delay)

    print(f'[{game}] Xong: +{added} ky winner data')
    return added


if __name__ == '__main__':
    if sys.platform == 'win32':
        sys.stdout.reconfigure(encoding='utf-8')
    last_n = int(sys.argv[1]) if len(sys.argv) > 1 else 500
    for g in ('645', '655'):
        crawl_winners(g, last_n)
