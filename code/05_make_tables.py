"""Write the LaTeX tables (booktabs) from the CSV outputs of 03 and 04."""
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
T = ROOT / "latex/tables"


def stars(p):
    return "***" if p < 0.01 else "**" if p < 0.05 else "*" if p < 0.10 else ""


# Table 1: contract inventory by group
df = pd.read_csv(ROOT / "data/derived/kalshi_markets.csv")
order = ["price", "rent", "mortgage rate", "activity", "credit and CRE", "other economics"]
names = {"price": "House prices", "rent": "Rents", "mortgage rate": "Mortgage rate",
         "activity": "Housing activity", "credit and CRE": "Credit and CRE",
         "other economics": "Other economics"}
lines = []
for g in order:
    d = df[df.re_group == g]
    if g == "other economics":
        lines.append(r"\midrule")
    lines.append(f"{names[g]} & {d.series_ticker.nunique():,} & {d.event_ticker.nunique():,} & {len(d):,} & "
                 f"{d.volume.sum()/1e6:,.2f} & {d.volume.median():,.0f} & {(d.volume == 0).mean()*100:.0f} & "
                 f"{d.horizon_days.median():.0f} & {d.horizon_days.max():,.0f} \\\\")
(T / "inventory.tex").write_text("\n".join(lines) + "\n")

# Table 2: summary statistics
s = pd.read_csv(ROOT / "data/derived/tab_summary.csv", index_col=0)
lab = {"volume": "Contracts traded", "volume_per_strike": "Contracts traded per strike",
       "log_volume": "log(1 + contracts traded)", "strikes": "Strikes per event",
       "horizon_days": "Horizon (days)", "re": "Real estate event (0/1)", "price": "House price event (0/1)"}
lines = [f"{lab[v]} & {r.N:,.0f} & {r.Mean:,.2f} & {r.SD:,.2f} & {r.Min:,.2f} & {r.Median:,.2f} & {r.Max:,.2f} \\\\"
         for v, r in s.iterrows()]
(T / "summary.tex").write_text("\n".join(lines) + "\n")

# Table 3: regressions
r = pd.read_csv(ROOT / "data/derived/tab_liquidity_regression.csv")
specs = ["(1)", "(2)", "(3)", "(4)"]
vlab = {"re": "Real estate", "re:log_horizon": r"Real estate $\times$ log horizon",
        "re:log_strikes": r"Real estate $\times$ log strikes", "log_horizon": "log horizon",
        "log_strikes": "log strikes"}
lines = []
for v, l in vlab.items():
    c, se = [l], [""]
    for sp in specs:
        x = r[(r.spec == sp) & (r["var"] == v)]
        if x.empty:
            c.append(""); se.append("")
        else:
            x = x.iloc[0]
            c.append(f"{x.coef:.3f}{stars(x.p)}"); se.append(f"({x.se:.3f})")
    lines += [" & ".join(c) + r" \\", " & ".join(se) + r" \\"]
lines.append(r"\midrule")
lines.append("Quarter fixed effects & No & Yes & Yes & Yes \\\\")
for v, l, f in [("N", "Events", "{:,.0f}"), ("series", "Series (clusters)", "{:,.0f}"), ("R2", "$R^2$", "{:.3f}")]:
    lines.append(l + " & " + " & ".join(f.format(r[(r.spec == sp) & (r["var"] == v)].coef.iloc[0]) for sp in specs) + r" \\")
(T / "regression.tex").write_text("\n".join(lines) + "\n")
print(open(T / "inventory.tex").read()); print(open(T / "regression.tex").read())

# Tables 4 and 5: quotes and forecast accuracy (outputs of 08_spreads_calibration.py)
if (ROOT / "data/derived/tab_quotes_summary.csv").exists():
    s = pd.read_csv(ROOT / "data/derived/tab_quotes_summary.csv", index_col=0)
    lab = {"spread_median": "Median quoted spread", "share_two_sided": "Share of days with two-sided quote",
           "share_days_traded": "Share of days with a trade", "p1": "Price one day before close",
           "brier1": "Brier score, one day", "p7": "Price seven days before close",
           "brier7": "Brier score, seven days", "horizon_days": "Horizon (days)", "re": "Real estate market (0/1)"}
    lines = [f"{lab[v]} & {r.N:,.0f} & {r.Mean:,.3f} & {r.SD:,.3f} & {r.Min:,.3f} & {r.Median:,.3f} & {r.Max:,.3f} \\\\"
             for v, r in s.iterrows()]
    (T / "quotes_summary.tex").write_text("\n".join(lines) + "\n")

    r = pd.read_csv(ROOT / "data/derived/tab_quotes_regression.csv")
    specs = ["(1)", "(2)", "(3)", "(4)", "(5)"]
    vlab = {"re": "Real estate", "p1": "Price one day before close", "re:p1": r"Real estate $\times$ price",
            "uncertainty1": "$p(1-p)$, one day", "uncertainty7": "$p(1-p)$, seven days",
            "log_horizon": "log horizon"}
    lines = []
    for v, l in vlab.items():
        c, se = [l], [""]
        for sp in specs:
            x = r[(r.spec == sp) & (r["var"] == v)]
            if x.empty:
                c.append(""); se.append("")
            else:
                x = x.iloc[0]
                c.append(f"{x.coef:.3f}{stars(x.p)}"); se.append(f"({x.se:.3f})")
        lines += [" & ".join(c) + r" \\", " & ".join(se) + r" \\"]
    lines.append(r"\midrule")
    lines.append("Quarter fixed effects & Yes & Yes & Yes & Yes & No \\\\")
    for v, l, f in [("N", "Markets", "{:,.0f}"), ("events", "Events (clusters)", "{:,.0f}"), ("R2", "$R^2$", "{:.3f}")]:
        lines.append(l + " & " + " & ".join(f.format(r[(r.spec == sp) & (r["var"] == v)].coef.iloc[0]) for sp in specs) + r" \\")
    (T / "quotes_regression.tex").write_text("\n".join(lines) + "\n")

