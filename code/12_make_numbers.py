"""Every number quoted in the paper's prose, computed from the pipeline outputs.

Writes latex/numbers.tex (one \\newcommand per number), data/derived/numbers.json,
and a dated copy in data/snapshots/ so that later versions can show how the
markets changed. main.tex contains no hard-coded results; it uses these macros.

Also checks the qualitative claims the prose makes (signs, significance, which
of two numbers is larger). A claim that no longer holds is printed and written
to data/derived/claims_check.csv: the sentence that depends on it needs a human.
"""
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

from common import (COMMERCIAL_ADJACENT, DERIVED as D, GROUP_OF, RAW, REVIEWED_NOT_REAL_ESTATE, ROOT,
                    read_vintage, vintage)

N, CLAIMS = {}, []


def put(name, value):
    assert re.fullmatch(r"[A-Za-z]+", name) and name not in N, name
    N[name] = value


def i(x):
    return f"{int(round(x)):,}"


def claim(text, ok):
    CLAIMS.append({"claim": text, "holds": bool(ok)})


def coef(tab, spec, var, col="coef"):
    return tab[(tab.spec == spec) & (tab["var"] == var)][col].iloc[0]


def month(ts):
    return f"{ts.strftime('%B')} {ts.year}"


# ---------------------------------------------------------------- dates
v = vintage("kalshi_markets")
put("dataDate", f"{v.day} {v.strftime('%B %Y')}")
put("dataMonth", month(v))

# ---------------------------------------------------------------- Kalshi inventory
m = pd.read_csv(D / "kalshi_markets.csv")
for c in ["open_time", "close_time"]:
    m[c] = pd.to_datetime(m[c], utc=True, format="ISO8601")
re_, pr, rent = m[m.real_estate], m[m.re_group == "price"], m[m.re_group == "rent"]
put("firstOpen", month(m.open_time.min()))
put("nMarkets", i(len(m)))
put("nSeries", i(m.series_ticker.nunique()))
put("nEvents", i(m.event_ticker.nunique()))
put("reMarkets", i(len(re_)))
put("reSeries", i(re_.series_ticker.nunique()))
put("reVolM", f"{re_.volume.sum() / 1e6:.1f}")
put("totalVolM", i(m.volume.sum() / 1e6))
put("reVolShare", f"{re_.volume.sum() / m.volume.sum() * 100:.1f}")
put("priceVolM", f"{pr.volume.sum() / 1e6:.2f}")
put("priceSeries", i(pr.series_ticker.nunique()))
put("rentZeroShare", i((rent.volume == 0).mean() * 100))
put("reMaxHorizon", i(re_.horizon_days.max()))
put("priceMaxHorizon", i(pr.horizon_days.max()))
put("reMaxHorizonMonths", i(np.ceil(re_.horizon_days.max() / 30.44)))
put("reMedianVol", i(re_.volume.median()))
put("otherMedianVol", i(m[~m.real_estate].volume.median()))
by_series = m.groupby("series_ticker").volume.sum().sort_values(ascending=False)
put("topTenShare", i(by_series.head(10).sum() / by_series.sum() * 100))
put("fedVolM", i(by_series.get("KXFEDDECISION", np.nan) / 1e6))
CME_NOTIONAL_M = 612   # Shiller (2008): notional traded, May 2006 to November 2007
put("cmeRatio", i(round(CME_NOTIONAL_M / (pr.volume.sum() / 1e6), -2)))
claim("Fed decisions is the largest series by volume", by_series.index[0] == "KXFEDDECISION")
claim("CME notional is more than 100 times Kalshi house price volume", CME_NOTIONAL_M / (pr.volume.sum() / 1e6) > 100)
claim("Every real estate contract runs under two years", re_.horizon_days.max() < 730)
claim("Median real estate market trades less than the median other market",
      re_.volume.median() < m[~m.real_estate].volume.median())

# Series that look like real estate but are not classified: new contract types to review by hand.
s = pd.read_csv(D / "kalshi_series.csv")

