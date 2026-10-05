"""Build a market-level table from the raw Kalshi download and classify real-estate series.

Output: data/derived/kalshi_markets.csv
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

from common import GROUP_OF

ROOT = Path(__file__).resolve().parents[1]

def stem(ticker):
    return ticker[2:] if ticker.startswith("KX") else ticker


rows = []
with (ROOT / "data/raw/kalshi_markets.jsonl").open() as f:
    for line in f:
        m = json.loads(line)
        rows.append({
            "ticker": m["ticker"],
            "event_ticker": m.get("event_ticker"),
            "series_ticker": m["series_ticker"],
            "title": m.get("title"),
            "status": m.get("status"),
            "result": m.get("result"),
            "open_time": m.get("open_time"),
            "close_time": m.get("close_time"),
            "strike_type": m.get("strike_type"),
            "floor_strike": m.get("floor_strike"),
            "cap_strike": m.get("cap_strike"),
            "volume": float(m.get("volume_fp") or 0),
            "open_interest": float(m.get("open_interest_fp") or 0),
            "last_price": float(m.get("last_price_dollars") or np.nan),
        })
df = pd.DataFrame(rows).drop_duplicates("ticker")
for c in ["open_time", "close_time"]:
    df[c] = pd.to_datetime(df[c], utc=True, errors="coerce", format="ISO8601")
df["horizon_days"] = (df.close_time - df.open_time).dt.total_seconds() / 86400
df["re_group"] = df.series_ticker.map(lambda t: GROUP_OF.get(stem(t), "other economics"))
df["real_estate"] = df.re_group != "other economics"
df["settled"] = df.result.isin(["yes", "no"])
df.to_csv(ROOT / "data/derived/kalshi_markets.csv", index=False)

unmatched = sorted(set(GROUP_OF) - set(df.series_ticker.map(stem)))
print("curated stems with no markets:", unmatched)
print(len(df), "markets,", df.series_ticker.nunique(), "series,", df.event_ticker.nunique(), "events")
print("open_time range:", df.open_time.min(), df.open_time.max())


def summ(g):
    return pd.Series({
        "series": g.series_ticker.nunique(),
        "events": g.event_ticker.nunique(),
        "markets": len(g),
        "settled": int(g.settled.sum()),
        "share_zero_vol": (g.volume == 0).mean(),
        "vol_median": g.volume.median(),
        "vol_mean": g.volume.mean(),
        "vol_p90": g.volume.quantile(0.9),
        "vol_total_m": g.volume.sum() / 1e6,
        "horizon_median_d": g.horizon_days.median(),
        "horizon_p90_d": g.horizon_days.quantile(0.9),
        "horizon_max_d": g.horizon_days.max(),
    })


pd.set_option("display.width", 250, "display.float_format", lambda x: f"{x:,.2f}")
print(df.groupby("re_group").apply(summ, include_groups=False).to_string())
print(df.groupby("real_estate").apply(summ, include_groups=False).to_string())
