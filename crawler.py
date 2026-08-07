"""
Vietlott Result Crawler
Crawl historical lottery results from vietlott.vn via AjaxPro API
Supports: Mega 6/45, Power 6/55
"""

import json
import re
import csv
import time
import os
from datetime import datetime
from bs4 import BeautifulSoup

# curl_cffi gia lap TLS fingerprint Chrome that -> vuot Cloudflare 403
# (requests thuong bi Cloudflare nhan dien la bot tren IP datacenter)
try:
    from curl_cffi import requests
    IMPERSONATE = {'impersonate': 'chrome'}
except ImportError:
    import requests
    IMPERSONATE = {}

BASE_URL = "https://vietlott.vn/ajaxpro"
RENDER_URL = f"{BASE_URL}/Vietlott.Utility.WebEnvironments,Vietlott.Utility.ashx"
GAME_URLS = {
    "645": f"{BASE_URL}/Vietlott.PlugIn.WebParts.Game645ResultDetailWebPart,Vietlott.PlugIn.WebParts.ashx",
    "655": f"{BASE_URL}/Vietlott.PlugIn.WebParts.Game655ResultDetailWebPart,Vietlott.PlugIn.WebParts.ashx",
    "535": f"{BASE_URL}/Vietlott.PlugIn.WebParts.Game535ResultDetailWebPart,Vietlott.PlugIn.WebParts.ashx",
}

# Cau hinh tung game: so luong so chinh (K), dai so (N), co so phu khong
GAME_SPEC = {
    "645": {"name": "Mega 6/45",  "k": 6, "max": 45, "bonus": None},
    "655": {"name": "Power 6/55", "k": 6, "max": 55, "bonus": "power"},
    # 5/35: 5 so tu 1-35 + 1 so dac biet tu 1-12, quay 2 lan/ngay (13h & 21h)
    "535": {"name": "Lotto 5/35", "k": 5, "max": 35, "bonus": "special", "bonus_max": 12},
}
HEADERS = {
    "Content-Type": "text/plain; charset=utf-8",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://vietlott.vn/",
}
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")


def get_render_info() -> dict:
    """Get RenderInfo object required for all AjaxPro calls."""
    h = {**HEADERS, "X-AjaxPro-Method": "ServerSideFrontEndCreateRenderInfo"}
    resp = requests.post(RENDER_URL, headers=h, data='{"SiteId":"main.frontend.vi"}', timeout=15, **IMPERSONATE)
    resp.raise_for_status()
    ri = resp.json()["value"]
    ri["SiteLang"] = "vi"
    return ri


def fetch_draw(game: str, draw_id: str, render_info: dict) -> dict | None:
    """Fetch a single draw result. Returns dict with date, draw_id, numbers or None if not found."""
    url = GAME_URLS[game]
    h = {**HEADERS, "X-AjaxPro-Method": "ServerSideDrawResult"}
    body = json.dumps({"ORenderInfo": render_info, "Key": "56779db8", "DrawId": draw_id})

    resp = requests.post(url, headers=h, data=body, timeout=15, **IMPERSONATE)
    resp.raise_for_status()
    data = resp.json()
    v = data.get("value", {})

    if v.get("Error"):
        return None

    html = v.get("RetExtraParam1", "") or ""
    if not html:
        return None

    soup = BeautifulSoup(html, "html.parser")

    # Extract date from heading like "Kỳ quay thưởng #01490 ngày 29/03/2026"
    heading = soup.get_text(" ", strip=True)
    date_match = re.search(r"ngày\s+(\d{2}/\d{2}/\d{4})", heading)
    date_str = date_match.group(1) if date_match else ""

    # Extract numbers from <span> elements
    spans = soup.select("span")
    numbers = [s.get_text(strip=True) for s in spans if re.match(r"^\d{2}$", s.get_text(strip=True))]

    if not numbers:
        return None

    spec = GAME_SPEC[game]
    k = spec["k"]
    main_numbers = numbers[:k]
    if len(main_numbers) != k:
        return None
    # So phu (Power cua 655 / so dac biet cua 535) nam ngay sau cac so chinh
    power_number = numbers[k] if (spec["bonus"] and len(numbers) > k) else ""

    return {
        "date": date_str,
        "draw_id": draw_id,
        "numbers": main_numbers,
        "power_number": power_number,
    }


def get_csv_path(game: str) -> str:
    os.makedirs(DATA_DIR, exist_ok=True)
    return os.path.join(DATA_DIR, f"vietlott_{game}.csv")