# The whole exchange: lifetime volume by category from the series list
cat = s.groupby("category").volume.sum()
re_all = s[s.ticker.isin(set(re_.series_ticker))].volume.sum()
put("allVolBn", i(cat.sum() / 1e9))
put("sportsVolBn", i(cat["Sports"] / 1e9))
put("sportsShare", i(cat["Sports"] / cat.sum() * 100))
put("sportsToRe", thousand(cat["Sports"] / re_all) if False else i(round(cat["Sports"] / re_all, -3)))
put("reShareAll", f"{re_all / cat.sum() * 100:.3f}")
put("sportsSeriesBigger", i((s[s.category == "Sports"].volume > re_all).sum()))
claim("Series-level and market-level volume agree for economics (within 2 per cent)", abs(cat["Economics"] / m.volume.sum() - 1) < 0.02)
claim("Sports is the largest category on Kalshi and more than 1,000 times real estate", cat.idxmax() == "Sports" and cat["Sports"] > 1000 * re_all)
stem = lambda t: t[2:] if t.startswith("KX") else t
new = s[s.re_keyword & s.category.eq("Economics") & s.ticker.isin(set(m.series_ticker))
        & ~s.ticker.map(stem).isin(set(GROUP_OF) | REVIEWED_NOT_REAL_ESTATE | COMMERCIAL_ADJACENT)]
unclassified = sorted(new.ticker)

# Hotel and data centre contracts: reported, not classified as real estate
adj = m[m.series_ticker.map(stem).isin(COMMERCIAL_ADJACENT)]
put("adjSeries", i(adj.series_ticker.nunique()))
put("adjMarkets", i(len(adj)))
put("adjVol", i(round(adj.volume.sum(), -3)))
put("adjFirst", month(adj.open_time.min()))
put("adjVolShareOfRe", f"{adj.volume.sum() / re_.volume.sum() * 100:.1f}")
claim("Hotel and data centre contracts are small (under 5 per cent of real estate volume)", adj.volume.sum() < 0.05 * re_.volume.sum())

# ---------------------------------------------------------------- event regressions
ev = pd.read_csv(D / "kalshi_events.csv")
reg = pd.read_csv(D / "tab_liquidity_regression.csv")
put("regEvents", i(len(ev)))
put("regSeries", i(ev.series_ticker.nunique()))
put("regReEvents", i(ev.re.sum()))
put("regPriceEvents", i(ev.price.sum()))
put("uncondGap", i((1 - np.exp(coef(reg, "(1)", "re"))) * 100))
put("condGap", i((1 - np.exp(coef(reg, "(2)", "re"))) * 100))
put("strikeElasticity", f"{coef(reg, '(4)', 'log_strikes') + coef(reg, '(4)', 're:log_strikes'):.1f}".replace("-", "$-$"))
put("priceMedianStrikes", i(ev[ev.price == 1].strikes.median()))
put("reEventsManyStrikes", i(((ev.re == 1) & (ev.strikes > 10)).sum()))
claim("Few real estate events list more than ten strikes (under 15 per cent of them)", ((ev.re == 1) & (ev.strikes > 10)).sum() < 0.15 * ev.re.sum())
claim("Real estate events trade less with controls (p < 0.05)", coef(reg, "(2)", "re") < 0 and coef(reg, "(2)", "re", "p") < 0.05)
claim("Volume rises with horizon", coef(reg, "(2)", "log_horizon") > 0 and coef(reg, "(2)", "log_horizon", "p") < 0.05)
claim("Horizon slope is no different for real estate (p > 0.10)", coef(reg, "(3)", "re:log_horizon", "p") > 0.10)
claim("Volume per strike does not fall with strikes for other events", coef(reg, "(4)", "log_strikes") > -0.1)
claim("Volume per strike falls with strikes for real estate (p < 0.10)",
      coef(reg, "(4)", "re:log_strikes") < 0 and coef(reg, "(4)", "re:log_strikes", "p") < 0.10)
claim("Median strikes per Kalshi house price event is seven, the ladder used in the hedging test",
      ev[ev.price == 1].strikes.median() == 7)

