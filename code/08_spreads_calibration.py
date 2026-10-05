"""Quoted spreads and forecast accuracy from daily candlesticks.

Sample: all real-estate markets and a random sample of other economics markets
listed for at least two days (see 06_fetch_kalshi_candles.py).

Output: data/derived/market_quotes.csv, calibration_bins.csv,
        tab_quotes_summary.csv, tab_quotes_regression.csv
"""
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

ROOT = Path(__file__).resolve().parents[1]
D = ROOT / "data/derived"

c = pd.read_csv(ROOT / "data/raw/kalshi_candles.csv", on_bad_lines="skip")
# Only markets in the current sample whose download completed.
done = set((ROOT / "data/raw/kalshi_candles_done.txt").read_text().split())
sample = set(pd.read_csv(D / "candle_sample.csv").ticker)
c = c[c.ticker.isin(done & sample)].drop_duplicates(["ticker", "end_ts"])
m = pd.read_csv(D / "kalshi_markets.csv")
for col in ["open_time", "close_time"]:
    m[col] = pd.to_datetime(m[col], utc=True, format="ISO8601")
c = c.merge(m[["ticker", "close_time"]], on="ticker")
c["days_to_close"] = ((c.close_time - pd.Timestamp(0, tz="UTC")).dt.total_seconds() - c.end_ts) / 86400
# A side of the book is empty when the bid is 0 or the ask is 1.
c["two_sided"] = (c.yes_bid > 0) & (c.yes_ask < 1) & (c.yes_ask > c.yes_bid)
c["spread"] = np.where(c.two_sided, c.yes_ask - c.yes_bid, np.nan)
c["mid"] = np.where(c.two_sided, (c.yes_ask + c.yes_bid) / 2, np.nan)
c["traded"] = c.volume > 0
pre = c[c.days_to_close >= 0]

q = pre.groupby("ticker").agg(days=("end_ts", "size"), share_two_sided=("two_sided", "mean"),
                              share_days_traded=("traded", "mean"), spread_median=("spread", "median")).reset_index()


def forecast(lead):
    """Last quote midpoint at least `lead` days before close; last trade price if the book is one-sided."""
    x = pre[pre.days_to_close >= lead].sort_values("end_ts").groupby("ticker").tail(1)
    p = x.mid.fillna(x.price_close)
    return pd.DataFrame({"ticker": x.ticker.values, f"p{lead}": p.values, f"spread{lead}": x.spread.values})


q = q.merge(forecast(1), on="ticker", how="left").merge(forecast(7), on="ticker", how="left")
q = q.merge(m[["ticker", "event_ticker", "series_ticker", "re_group", "real_estate", "result", "volume",
               "horizon_days", "close_time"]], on="ticker")
q = q[q.result.isin(["yes", "no"])].copy()
q["y"] = (q.result == "yes").astype(int)
q["re"] = q.real_estate.astype(int)
q["quarter"] = q.close_time.dt.tz_localize(None).dt.to_period("Q").astype(str)
q["log_horizon"] = np.log(q.horizon_days)
for lead in [1, 7]:
    q[f"brier{lead}"] = (q[f"p{lead}"] - q.y) ** 2
    q[f"uncertainty{lead}"] = q[f"p{lead}"] * (1 - q[f"p{lead}"])
q.to_csv(D / "market_quotes.csv", index=False)

pd.set_option("display.width", 220, "display.float_format", lambda x: f"{x:,.3f}")
print(len(q), "settled markets with candles;", int(q.re.sum()), "real estate")
grp = q.groupby("re_group").agg(n=("ticker", "size"), two_sided=("share_two_sided", "mean"),
                                days_traded=("share_days_traded", "mean"), spread=("spread_median", "median"),
                                spread1=("spread1", "median"), n_p1=("p1", "count"), brier1=("brier1", "mean"),
                                n_p7=("p7", "count"), brier7=("brier7", "mean"))