def load_existing(game: str) -> set[str]:
    """Load already-crawled draw IDs from CSV."""
    path = get_csv_path(game)
    if not os.path.exists(path):
        return set()
    existing = set()
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            existing.add(row["draw_id"])
    return existing


def save_results(game: str, results: list[dict]):
    """Append results to CSV file."""
    path = get_csv_path(game)
    file_exists = os.path.exists(path)

    spec = GAME_SPEC[game]
    fieldnames = ["date", "draw_id"] + [f"n{i+1}" for i in range(spec["k"])]
    if spec["bonus"]:
        fieldnames.append("power")

    with open(path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        for r in results:
            row = {
                "date": r["date"],
                "draw_id": r["draw_id"],
            }
            for i, n in enumerate(r["numbers"]):
                row[f"n{i+1}"] = n
            if spec["bonus"]:
                row["power"] = r["power_number"]
            writer.writerow(row)


def crawl(game: str = "645", max_draws: int = 0, delay: float = 0.3):
    """
    Crawl historical results for a game.
    game: '645' for Mega 6/45, '655' for Power 6/55
    max_draws: 0 = crawl all, >0 = crawl up to N draws
    delay: seconds between requests
    """
    print(f"[Crawler] Starting crawl for {GAME_SPEC[game]['name']}...")

    ri = get_render_info()
    existing = load_existing(game)
    print(f"[Crawler] Already have {len(existing)} draws in database")

    # Find latest draw ID by trying recent ones.
    # Bat dau do tu (ky lon nhat da co + bien do) de khong phai doan cung.
    latest_id = None
    have_max = max((int(x) for x in existing), default=0)
    default_probe = {"645": 1560, "655": 1400, "535": 900}.get(game, 1500)
    start_probe = max(have_max + 60, default_probe)

    # Probe to find the latest valid draw
    print("[Crawler] Finding latest draw...")
    for probe in range(start_probe, max(0, start_probe - 120), -1):
        draw_id = f"{probe:05d}"
        result = fetch_draw(game, draw_id, ri)
        if result:
            latest_id = probe
            print(f"[Crawler] Latest draw: #{draw_id} ({result['date']})")
            break
        time.sleep(0.1)

    if not latest_id:
        print("[Crawler] Could not find latest draw!")
        return

    # Crawl backwards from latest
    results = []
    consecutive_fails = 0
    crawled = 0

    for draw_num in range(latest_id, 0, -1):
        draw_id = f"{draw_num:05d}"

        if draw_id in existing:
            consecutive_fails = 0
            continue

        if max_draws > 0 and crawled >= max_draws:
            break

        try:
            result = fetch_draw(game, draw_id, ri)
            if result:
                results.append(result)
                crawled += 1
                consecutive_fails = 0

                if crawled % 10 == 0:
                    print(f"[Crawler] Crawled {crawled} draws (current: #{draw_id} {result['date']})")
                    # Save periodically
                    save_results(game, results)
                    results = []
            else:
                consecutive_fails += 1
        except Exception as e:
            print(f"[Crawler] Error at #{draw_id}: {e}")
            consecutive_fails += 1

        # Stop if too many consecutive failures (reached beginning of history)
        if consecutive_fails > 20:
            print(f"[Crawler] Stopping - {consecutive_fails} consecutive failures (likely reached start of history)")
            break

        time.sleep(delay)

    # Save remaining
    if results:
        save_results(game, results)

    total = len(existing) + crawled
    print(f"[Crawler] Done! Crawled {crawled} new draws. Total: {total}")


def load_data(game: str = "645") -> list[dict]:
    """Load all crawled data from CSV, sorted by draw_id ascending."""
    path = get_csv_path(game)
    if not os.path.exists(path):
        return []

    spec = GAME_SPEC[game]
    rows = []
    seen_ids = set()
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["draw_id"] in seen_ids:
                continue  # chong trung lap
            seen_ids.add(row["draw_id"])
            numbers = [int(row[f"n{i}"]) for i in range(1, spec["k"] + 1)]
            entry = {
                "date": row["date"],
                "draw_id": row["draw_id"],
                "numbers": sorted(numbers),
            }
            if spec["bonus"] and row.get("power"):
                entry["power"] = int(row["power"])
            rows.append(entry)

    rows.sort(key=lambda x: x["draw_id"])
    return rows


if __name__ == "__main__":
    import sys
    game = sys.argv[1] if len(sys.argv) > 1 else "645"
    max_draws = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    crawl(game, max_draws)