# ---------------------------------------------------------------- quotes and accuracy
q = pd.read_csv(D / "market_quotes.csv")
qr = pd.read_csv(D / "tab_quotes_regression.csv")
a, b = q[q.re == 1], q[q.re == 0]
put("quoteMarkets", i(len(q)))
put("quoteReMarkets", i(len(a)))
put("spreadRe", i(a.spread_median.median() * 100))
put("spreadOther", i(b.spread_median.median() * 100))
put("spreadRoundTrip", i(a.spread_median.median() / 0.5 * 100))
# A phrase, not a number: the wording depends on whether the two medians coincide after rounding.
sr, so = i(a.spread_median.median() * 100), i(b.spread_median.median() * 100)
put("spreadComparison", f"{sr} cents in both groups" if sr == so else f"{sr} cents for real estate contracts and {so} cents for the others")
put("twoSidedRe", i(a.share_two_sided.mean() * 100))
put("twoSidedOther", i(b.share_two_sided.mean() * 100))
put("twoSidedGap", i(coef(qr, "(2)", "re") * 100))
put("priceDaysTraded", i(q[q.re_group == "price"].share_days_traded.mean() * 100))
put("rentDaysTraded", i(q[q.re_group == "rent"].share_days_traded.mean() * 100))
put("otherDaysTraded", i(b.share_days_traded.mean() * 100))
put("brierRe", f"{a.brier1.mean():.3f}")
put("brierOther", f"{b.brier1.mean():.3f}")
put("brierDiff", f"{coef(qr, '(3)', 're'):.3f}")
put("calSlope", f"{coef(qr, '(5)', 'p1'):.2f}")
put("priceForecastN", i(q[q.re_group == "price"].p1.notna().sum()))
claim("Spread difference is insignificant (p > 0.10)", coef(qr, "(1)", "re", "p") > 0.10)
claim("Real estate markets are quoted two-sided more often (p < 0.05)", coef(qr, "(2)", "re") > 0 and coef(qr, "(2)", "re", "p") < 0.05)
claim("House price and rent markets trade on fewer days than other markets",
      max(q[q.re_group == "price"].share_days_traded.mean(), q[q.re_group == "rent"].share_days_traded.mean()) < b.share_days_traded.mean())
claim("Raw Brier score is worse for real estate, with prices closer to 50 cents",
      a.brier1.mean() > b.brier1.mean() and a.uncertainty1.mean() > b.uncertainty1.mean())
claim("Brier difference one day out is insignificant with controls (p > 0.10)", coef(qr, "(3)", "re", "p") > 0.10)
claim("Brier difference seven days out is insignificant with controls (p > 0.10)", coef(qr, "(4)", "re", "p") > 0.10)
claim("Calibration slope does not differ for real estate (p > 0.10)", coef(qr, "(5)", "re:p1", "p") > 0.10)
claim("Calibration slope is close to one", abs(coef(qr, "(5)", "p1") - 1) < 0.15)
sb = pd.read_csv(D / "tab_spread_by_strikes.csv")
put("spreadStrikeCoef", f"{sb['coef_log_strikes'].iloc[0] * 100:.1f}".replace("-", "$-$"))
put("spreadBinMin", i(sb.median_other.min() * 100))
put("spreadBinMax", i(sb.median_other.max() * 100))
sbi = sb.set_index("bin")
put("spreadReOneStrike", i(sbi.loc["1", "median_re"] * 100))
put("spreadReManyStrikes", i(sbi.loc["11-15", "median_re"] * 100))
claim("Raw real estate spreads rise from single-strike events to events with 11-15 strikes",
      sbi.loc["11-15", "median_re"] > sbi.loc["1", "median_re"])
claim("Quoted spreads do not widen with the number of strikes", sb["coef_log_strikes"].iloc[0] <= 0.005)
claim("The spread-strike relation does not differ for real estate (p > 0.10)", sb["p_log_strikes:re"].iloc[0] > 0.10)