# Table 6: hedging effectiveness (output of 10_hedging_test.py --warranty)
if (ROOT / "data/derived/tab_hedging_warranty.csv").exists():
    h = pd.read_csv(ROOT / "data/derived/tab_hedging_warranty.csv")
    lines = []
    for r in h.itertuples():
        if r.holding_years == "All":
            lines.append(r"\midrule")
        lab = "All" if r.holding_years == "All" else r.holding_years.replace("-", "--")
        lines.append(f"{lab} & {r.pairs:,} & {r.sd_house:.3f} & {r.sd_index:.3f} & {r.beta:.2f} & "
                     f"{r.r2_linear:.3f} & {r.r2_ladder:.3f} & {r.r2_binary:.3f} \\\\")
    (T / "hedging.tex").write_text("\n".join(lines) + "\n")

# Table: Polymarket house price events by launch month
if (ROOT / "data/derived/polymarket_re_events.csv").exists():
    pe = pd.read_csv(ROOT / "data/derived/polymarket_re_events.csv")
    pe = pe[pe.group == "price"].assign(month=lambda d: d.start.str[:7])
    wallets, usd = {}, {}
    tr = ROOT / "data/raw/polymarket_house_price_trades.csv"
    if tr.exists():
        t = pd.read_csv(tr, usecols=["event_start", "wallet", "size", "price", "is_taker"])
        wallets = t.groupby(t.event_start.str[:7]).wallet.nunique().to_dict()
        tk = t[t.is_taker]
        usd = (tk["size"] * tk.price).groupby(tk.event_start.str[:7]).sum().to_dict()
    lines = []
    for mth, d in pe.groupby("month"):
        lab = pd.Timestamp(mth + "-01").strftime("%B %Y")
        lines.append(f"{lab} & {len(d)} & {d.volume_contracts.sum()/1e3:,.0f} & {d.volume_contracts.median():,.0f} & {usd.get(mth, 0)/1e3:,.0f} & "
                     f"{d.horizon_days.median():.0f} & {wallets.get(mth, 0):,} \\\\")
    (T / "polymarket_cohorts.tex").write_text("\n".join(lines) + "\n")

# ---------------------------------------------------------------- appendix tables (backup for statements in the text)
import re as _re


def tex(s):
    return _re.sub(r"([&%$#_])", r"\\\1", str(s)).replace("’", "'")


# A1: every real-estate series
mk = pd.read_csv(ROOT / "data/derived/kalshi_markets.csv")
ser = pd.read_csv(ROOT / "data/derived/kalshi_series.csv").set_index("ticker").title.to_dict()
lines = []
for g in order[:-1]:
    d = mk[mk.re_group == g]
    a = d.groupby("series_ticker").agg(events=("event_ticker", "nunique"), markets=("ticker", "size"),
                                       vol=("volume", "sum"), first=("open_time", "min"), last=("close_time", "max"))
    lines.append(f"\\multicolumn{{7}}{{l}}{{\\textit{{{names[g]}}}}} \\\\")
    for t, r in a.sort_values("vol", ascending=False).iterrows():
        title = tex(ser.get(t, ""))[:52]
        lines.append(f"\\texttt{{{tex(t)}}} & {title} & {r.events} & {r.markets} & {r.vol/1e3:,.1f} & {r['first'][:7]} & {r['last'][:7]} \\\\")
(T / "re_series.tex").write_text("\n".join(lines) + "\n")

# A2: quotes and accuracy by group
if (ROOT / "data/derived/market_quotes.csv").exists():
    q = pd.read_csv(ROOT / "data/derived/market_quotes.csv")
    lines = []
    for g in order:
        d = q[q.re_group == g]
        if g == "other economics":
            lines.append(r"\midrule")
        lines.append(f"{names[g]} & {len(d):,} & {d.share_two_sided.mean()*100:.0f} & {d.share_days_traded.mean()*100:.0f} & "
                     f"{d.spread_median.median()*100:.0f} & {d.p1.notna().sum():,} & {d.brier1.mean():.3f} & "
                     f"{d.p7.notna().sum():,} & {d.brier7.mean():.3f} \\\\")
    (T / "quotes_by_group.tex").write_text("\n".join(lines) + "\n")

