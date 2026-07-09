"""
Vietlott Analyzer - Main CLI
Crawl, analyze, and predict Vietlott lottery results.
"""

import sys
import os

# Ensure UTF-8 output on Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

from crawler import crawl, load_data
from analyzer import print_report, full_report
from predictor import print_predictions


def print_usage():
    print("""
╔══════════════════════════════════════════════════════╗
║         VIETLOTT ANALYZER - Phan tich xo so          ║
╚══════════════════════════════════════════════════════╝

Cach dung:
  python main.py <lenh> [tham_so]

Cac lenh:
  crawl [645|655] [so_ky]    Crawl ket qua tu vietlott.vn
                              645 = Mega 6/45 (mac dinh)
                              655 = Power 6/55
                              so_ky = 0 (tat ca) hoac so ky muon lay

  stats [645|655]             Phan tich thong ke day du
                              - Tan suat xuat hien
                              - So nong / so lanh
                              - So qua han
                              - Cap so hay di cung
                              - Phan bo le/chan, cao/thap

  predict [645|655] [chien_luoc] [so_bo]
                              Du doan so
                              Chien luoc: all, hot, cold, balanced,
                                          frequency, pattern
                              So bo: so luong bo so muon tao

  info [645|655]              Hien thi thong tin du lieu da crawl

Vi du:
  python main.py crawl 645 100   # Crawl 100 ky Mega 6/45
  python main.py crawl 655       # Crawl tat ca Power 6/55
  python main.py stats 645       # Thong ke Mega 6/45
  python main.py predict 645 all # Du doan voi tat ca chien luoc
  python main.py predict 655 hot 3  # 3 bo so nong Power 6/55
""")


def cmd_info(game: str):
    data = load_data(game)
    game_name = "Mega 6/45" if game == "645" else "Power 6/55"

    if not data:
        print(f"\nChua co du lieu {game_name}. Chay 'python main.py crawl {game}' truoc.")
        return

    print(f"\n--- Thong tin du lieu {game_name} ---")
    print(f"  Tong so ky: {len(data)}")
    print(f"  Ky dau:     #{data[0]['draw_id']} ({data[0]['date']})")
    print(f"  Ky cuoi:    #{data[-1]['draw_id']} ({data[-1]['date']})")

    last5 = data[-5:]
    print(f"\n  5 ky gan nhat:")
    for entry in reversed(last5):
        nums = " ".join(f"{n:02d}" for n in entry["numbers"])
        power = f" | {entry['power']:02d}" if "power" in entry else ""
        print(f"    #{entry['draw_id']} ({entry['date']}): {nums}{power}")
    print()


def main():
    if len(sys.argv) < 2:
        print_usage()
        return

    cmd = sys.argv[1].lower()
    game = sys.argv[2] if len(sys.argv) > 2 else "645"

    if game not in ("645", "655"):
        # Maybe the arg was something else, default to 645
        if cmd in ("645", "655"):
            game = cmd
            cmd = sys.argv[2] if len(sys.argv) > 2 else "crawl"
        else:
            game = "645"

    if cmd == "crawl":
        max_draws = int(sys.argv[3]) if len(sys.argv) > 3 else 0
        crawl(game, max_draws, delay=0.3)

    elif cmd == "stats":
        print_report(game)

    elif cmd == "predict":
        strategy = sys.argv[3] if len(sys.argv) > 3 else "all"
        num_sets = int(sys.argv[4]) if len(sys.argv) > 4 else 5
        print_predictions(game, num_sets, strategy)

    elif cmd == "info":
        cmd_info(game)

    elif cmd in ("help", "-h", "--help"):
        print_usage()

    else:
        print(f"Lenh khong hop le: {cmd}")
        print_usage()


if __name__ == "__main__":
    main()