# ---------------------------------------------------------------- hedging
h = pd.read_csv(D / "tab_hedging_warranty.csv").set_index("holding_years")
hp = pd.read_csv(D / "tab_hedging_by_purchase_period_warranty.csv")
ny = pd.read_csv(D / "tab_hedging_nyc.csv")
ny = ny[ny.holding_years != "All"]
sales = pd.read_csv(RAW / "cook_county_sales.csv", usecols=["sale_date"])
put("cookSalesM", f"{len(sales) / 1e6:.1f}")
cv = vintage("cook_county_sales")
put("cookSalesDate", f"{cv.day} {cv.strftime('%B %Y')}")
nv, fv = vintage("nyc_sales"), vintage("case_shiller")
put("nycSalesDate", f"{nv.day} {nv.strftime('%B %Y')}")
put("caseShillerDate", f"{fv.day} {fv.strftime('%B %Y')}")
put("pairs", i(h.loc["All", "pairs"]))
put("pairProperties", i(h.loc["All", "properties"]))
put("hedgeUnderTwo", f"{max(h.loc['0.5-1', 'r2_linear'], h.loc['1-2', 'r2_linear']) * 100:.1f}")
put("hedgeTwoThree", i(h.loc["2-3", "r2_linear"] * 100))
put("hedgeThreeFive", i(h.loc["3-5", "r2_linear"] * 100))
put("hedgeFiveTen", i(h.loc["5-10", "r2_linear"] * 100))
put("hedgeTenPlus", i(h.loc["10+", "r2_linear"] * 100))
put("binaryThreeFive", i(h.loc["3-5", "r2_binary"] * 100))
put("binaryTenPlus", i(h.loc["10+", "r2_binary"] * 100))


def sub(period, bucket, col="r2_linear"):
    return hp[(hp.purchase == period) & (hp.holding_years == bucket)][col].iloc[0]


E, L = "bought 2000-2011", "bought 2012 or later"
put("earlyThreeFive", i(sub(E, "3-5") * 100))
put("earlyFiveTen", i(sub(E, "5-10") * 100))
put("lateThreeFive", i(sub(L, "3-5") * 100))
put("lateFiveTen", i(sub(L, "5-10") * 100))
put("sdIndexEarly", f"{sub(E, '5-10', 'sd_index'):.2f}")
put("sdIndexLate", f"{sub(L, '5-10', 'sd_index'):.2f}")
put("nycMaxR", f"{ny.r2_linear.max() * 100:.1f}")
rows = h.drop(index="All")
claim("Index hedge removes under 5 per cent of variance below two years", max(h.loc["0.5-1", "r2_linear"], h.loc["1-2", "r2_linear"]) < 0.05)
claim("Hedgeable share rises from two to ten years", h.loc["2-3", "r2_linear"] < h.loc["3-5", "r2_linear"] < h.loc["5-10", "r2_linear"])
claim("Seven-binary ladder matches the linear hedge at every holding period (within 3 points)",
      (rows.r2_ladder - rows.r2_linear).abs().max() < 0.03)
claim("Single binary does markedly worse beyond ten years", h.loc["10+", "r2_binary"] < 0.7 * h.loc["10+", "r2_linear"])
claim("Hedgeable share comes from the 2000s cycle: later purchases under 15 per cent, earlier above 25",
      max(sub(L, "3-5"), sub(L, "5-10")) < 0.15 and min(sub(E, "3-5"), sub(E, "5-10")) > 0.25)
claim("Index moved less for later purchases", sub(L, "5-10", "sd_index") < sub(E, "5-10", "sd_index"))
claim("New York hedge removes under 5 per cent at every holding period", ny.r2_linear.max() < 0.05)
claim("Fitted hedge ratio is negative below one year", h.loc["0.5-1", "beta"] < 0)

# ---------------------------------------------------------------- Polymarket events
pe = pd.read_csv(D / "polymarket_re_events.csv")
pp = pe[pe.group == "price"].copy()
pp["month"] = pp.start.str[:7]
put("polyEvents", i(len(pp)))
put("polyPriceVolM", f"{pp.volume_contracts.sum() / 1e6:.2f}")
put("polyLaunch", month(pd.Timestamp(pp.start.min())))
put("polyMaxHorizon", i(pp.horizon_days.max()))
put("polyBracketsMin", i(pp.markets.min()))
put("polyBracketsMax", i(pp.markets.max()))
AREAS = {"austin": "Austin", "chicago": "Chicago", "dc metro": "Washington", "dallas": "Dallas", "denver": "Denver",
         "los angeles": "Los Angeles", "la metro": "Los Angeles", "miami": "Miami", "new york": "New York",
         "san francisco": "San Francisco", "sf metro": "San Francisco", "in the us": "United States"}
