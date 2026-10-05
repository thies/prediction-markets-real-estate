"""Snapshot of the live order books of open house-price contracts on Kalshi and Polymarket.

Neither exchange archives its order book, so depth can only be recorded going
forward. Each run appends one dated snapshot to data/snapshots/depth.csv.

For each market and side: contracts resting at the best price, within five
cents of it, and in the whole book. A contract pays one dollar, so contracts
are also the dollars of payout a trader could buy at those prices.

Kalshi lists bids only. Buying No at price q is filled by a resting Yes bid at
1 - q, so the Yes bids are what a buyer of No can trade against, and vice versa.

Output: data/snapshots/depth.csv (appended), data/derived/depth_latest.csv
"""
import json
import time
from datetime import datetime, timezone

import pandas as pd
import requests

from common import DERIVED, RAW, ROOT, stamp

KALSHI = "https://api.elections.kalshi.com/trade-api/v2"
CLOB = "https://clob.polymarket.com"
NEAR = 0.05
now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def get(url, params=None):
    while True:
        r = requests.get(url, params=params, timeout=60)
        if r.status_code == 429:
            time.sleep(2)
            continue
        return r


SIZES = [100, 1000, 7000, 50000]   # contracts; 7,000 per strike is a 50,000 dollar hedge over seven strikes


def side_depth(levels, best_is_max=True):
    """levels: list of (price, size) resting orders on one side, as a buyer on the other side meets them.

    Besides depth, returns for each order size the number of cents the price moves against the buyer
    from the best quote to the last contract filled (impact_*), or None if the book cannot fill it.
    """
    lv = [(float(p), float(s)) for p, s in levels if float(s) > 0]
    if not lv:
        return dict(best=None, at_best=0.0, near=0.0, total=0.0, **{f"impact_{q}": None for q in SIZES})
    best = max(p for p, _ in lv) if best_is_max else min(p for p, _ in lv)
    out = dict(best=best, at_best=sum(s for p, s in lv if p == best),
               near=sum(s for p, s in lv if abs(p - best) <= NEAR + 1e-9), total=sum(s for _, s in lv))
    walk = sorted(lv, key=lambda x: abs(x[0] - best))     # best price first
    for q in SIZES:
        filled, last = 0.0, None
        for price, size in walk:
            filled += size
            if filled >= q:
                last = price
                break
        out[f"impact_{q}"] = None if last is None else round(abs(last - best) * 100, 2)
    return out


rows = []

# ---- Kalshi: open markets in the house price group
m = pd.read_csv(DERIVED / "kalshi_markets.csv")
for r in m[(m.re_group == "price") & m.status.isin(["active", "open"])].itertuples():
    ob = get(f"{KALSHI}/markets/{r.ticker}/orderbook").json().get("orderbook_fp") or {}
    mk = get(f"{KALSHI}/markets/{r.ticker}").json().get("market") or {}
    yes_bids, no_bids = side_depth(ob.get("yes_dollars") or []), side_depth(ob.get("no_dollars") or [])
    for buy, d in [("no", yes_bids), ("yes", no_bids)]:      # what a buyer of `buy` can trade against
        rows.append(dict(snapshot=now, exchange="Kalshi", event=r.event_ticker, market=r.ticker, title=r.title,
                         buy=buy, price=None if d["best"] is None else round(1 - d["best"], 4),
                         at_best=d["at_best"], near=d["near"], total=d["total"],
                         open_interest=float(mk.get("open_interest_fp") or 0),
                         **{k: v for k, v in d.items() if k.startswith("impact_")}))
    time.sleep(0.15)

# ---- Polymarket: open house price events
events = [e for e in json.loads((RAW / "polymarket_re_events.json").read_text())
          if "median home value" in (e.get("title") or "") and not e.get("closed")]
for e in events:
    for mk in e.get("markets") or []:
        if mk.get("closed"):
            continue
        tokens = json.loads(mk.get("clobTokenIds") or "[]")
        for outcome, tok in zip(["yes", "no"], tokens):
            b = get(f"{CLOB}/book", {"token_id": tok})
            if b.status_code != 200:
                continue
            asks = side_depth([(a["price"], a["size"]) for a in b.json().get("asks") or []], best_is_max=False)
            rows.append(dict(snapshot=now, exchange="Polymarket", event=e.get("title"), market=mk.get("conditionId"),
                             title=mk.get("question"), buy=outcome, price=asks["best"], at_best=asks["at_best"],
                             near=asks["near"], total=asks["total"], open_interest=None,
                             **{k: v for k, v in asks.items() if k.startswith("impact_")}))
            time.sleep(0.05)

d = pd.DataFrame(rows)
d.to_csv(DERIVED / "depth_latest.csv", index=False)
out = ROOT / "data/snapshots/depth.csv"
if out.exists() and list(pd.read_csv(out, nrows=0).columns) != list(d.columns):
    d = pd.concat([pd.read_csv(out), d], ignore_index=True)      # columns were added: rewrite with the union
    d.to_csv(out, index=False)
    d = d[d.snapshot == now]
else:
    d.to_csv(out, mode="a", header=not out.exists(), index=False)
stamp("depth")

pd.set_option("display.width", 220, "display.max_colwidth", 60, "display.float_format", lambda x: f"{x:,.0f}")
print(len(d), "book sides;", d.market.nunique(), "markets")
# Per event: payout a trader could buy across all strikes, summing the larger of the two sides per market is
# not meaningful, so report each side.
g = d.groupby(["exchange", "event", "buy"]).agg(markets=("market", "nunique"), at_best=("at_best", "sum"),
                                                 near=("near", "sum"), total=("total", "sum")).reset_index()
print(g.to_string(index=False))
print(d.groupby(["exchange", "buy"])[["at_best", "near", "total"]].describe().loc[:, (slice(None), ["50%", "max"])].to_string())

# Price impact: share of book sides that can fill an order of each size, and the move in cents where they can
for q in SIZES:
    x = d[f"impact_{q}"]
    print(f"{q:>6} contracts: fillable on {x.notna().mean()*100:.0f}% of book sides; median move where fillable "
          f"{x.median():.0f} cents; fillable within 5 cents on {(x <= 5).mean()*100:.0f}%")