print(grp.to_string())
print(q.groupby("re").agg(n=("ticker", "size"), two_sided=("share_two_sided", "mean"),
                          days_traded=("share_days_traded", "mean"), spread=("spread_median", "median"),
                          brier1=("brier1", "mean"), unc1=("uncertainty1", "mean"),
                          brier7=("brier7", "mean"), unc7=("uncertainty7", "mean")).to_string())

# Calibration: realised frequency by forecast bin
bins = [0, .1, .2, .3, .4, .5, .6, .7, .8, .9, 1.0001]
cal = []
for lead in [1, 7]:
    x = q.dropna(subset=[f"p{lead}"]).copy()
    x["bin"] = pd.cut(x[f"p{lead}"], bins, right=False)
    g = x.groupby(["re", "bin"], observed=True).agg(n=("y", "size"), forecast=(f"p{lead}", "mean"),
                                                    realised=("y", "mean")).reset_index()
    g["lead"] = lead
    cal.append(g)
cal = pd.concat(cal)
cal["bin"] = cal.bin.astype(str)
cal.to_csv(D / "calibration_bins.csv", index=False)
print(cal[cal.lead == 1].to_string(index=False))

vars_ = ["spread_median", "share_two_sided", "share_days_traded", "p1", "brier1", "p7", "brier7",
         "horizon_days", "re"]
s = q[vars_].agg(["count", "mean", "std", "min", "median", "max"]).T
s.columns = ["N", "Mean", "SD", "Min", "Median", "Max"]
s.to_csv(D / "tab_quotes_summary.csv")
print(s.to_string())

specs = {
    "(1)": ("spread_median ~ re + log_horizon + C(quarter)", "spread_median"),
    "(2)": ("share_two_sided ~ re + log_horizon + C(quarter)", "share_two_sided"),
    "(3)": ("brier1 ~ re + uncertainty1 + log_horizon + C(quarter)", "brier1"),
    "(4)": ("brier7 ~ re + uncertainty7 + log_horizon + C(quarter)", "brier7"),
    "(5)": ("y ~ p1 + re + re:p1", "p1"),
}
out = []
for name, (f, need) in specs.items():
    x = q.dropna(subset=[need, "log_horizon"] + (["uncertainty7"] if "7" in need else []))
    r = smf.ols(f, x).fit(cov_type="cluster", cov_kwds={"groups": x.event_ticker})
    for v in r.params.index:
        if v.startswith("C("):
            continue
        out.append({"spec": name, "var": v, "coef": r.params[v], "se": r.bse[v], "p": r.pvalues[v]})
    out.append({"spec": name, "var": "N", "coef": r.nobs})
    out.append({"spec": name, "var": "events", "coef": x.event_ticker.nunique()})
    out.append({"spec": name, "var": "R2", "coef": r.rsquared})
res = pd.DataFrame(out)
res.to_csv(D / "tab_quotes_regression.csv", index=False)

# Does a longer ladder come with wider quotes? Spread against the number of strikes in the event.
q["strikes"] = q.event_ticker.map(m.groupby("event_ticker").size())
q["log_strikes"] = np.log(q.strikes)
x = q.dropna(subset=["spread_median", "log_horizon"])
r = smf.ols("spread_median ~ log_strikes * re + log_horizon + C(quarter)", x).fit(
    cov_type="cluster", cov_kwds={"groups": x.event_ticker})
bins = pd.cut(x.strikes, [0, 1, 3, 6, 10, 15, 1000], labels=["1", "2-3", "4-6", "7-10", "11-15", "16+"])
sb = x.groupby([bins, "re"], observed=True).spread_median.agg(["size", "median"]).unstack("re")
sb.columns = [f"{a}_{'re' if b else 'other'}" for a, b in sb.columns]
sb = sb.reset_index().rename(columns={"strikes": "bin"})
for v in ["log_strikes", "log_strikes:re"]:
    sb[f"coef_{v}"], sb[f"p_{v}"] = r.params[v], r.pvalues[v]
sb.to_csv(D / "tab_spread_by_strikes.csv", index=False)
print(sb.to_string(index=False))
print(res[res["var"] != "Intercept"].to_string(index=False))
