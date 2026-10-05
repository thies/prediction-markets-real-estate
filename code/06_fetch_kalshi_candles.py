"""Download daily candlesticks (quotes, trade prices, volume) for a sample of Kalshi markets.

Sample: every real-estate market, plus a fixed share of other economics
markets chosen by a hash of the ticker, both restricted to markets listed for at least two days so that a
price one day before close exists. Markets settled before Kalshi's cutoff are
served by /historical/markets/{ticker}/candlesticks, the rest by
/series/{series}/markets/{ticker}/candlesticks; both are tried. Resumable.

Output: data/raw/kalshi_candles.csv, data/derived/candle_sample.csv
"""
import csv
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd
import requests

from common import in_hash_sample, stamp, vintage

BASE = "https://api.elections.kalshi.com/trade-api/v2"
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/raw/kalshi_candles.csv"
DONE = ROOT / "data/raw/kalshi_candles_done.txt"
SAMPLE_RATE = 0.26   # share of other economics markets sampled, by hash of the ticker
WORKERS = 3
FIELDS = ["ticker", "end_ts", "yes_bid", "yes_ask", "price_close", "price_mean", "volume", "open_interest"]

# Markets settled before this date are served from the historical endpoint. The date moves.
CUTOFF = pd.Timestamp(requests.get(BASE + "/historical/cutoff", timeout=60).json()["market_settled_ts"])

df = pd.read_csv(ROOT / "data/derived/kalshi_markets.csv")
for c in ["open_time", "close_time"]:
    df[c] = pd.to_datetime(df[c], utc=True, format="ISO8601")
# Closed markets only, as of the market download.
df = df[(df.horizon_days >= 2) & (df.close_time < vintage("kalshi_markets"))]
keep = df.real_estate | df.ticker.map(lambda t: in_hash_sample(t, SAMPLE_RATE))
sample = df[keep]
sample[["ticker"]].to_csv(ROOT / "data/derived/candle_sample.csv", index=False)
print(len(sample), "markets in sample;", int(sample.real_estate.sum()), "real estate", flush=True)


def pick(d, key):
    """Candle fields are named 'close' on the historical endpoint and 'close_dollars' on the live one."""
    if not d:
        return None
    return d.get(key + "_dollars", d.get(key))


def get(path, params):
    """GET with unlimited retries on rate limiting, so a throttled market is never recorded as empty."""
    wait = 1.0
    while True:
        r = requests.get(BASE + path, params=params, timeout=60)
        if r.status_code == 429 or r.status_code >= 500:
            time.sleep(wait)
            wait = min(wait * 2, 30)
            continue
        return r


def candles(row):
    p = {"start_ts": int(row.open_time.timestamp()), "end_ts": int(row.close_time.timestamp()) + 86400,
         "period_interval": 1440}
    paths = [f"/historical/markets/{row.ticker}/candlesticks",
             f"/series/{row.series_ticker}/markets/{row.ticker}/candlesticks"]
    if row.close_time >= CUTOFF:   # recent markets live on the series endpoint; try it first
        paths.reverse()
    for path in paths:
        r = get(path, p)
        if r.status_code == 200 and r.json().get("candlesticks"):
            return r.json()["candlesticks"]
    return []


def rows_for(row):
    return row.ticker, [[row.ticker, c["end_period_ts"], pick(c.get("yes_bid"), "close"),
                         pick(c.get("yes_ask"), "close"), pick(c.get("price"), "close"),
                         pick(c.get("price"), "mean"), c.get("volume_fp", c.get("volume")),
                         c.get("open_interest_fp", c.get("open_interest"))] for c in candles(row)]


done = set(DONE.read_text().split()) if DONE.exists() else set()
# An interrupted run can leave rows for markets not yet marked done, or a cut-off last line.
# Keep only complete markets before appending.
if OUT.exists():
    old = pd.read_csv(OUT, on_bad_lines="skip")
    old = old[old.ticker.isin(done)]
    old.to_csv(OUT, index=False)
    done &= set(old.ticker)       # refetch markets recorded as done without any candles
    DONE.write_text("".join(t + "\n" for t in sorted(done)))
else:
    pd.DataFrame(columns=FIELDS).to_csv(OUT, index=False)
todo = [r for r in sample.itertuples() if r.ticker not in done]
print(len(done), "already done;", len(todo), "to fetch", flush=True)
with OUT.open("a", newline="") as f, DONE.open("a") as d, ThreadPoolExecutor(WORKERS) as pool:
    w = csv.writer(f)
    for i, (ticker, rows) in enumerate(pool.map(rows_for, todo)):
        w.writerows(rows)
        d.write(ticker + "\n")
        if i % 250 == 0:
            f.flush(); d.flush()
            print(i, len(todo), flush=True)
stamp("kalshi_candles")
print("done", flush=True)
