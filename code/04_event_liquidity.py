"""Event-level liquidity: real-estate events against other Kalshi economics events.

An event is one settlement statistic on one date; its markets are the strikes.
Output: data/derived/kalshi_events.csv, data/derived/tab_summary.csv,
        data/derived/tab_liquidity_regression.csv
"""
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

from common import vintage

ROOT = Path(__file__).resolve().parents[1]
df = pd.read_csv(ROOT / "data/derived/kalshi_markets.csv")
for c in ["open_time", "close_time"]:
    df[c] = pd.to_datetime(df[c], utc=True, format="ISO8601")

ev = df.groupby(["event_ticker", "series_ticker", "re_group", "real_estate"]).agg(
    strikes=("ticker", "size"),
    volume=("volume", "sum"),
    open_time=("open_time", "min"),
    close_time=("close_time", "max"),
).reset_index()
ev["horizon_days"] = (ev.close_time - ev.open_time).dt.total_seconds() / 86400
# Closed events only: volume is final. Drop events with non-positive horizon.
ev = ev[(ev.close_time < vintage("kalshi_markets")) & (ev.horizon_days > 0)].copy()
ev["quarter"] = ev.close_time.dt.tz_localize(None).dt.to_period("Q").astype(str)
ev["log_volume"] = np.log1p(ev.volume)
ev["log_horizon"] = np.log(ev.horizon_days)
ev["log_strikes"] = np.log(ev.strikes)
ev["volume_per_strike"] = ev.volume / ev.strikes
ev["log_vps"] = np.log1p(ev.volume_per_strike)
ev["re"] = ev.real_estate.astype(int)
ev["price"] = (ev.re_group == "price").astype(int)
ev.to_csv(ROOT / "data/derived/kalshi_events.csv", index=False)

vars_ = ["volume", "volume_per_strike", "log_volume", "strikes", "horizon_days", "re", "price"]
summ = ev[vars_].agg(["count", "mean", "std", "min", "median", "max"]).T
summ.columns = ["N", "Mean", "SD", "Min", "Median", "Max"]
summ.to_csv(ROOT / "data/derived/tab_summary.csv")
pd.set_option("display.width", 220, "display.float_format", lambda x: f"{x:,.3f}")
print(summ.to_string())
print(ev.groupby("re_group")[["volume", "strikes", "horizon_days"]].median().to_string())

specs = {
    "(1)": "log_volume ~ re",
    "(2)": "log_volume ~ re + log_horizon + log_strikes + C(quarter)",
    "(3)": "log_volume ~ re + re:log_horizon + log_horizon + log_strikes + C(quarter)",
    "(4)": "log_vps ~ re + re:log_strikes + log_horizon + log_strikes + C(quarter)",
}
out = []
for name, f in specs.items():
    m = smf.ols(f, ev).fit(cov_type="cluster", cov_kwds={"groups": ev.series_ticker})
    for v in m.params.index:
        if v.startswith("C(") or v == "Intercept":
            continue
        out.append({"spec": name, "var": v, "coef": m.params[v], "se": m.bse[v], "p": m.pvalues[v]})
    out.append({"spec": name, "var": "N", "coef": m.nobs})
    out.append({"spec": name, "var": "R2", "coef": m.rsquared})
    out.append({"spec": name, "var": "series", "coef": ev.series_ticker.nunique()})
res = pd.DataFrame(out)
res.to_csv(ROOT / "data/derived/tab_liquidity_regression.csv", index=False)
print(res.to_string(index=False))