area = pp.title.str.lower().map(lambda t: next((v for k, v in AREAS.items() if k in t), t))
put("polyMetros", i(area[area != "United States"].nunique()))
thousand = lambda x: i(round(x, -3))
put("polyJanMedian", thousand(pp[pp.month == "2026-01"].volume_contracts.median()))
put("polyMarJunMedian", thousand(pp[pp.month.between("2026-03", "2026-06")].volume_contracts.median()))
put("polyJulyMedian", thousand(pp[pp.month == "2026-07"].volume_contracts.median()))
put("polyMortgageEvents", i((pe.group == "mortgage rate").sum()))
put("polyOtherEvents", i((pe.group == "other real estate").sum()))
claim("Polymarket house price contracts traded exceed Kalshi's", pp.volume_contracts.sum() > pr.volume.sum())
claim("Polymarket monthly events faded after launch and the quarterly contracts traded more",
      pp[pp.month.between("2026-03", "2026-06")].volume_contracts.median() < pp[pp.month == "2026-01"].volume_contracts.median()
      < pp[pp.month == "2026-07"].volume_contracts.median())
claim("Every Polymarket house price contract runs under four months", pp.horizon_days.max() < 122)
claim("All Polymarket area names are recognised", area.isin(set(AREAS.values())).all())

# ---------------------------------------------------------------- Polymarket wallets
t = pd.read_csv(RAW / "polymarket_house_price_trades.csv")
w = pd.read_csv(D / "polymarket_wallets.csv")
top = pd.read_csv(D / "polymarket_top_wallets.csv")
ty = pd.read_csv(D / "tab_wallet_types.csv").set_index("type")
big = w[w.usd >= 10000]
bigtop = top[top.usd >= 10000]
put("polyTx", i(t.tx.nunique()))
put("polyWallets", i(len(w)))
put("polyTakerUsd", thousand((t[t.is_taker]["size"] * t[t.is_taker].price).sum()))
put("polyTakerUsdM", f"{(t[t.is_taker]['size'] * t[t.is_taker].price).sum() / 1e6:.2f}")
claim("Polymarket's volume field counts contracts: it matches taker shares in the trade file within 2 per cent",
      abs(t[t.is_taker]["size"].sum() / pp.volume_contracts.sum() - 1) < 0.02)
put("walletMedianUsd", i(w.usd.median()))
put("walletUnderHundred", i((w.usd < 100).mean() * 100))
put("walletOneMonth", i((w.months == 1).mean() * 100))
put("bigWallets", i(len(big)))
put("topTenWalletShare", i(w.share.head(10).sum() * 100))
put("mmWallets", i(ty.loc["market maker", "wallets"]))
put("mmShare", i(ty.loc["market maker", "share_usd"] * 100))
put("holdWallets", i(ty.loc["taker, directional", "wallets"]))
put("holdShare", i(ty.loc["taker, directional", "share_usd"] * 100))
put("bigHold", i((big.type == "taker, directional").sum()))
put("bigRound", i((big.type == "taker, round-trips").sum()))
put("bigMM", i((big.type == "market maker").sum()))
put("bigRestHold", i((big.type == "resting directional").sum()))
put("bigMedianMarkets", i(round(bigtop.markets_all_platform.median(), -2)))
put("bigRewarded", i((bigtop.reward_usd > 1000).sum()))
put("bigRewardedLarge", i((bigtop.reward_usd > 100000).sum()))
put("topProfiled", i(len(top)))
put("housingOnly", i((top.markets >= top.markets_all_platform).sum()))
put("topWalletShare", i(w.share.iloc[0] * 100))
put("topWalletUsd", thousand(w.usd.iloc[0]))
claim("All wallets above $10,000 were profiled", len(bigtop) == len(big))
claim("Most wallets trade under $100 and in one launch month only", (w.usd < 100).mean() > 0.5 and (w.months == 1).mean() > 0.5)
claim("Large wallets are generalists (median above 1,000 markets platform-wide)", bigtop.markets_all_platform.median() > 1000)
claim("Largest wallet is a directional taker active in one launch month", w.type.iloc[0] == "taker, directional" and w.months.iloc[0] == 1)
claim("No wallet traded as much as $1 million", w.usd.iloc[0] < 1e6)

