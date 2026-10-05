"""How much house-level price risk could an index-settled contract remove? Repeat sales in Cook County (default) or New York City (--nyc).

For each repeat-sale pair the house's log price change is regressed on the
payoff of a hedge written on the S&P/Case-Shiller index for the city over the same
dates (Chicago or New York index): (a) a linear position (a future), (b) one binary contract on the index
rising, (c) a ladder of seven binary contracts. The R-squared is the share of
house-level variance the hedge removes. It is an upper bound: the hedge matches
the holding period exactly, hedge ratios are fitted in sample, and the index
is taken as final (no revision).

Output: data/derived/repeat_sales_cook.csv, data/derived/tab_hedging.csv
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SINGLE_FAMILY = {"202", "203", "204", "205", "206", "207", "208", "209", "210", "234", "278", "295"}
CONDO = {"299"}
N_STRIKES = 7
WARRANTY_ONLY = "--warranty" in sys.argv   # robustness: arm's-length warranty deeds only
TRIM = 0.05 if "--trim5" in sys.argv else 0.01
SUFFIX = ("_warranty" if WARRANTY_ONLY else "") + ("_trim5" if TRIM == 0.05 else "")
BUCKETS = [0.5, 1, 2, 3, 5, 10, 30]
LABELS = ["0.5-1", "1-2", "2-3", "3-5", "5-10", "10+"]

CITY = "nyc" if "--nyc" in sys.argv else "cook"
if CITY == "cook":
    s = pd.read_csv(ROOT / "data/raw/cook_county_sales.csv", dtype={"pin": str, "class": str},
                    parse_dates=["sale_date"])
    n0 = len(s)
    s = s[s["class"].isin(SINGLE_FAMILY | CONDO)]
    s = s[~s.is_multisale & ~s.sale_filter_same_sale_within_365 & ~s.sale_filter_less_than_10k
          & ~s.sale_filter_deed_type & (s.sale_price >= 10000) & (s.sale_date >= "2000-01-01")]
    if WARRANTY_ONLY:
        s = s[s.deed_type == "Warranty"]
    s["condo"] = s["class"].isin(CONDO)
    INDEX_FILE = "case_shiller_chicago_CHXRNSA.csv"
else:
    # New York City: one- to three-family houses and residential condominium units. Co-operative
    # apartments share a tax lot and cannot be tracked across sales, so they are left out.
    s = pd.read_csv(ROOT / "data/raw/nyc_sales.csv", dtype={"bbl": str}, parse_dates=["sale_date"])
    n0 = len(s)
    cat = s.building_class_category.str.extract(r"^(\d\d)")[0]
    s = s[cat.isin(["01", "02", "03", "04", "12", "13", "15"]) & (s.sale_price >= 10000)].copy()
    s["condo"] = cat.loc[s.index].isin(["04", "12", "13", "15"])
    s = s.rename(columns={"bbl": "pin"})
    INDEX_FILE = "case_shiller_newyork_NYXRNSA.csv"
    SUFFIX = "_nyc" + SUFFIX
s = s.sort_values(["pin", "sale_date"]).drop_duplicates(["pin", "sale_date"])
print(n0, "sales downloaded;", len(s), "after filters")

idx = pd.read_csv(ROOT / "data/raw" / INDEX_FILE, parse_dates=["observation_date"])
idx = idx.set_index(idx.observation_date.dt.to_period("M")).iloc[:, 1]
s["ym"] = s.sale_date.dt.to_period("M")
s["log_index"] = np.log(s.ym.map(idx))
s["log_price"] = np.log(s.sale_price)

g = s.groupby("pin")
p = pd.DataFrame({
    "pin": s.pin, "condo": s.condo, "date2": s.sale_date, "date1": g.sale_date.shift(),
    "r_house": s.log_price - g.log_price.shift(), "r_index": s.log_index - g.log_index.shift(),
}).dropna()
p["years"] = (p.date2 - p.date1).dt.days / 365.25
p = p[p.years >= 0.5]
p["bucket"] = pd.cut(p.years, BUCKETS, labels=LABELS, right=False)
# Trim the tails (1 per cent by default) of annualised returns within each bucket: flips after
# renovation and distressed sales are not price risk an index could hedge.
ann = p.r_house / p.years
lo, hi = ann.groupby(p.bucket, observed=True).transform(lambda x: x.quantile(TRIM)), \
         ann.groupby(p.bucket, observed=True).transform(lambda x: x.quantile(1 - TRIM))
p = p[(ann >= lo) & (ann <= hi)]
if not SUFFIX:
    p.to_csv(ROOT / "data/derived/repeat_sales_cook.csv", index=False)
print(len(p), "repeat-sale pairs;", p.pin.nunique(), "properties;", p.date1.min().date(), "to", p.date2.max().date())


def r2(y, X):
    X = np.column_stack([np.ones(len(y)), X])
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    return 1 - ((y - X @ beta) ** 2).sum() / ((y - y.mean()) ** 2).sum()


def ladder(r_index, n):
    """Payoffs of n binary contracts with strikes at evenly spaced quantiles of the index change."""
    strikes = np.quantile(r_index, np.arange(1, n + 1) / (n + 1))
    return np.column_stack([(r_index > k).astype(float) for k in np.unique(strikes)])


rows = []
for name, d in [(b, p[p.bucket == b]) for b in LABELS if (p.bucket == b).sum() > 100] + [("All", p)]:
    y, x = d.r_house.values, d.r_index.values
    rows.append({"holding_years": name, "pairs": len(d), "properties": d.pin.nunique(), "sd_house": y.std(), "sd_index": x.std(),
                 "beta": np.polyfit(x, y, 1)[0], "r2_linear": r2(y, x),
                 "r2_binary": r2(y, (x > 0).astype(float)), "r2_ladder": r2(y, ladder(x, N_STRIKES))})
out = pd.DataFrame(rows)
out.to_csv(ROOT / f"data/derived/tab_hedging{SUFFIX}.csv", index=False)
pd.set_option("display.width", 200, "display.float_format", lambda v: f"{v:,.3f}")
print(out.to_string(index=False))

# The same linear hedge split by purchase date: holding periods that span the 2000s boom and
# bust against those that start after it.
if CITY == "cook":
    sub = []
    for label, d in [("bought 2000-2011", p[p.date1 < "2012-01-01"]), ("bought 2012 or later", p[p.date1 >= "2012-01-01"])]:
        for b in LABELS[:-1]:
            q = d[d.bucket == b]
            sub.append({"purchase": label, "holding_years": b, "pairs": len(q), "sd_index": q.r_index.std(),
                        "beta": np.polyfit(q.r_index, q.r_house, 1)[0], "r2_linear": r2(q.r_house.values, q.r_index.values)})
    sub = pd.DataFrame(sub)
    sub.to_csv(ROOT / f"data/derived/tab_hedging_by_purchase_period{SUFFIX}.csv", index=False)
    print(sub.to_string(index=False))
