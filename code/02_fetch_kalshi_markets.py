"""Download every market in Kalshi's Economics category, live and historical.

Kalshi serves markets settled before a cutoff date from /historical/markets and
the rest from /markets, so both are queried for each series. Resumable: series
already listed in data/raw/kalshi_markets_done.txt are skipped. With --refresh
everything is downloaded again and the old file is replaced only when the new
one is complete; open markets change, so an update needs this.

Output: data/raw/kalshi_markets.jsonl (one market per line, with series_ticker)
"""
import json
import sys
import time
from pathlib import Path

import pandas as pd
import requests

from common import stamp

BASE = "https://api.elections.kalshi.com/trade-api/v2"
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/raw/kalshi_markets.jsonl"
DONE = ROOT / "data/raw/kalshi_markets_done.txt"
CATEGORIES = ["Economics"]
REFRESH = "--refresh" in sys.argv
FINAL_OUT, FINAL_DONE = OUT, DONE
if REFRESH:
    OUT, DONE = OUT.with_suffix(".jsonl.new"), DONE.with_suffix(".txt.new")
    OUT.unlink(missing_ok=True)
    DONE.unlink(missing_ok=True)


def get(path, params):
    for attempt in range(8):
        r = requests.get(BASE + path, params=params, timeout=60)
        if r.status_code == 200:
            return r.json()
        if r.status_code == 429 or r.status_code >= 500:
            time.sleep(1.5 * (attempt + 1))
            continue
        r.raise_for_status()
    raise RuntimeError(f"gave up on {path} {params}")


def all_markets(path, series):
    cursor, out = None, []
    while True:
        p = {"series_ticker": series, "limit": 1000}
        if cursor:
            p["cursor"] = cursor
        j = get(path, p)
        out += j.get("markets", [])
        cursor = j.get("cursor")
        if not cursor or not j.get("markets"):
            return out


series = pd.read_csv(ROOT / "data/derived/kalshi_series.csv")
series = series[series.category.isin(CATEGORIES)].ticker.tolist()
done = set(DONE.read_text().split()) if DONE.exists() else set()
n = 0
with OUT.open("a") as f, DONE.open("a") as d:
    for i, s in enumerate(series):
        if s in done:
            continue
        seen = set()
        for path in ["/historical/markets", "/markets"]:
            for m in all_markets(path, s):
                if m["ticker"] in seen:
                    continue
                seen.add(m["ticker"])
                m["series_ticker"] = s
                m["source_endpoint"] = path
                f.write(json.dumps(m) + "\n")
        n += len(seen)
        d.write(s + "\n")
        d.flush()
        if i % 50 == 0:
            print(i, len(series), s, n, flush=True)
        time.sleep(0.05)
if REFRESH:
    OUT.replace(FINAL_OUT)
    DONE.replace(FINAL_DONE)
stamp("kalshi_markets")
print("new markets written:", n)