# ---------------------------------------------------------------- hedgers and depth
hs = pd.read_csv(D / "polymarket_hedger_screen.csv")
cand = hs[(hs.usd >= 1000) & (hs.months >= 2)]
one_area = cand[cand.top_area_share >= 0.8]
like = one_area[(one_area.one_sided >= 0.8) & (one_area.net_to_gross >= 0.5)]
put("hedgerCandidates", i(len(cand)))
put("hedgerOneArea", i(len(one_area)))
put("hedgerLike", i(len(like)))
put("hedgerLikeUsd", i(round(like.usd.max(), -2)) if len(like) else "0")
put("maxNetPosition", thousand(hs.max_net_one_event.max()))
claim("Almost no repeat wallet with $1,000+ concentrates on one area (under 10 per cent of them)", len(one_area) < 0.1 * len(cand))
claim("No wallet ever held 50,000 contracts net in one event", hs.max_net_one_event.max() < 50000)

HEDGE_PAYOUT = 50000   # a 10 per cent fall on a 500,000 dollar home
dp = pd.read_csv(D / "depth_latest.csv")
dv = vintage("depth")
put("depthDate", f"{dv.day} {dv.strftime('%B %Y')}")
ev_depth = dp.groupby(["exchange", "event", "buy"])[["near", "total"]].sum().groupby(["exchange", "event"]).max()
for ex, tag in [("Kalshi", "Kalshi"), ("Polymarket", "Poly")]:
    e = ev_depth.loc[ex]
    put(f"depth{tag}Events", i(len(e)))
    put(f"depth{tag}Median", i(round(e.near.median(), -2)))
    put(f"depth{tag}Max", i(round(e.near.max(), -2)))
    put(f"depth{tag}BookMedian", i(round(e.total.median(), -2)))
put("depthMaxShare", i(ev_depth.near.max() / HEDGE_PAYOUT * 100))
put("depthMedianShare", i(ev_depth.near.median() / HEDGE_PAYOUT * 100))
for q, tag in [(100, "Hundred"), (1000, "Thousand"), (7000, "Ladder"), (50000, "Full")]:
    x = dp[f"impact_{q}"]
    put(f"fill{tag}", i(x.notna().mean() * 100))
    put(f"fillNear{tag}", i((x <= 5).mean() * 100))
    if x.notna().any():
        put(f"move{tag}", i(x.median()))
claim("A 100-contract order fills at or near the best quote on most book sides", (dp.impact_100 <= 5).mean() > 0.6)
claim("A 7,000-contract order cannot be filled within five cents on 90 per cent of book sides", (dp.impact_7000 <= 5).mean() < 0.1)
claim("No book holds 50,000 contracts on one side", dp.impact_50000.notna().sum() == 0)
claim("No open house price event has 50,000 dollars of payout within five cents of the best quote", ev_depth.near.max() < HEDGE_PAYOUT)
claim("The median open event offers under a tenth of a 50,000 dollar hedge near the quote", ev_depth.near.median() < 0.1 * HEDGE_PAYOUT)

# ---------------------------------------------------------------- write
tex = ["% Generated by code/12_make_numbers.py. Do not edit by hand."]
tex += [f"\\newcommand{{\\{k}}}{{{val}}}" for k, val in N.items()]
(ROOT / "latex/numbers.tex").write_text("\n".join(tex) + "\n")
out = {"vintage": read_vintage(), "numbers": N, "unclassified_real_estate_series": unclassified}
(D / "numbers.json").write_text(json.dumps(out, indent=1))
snap = ROOT / "data/snapshots"
snap.mkdir(exist_ok=True)
(snap / f"numbers_{v.strftime('%Y-%m-%d')}.json").write_text(json.dumps(out, indent=1))
c = pd.DataFrame(CLAIMS)
c.to_csv(D / "claims_check.csv", index=False)

print(len(N), "numbers written;", len(c), "claims checked;", int((~c.holds).sum()), "no longer hold")
for x in c[~c.holds].claim:
    print("  CLAIM FAILS:", x)
if unclassified:
    print("  Real-estate-looking series not classified in 03_build_market_panel.py:", ", ".join(unclassified))