# Spread by number of strikes
if (ROOT / "data/derived/tab_spread_by_strikes.csv").exists():
    sb = pd.read_csv(ROOT / "data/derived/tab_spread_by_strikes.csv").fillna(0)
    lines = [f"{str(r.bin).replace('-', '--')} & {int(r.size_other):,} & {r.median_other*100:.0f} & {int(r.size_re):,} & {r.median_re*100:.0f} \\\\"
             for r in sb.itertuples()]
    (T / "spread_by_strikes.tex").write_text("\n".join(lines) + "\n")

# A3: hedging by purchase period; A4: robustness across samples
D_ = ROOT / "data/derived"
if (D_ / "tab_hedging_by_purchase_period_warranty.csv").exists():
    hp = pd.read_csv(D_ / "tab_hedging_by_purchase_period_warranty.csv")
    lines = []
    for per, lab in [("bought 2000-2011", "Bought 2000--2011"), ("bought 2012 or later", "Bought 2012 or later")]:
        lines.append(f"\\multicolumn{{5}}{{l}}{{\\textit{{{lab}}}}} \\\\")
        for r in hp[hp.purchase == per].itertuples():
            lines.append(f"{r.holding_years.replace('-', '--')} & {r.pairs:,} & {r.sd_index:.3f} & {r.beta:.2f} & {r.r2_linear:.3f} \\\\")
    (T / "hedging_by_period.tex").write_text("\n".join(lines) + "\n")
    w_, a_, n_ = [pd.read_csv(D_ / f).set_index("holding_years") for f in
                  ("tab_hedging_warranty.csv", "tab_hedging.csv", "tab_hedging_nyc.csv")]
    lines = []
    for b in list(w_.index):
        if b == "All":
            lines.append(r"\midrule")
        ny = f"{n_.loc[b, 'pairs']:,} & {n_.loc[b, 'r2_linear']:.3f}" if b in n_.index else " & "
        lines.append(f"{b.replace('-', '--')} & {w_.loc[b, 'pairs']:,} & {w_.loc[b, 'r2_linear']:.3f} & "
                     f"{a_.loc[b, 'pairs']:,} & {a_.loc[b, 'r2_linear']:.3f} & {ny} \\\\")
    (T / "hedging_robust.tex").write_text("\n".join(lines) + "\n")

# A5: the largest Polymarket wallets (no addresses)
if (D_ / "polymarket_top_wallets.csv").exists():
    tw = pd.read_csv(D_ / "polymarket_top_wallets.csv")
    short = {"taker, directional": "Takes, holds", "taker, round-trips": "Takes, trades out",
             "market maker": "Rests, flat", "resting directional": "Rests, holds"}
    lines = [f"{r.rank} & {r.usd:,.0f} & {r.share*100:.1f} & {r.trades:,} & {r.markets} & {r.months} & {r.maker_share*100:.0f} & "
             f"{r.net_to_gross:.2f} & {short[r.type]} & {r.markets_all_platform:,} & {r.reward_usd:,.0f} \\\\" for r in tw.itertuples()]
    (T / "top_wallets.tex").write_text("\n".join(lines) + "\n")

# Depth of open house price contracts
if (D_ / "depth_latest.csv").exists():
    dp = pd.read_csv(D_ / "depth_latest.csv")
    e = dp.groupby(["exchange", "event", "buy"])[["at_best", "near", "total"]].sum().groupby(["exchange", "event"]).max()
    nm = dp.groupby("exchange").market.nunique()
    lines = [f"{ex} & {len(e.loc[ex])} & {nm[ex]} & {e.loc[ex].at_best.median():,.0f} & {e.loc[ex].near.median():,.0f} & "
             f"{e.loc[ex].near.max():,.0f} & {e.loc[ex].total.median():,.0f} & {e.loc[ex].total.max():,.0f} \\\\" for ex in ["Kalshi", "Polymarket"]]
    (T / "depth.tex").write_text("\n".join(lines) + "\n")

# Price impact of orders of increasing size
if (D_ / "depth_latest.csv").exists() and "impact_100" in pd.read_csv(D_ / "depth_latest.csv", nrows=0).columns:
    dp = pd.read_csv(D_ / "depth_latest.csv")
    lines = []
    for q in [100, 1000, 7000, 50000]:
        cells = []
        for ex in ["Kalshi", "Polymarket"]:
            x = dp[dp.exchange == ex][f"impact_{q}"]
            med = f"{x.median():.0f}" if x.notna().any() else "--"
            cells += [f"{x.notna().mean()*100:.0f}", f"{(x <= 5).mean()*100:.0f}", med]
        lines.append(f"{q:,} & " + " & ".join(cells) + " \\\\")
    (T / "price_impact.tex").write_text("\n".join(lines) + "\n")
