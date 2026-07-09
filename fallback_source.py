"""
Fallback data source: dataset cong khai vietvudanh/vietlott-data (cap nhat hang ngay
boi GitHub Actions cua du an do). Dung khi crawl truc tiep vietlott.vn bi chan (403).

Format nguon (JSONL, moi dong 1 ky):
  {"date": "2017-08-01", "id": "00001", "result": [n1..n6] hoac [n1..n6, power], ...}
"""
import json
import os
import csv
from datetime import datetime

try:
    from curl_cffi import requests
    IMPERSONATE = {'impersonate': 'chrome'}
except ImportError:
    import requests
    IMPERSONATE = {}

DATASET_URLS = {
    '645': [
        'https://raw.githubusercontent.com/vietvudanh/vietlott-data/master/data/power645.jsonl',
        'https://cdn.jsdelivr.net/gh/vietvudanh/vietlott-data@master/data/power645.jsonl',
    ],
    '655': [
        'https://raw.githubusercontent.com/vietvudanh/vietlott-data/master/data/power655.jsonl',
        'https://cdn.jsdelivr.net/gh/vietvudanh/vietlott-data@master/data/power655.jsonl',
    ],
}
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')


def _csv_path(game):
    return os.path.join(DATA_DIR, f'vietlott_{game}.csv')


def _existing_ids(game):
    path = _csv_path(game)
    ids = set()
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            for row in csv.DictReader(f):
                ids.add(row['draw_id'])
    return ids


def sync_from_public_dataset(game):
    """Tai dataset cong khai, merge cac ky con thieu vao CSV. Tra ve so ky them moi."""
    resp = None
    last_err = None
    for url in DATASET_URLS[game]:
        try:
            resp = requests.get(url, timeout=60, **IMPERSONATE)
            resp.raise_for_status()
            break
        except Exception as e:
            last_err = e
            resp = None
    if resp is None:
        raise last_err

    existing = _existing_ids(game)
    new_rows = []

    for line in resp.text.strip().splitlines():
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        draw_id = str(rec.get('id', '')).zfill(5)
        if not draw_id or draw_id in existing:
            continue
        result = rec.get('result') or []
        if len(result) < 6:
            continue
        # date: YYYY-MM-DD -> dd/mm/yyyy
        try:
            d = datetime.strptime(rec['date'], '%Y-%m-%d').strftime('%d/%m/%Y')
        except (KeyError, ValueError):
            continue
        row = {'date': d, 'draw_id': draw_id}
        for i in range(6):
            row[f'n{i+1}'] = f'{int(result[i]):02d}'
        if game == '655':
            row['power'] = f'{int(result[6]):02d}' if len(result) > 6 else ''
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
        # ghi theo thu tu draw_id tang dan
        for row in sorted(new_rows, key=lambda r: r['draw_id']):
            writer.writerow(row)

    return len(new_rows)


if __name__ == '__main__':
    import sys
    if sys.platform == 'win32':
        sys.stdout.reconfigure(encoding='utf-8')
    for g in ('645', '655'):
        try:
            n = sync_from_public_dataset(g)
            print(f'{g}: +{n} ky tu dataset cong khai')
        except Exception as e:
            print(f'{g}: loi - {e}')
