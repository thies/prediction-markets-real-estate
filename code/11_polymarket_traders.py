"""Who trades Polymarket's house-price contracts? Trade-level data by wallet.

Polymarket settles on a public blockchain, so every trade carries the trader's
wallet address. Wallets are pseudonymous: they identify an account, not a
person, and one person can hold several. Only the address, side, size, price
and time are stored; profile names and bios are discarded.

The trades endpoint returns the taker's side only unless takerOnly=false, in
which case each transaction has one row for the taker and one per maker whose
resting order was filled. Both versions are fetched so that each row can be
labelled taker or maker.

Output: data/raw/polymarket_house_price_trades.csv (both sides, is_taker flag),
        data/derived/polymarket_wallets.csv (one row per wallet, address dropped),
        data/derived/tab_wallet_types.csv
"""
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import requests

from common import stamp

D = "https://data-api.polymarket.com"
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/raw/polymarket_house_price_trades.csv"
TOP = 25   # wallets profiled individually


def get(path, params):
    while True:
        r = requests.get(D + path, params=params, timeout=60)
        if r.status_code == 429:
            time.sleep(3)
            continue
        return r


def fetch(taker_only):
    events = [e for e in json.loads((ROOT / "data/raw/polymarket_re_events.json").read_text())
              if "median home value" in (e.get("title") or "")]
    rows = []
    for e in events:
        for m in e.get("markets") or []:
            offset = 0
            while True:
                r = get("/trades", {"market": m["conditionId"], "limit": 500, "offset": offset,
                                    "takerOnly": "true" if taker_only else "false"})
                if r.status_code != 200:      # the API refuses offsets beyond its cap
                    print("stopped", e["title"][:50], offset, r.status_code, flush=True)
                    break
                t = r.json()
                rows += [{"event_id": e["id"], "event_start": (e.get("startDate") or "")[:10],
                          "condition_id": x["conditionId"], "tx": x["transactionHash"], "wallet": x["proxyWallet"],
                          "side": x["side"], "outcome": x.get("outcome"), "size": x["size"], "price": x["price"],
                          "timestamp": x["timestamp"]} for x in t]
                if len(t) < 500:
                    break
                offset += 500
            time.sleep(0.05)
    return pd.DataFrame(rows).drop_duplicates()


if "--refresh" in sys.argv or not OUT.exists():
    both, takers = fetch(False), fetch(True)
    key = set(zip(takers.tx, takers.wallet, takers.condition_id))
    both["is_taker"] = [k in key for k in zip(both.tx, both.wallet, both.condition_id)]
    both.to_csv(OUT, index=False)
    stamp("polymarket_trades")

t = pd.read_csv(OUT)
t["usd"] = t["size"] * t.price
t["month"] = t.event_start.str[:7]
# Exposure in "Yes" terms: buying No or selling Yes is a short position in Yes.
long_yes = ((t.side == "BUY") & (t.outcome == "Yes")) | ((t.side == "SELL") & (t.outcome == "No"))
t["signed"] = np.where(long_yes, t["size"], -t["size"])
tk = t[t.is_taker]
print(len(t), "rows;", t.tx.nunique(), "transactions;", t.wallet.nunique(), "wallets;",
      f"taker dollars ${tk.usd.sum():,.0f}; maker dollars ${t[~t.is_taker].usd.sum():,.0f}")
print("wallets that only take:", t.groupby("wallet").is_taker.all().sum(), "; only make:",
      (~t.groupby("wallet").is_taker.any()).sum())

# Per wallet and market: gross and net position in shares
pos = t.groupby(["wallet", "condition_id"]).agg(gross=("size", "sum"), net=("signed", "sum")).reset_index()
pos["abs_net"] = pos.net.abs()
w = t.groupby("wallet").agg(trades=("usd", "size"), usd=("usd", "sum"), usd_maker=("usd", lambda x: x[~t.loc[x.index, "is_taker"]].sum()),
                            events=("event_id", "nunique"), markets=("condition_id", "nunique"),
                            months=("month", "nunique")).reset_index()
w = w.merge(pos.groupby("wallet").agg(gross=("gross", "sum"), abs_net=("abs_net", "sum")).reset_index(), on="wallet")
w["maker_share"] = w.usd_maker / w.usd
w["net_to_gross"] = w.abs_net / w.gross       # 1 = every share bought was held; 0 = flat in every market
# A wallet makes markets if most of its dollars rest in the book and it ends close to flat.
w["type"] = np.select([(w.maker_share >= 0.5) & (w.net_to_gross < 0.5),
                       (w.maker_share >= 0.5), (w.net_to_gross < 0.5)],
                      ["market maker", "resting directional", "taker, round-trips"], "taker, directional")
w = w.sort_values("usd", ascending=False).reset_index(drop=True)
w["share"] = w.usd / w.usd.sum()

# Platform-wide activity of the largest wallets: markets ever traded, liquidity rewards received
top = w.head(TOP).copy()
# Profiles are cached in data/raw (with addresses) so that a rebuild without --refresh needs no network.
CACHE = ROOT / "data/raw/polymarket_wallet_profiles.csv"
prof = pd.read_csv(CACHE) if CACHE.exists() and "--refresh" not in sys.argv else pd.DataFrame(
    columns=["wallet", "markets_all_platform", "reward_payments", "reward_usd"])
extra = []
for a in top.wallet[~top.wallet.isin(prof.wallet)]:
    traded = get("/traded", {"user": a}).json().get("traded")
    rw = get("/activity", {"user": a, "type": "REWARD", "limit": 500}).json()
    extra.append({"wallet": a, "markets_all_platform": traded, "reward_payments": len(rw),
                  "reward_usd": sum(x.get("usdcSize") or 0 for x in rw)})
    time.sleep(0.1)
if extra:
    prof = pd.concat([prof, pd.DataFrame(extra)], ignore_index=True)
    prof.to_csv(CACHE, index=False)
top = top.merge(prof, on="wallet")

w.drop(columns="wallet").assign(rank=range(1, len(w) + 1)).to_csv(ROOT / "data/derived/polymarket_wallets.csv", index=False)
types = w.groupby("type").agg(wallets=("usd", "size"), usd=("usd", "sum"), median_usd=("usd", "median"),
                              median_markets=("markets", "median")).reset_index()
types["share_usd"] = types.usd / types.usd.sum()
types.to_csv(ROOT / "data/derived/tab_wallet_types.csv", index=False)

pd.set_option("display.width", 230, "display.float_format", lambda v: f"{v:,.2f}")
print(types.to_string(index=False))
big = w[w.usd >= 10000]
print(len(big), "wallets above $10,000:", big.type.value_counts().to_dict(), "; their share of dollars", round(big.share.sum(), 3))
print("volume share of top 1 / 5 / 10 / 20 wallets:", [round(w.share.head(k).sum(), 3) for k in (1, 5, 10, 20)])
print("median wallet: $", round(w.usd.median(), 2), "; under $100:", round((w.usd < 100).mean(), 3),
      "; one launch month only:", round((w.months == 1).mean(), 3))
top["rank"] = range(1, len(top) + 1)
print(top[["rank", "usd", "share", "trades", "markets", "months", "maker_share", "net_to_gross", "type",
           "markets_all_platform", "reward_payments", "reward_usd"]].to_string(index=False))
top.drop(columns="wallet").to_csv(ROOT / "data/derived/polymarket_top_wallets.csv", index=False)

# ---------------------------------------------------------------- does anyone trade like a hedger?
# A household hedging its home would trade one area, come back each time contracts are relisted,
# hold what it buys, and sit on one side of the market consensus. Each bracket's bounds are read
# from the market question; a wallet's tilt in an event is the share-weighted distance of its net
# position from the consensus mean, which is the volume-weighted price across brackets.
import re

AREAS = {"austin": "Austin", "chicago": "Chicago", "dc metro": "Washington", "dallas": "Dallas", "denver": "Denver",
         "los angeles": "Los Angeles", "la metro": "Los Angeles", "miami": "Miami", "new york": "New York",
         "nyc": "New York", "san francisco": "San Francisco", "sf metro": "San Francisco", "in the us": "United States"}
br = []
for e in json.loads((ROOT / "data/raw/polymarket_re_events.json").read_text()):
    if "median home value" not in (e.get("title") or ""):
        continue
    area = next((v for k, v in AREAS.items() if k in e["title"].lower()), e["title"])
    for mk in e.get("markets") or []:
        q = (mk.get("question") or "").lower()
        nums = [float(x.replace(",", "")) for x in re.findall(r"\$([\d,]+(?:\.\d+)?)", q)]
        if "between" in q and len(nums) == 2:
            lo, hi = nums
        elif any(k in q for k in ["less than", "below", "under"]) and nums:
            lo, hi = np.nan, nums[0]
        elif any(k in q for k in ["greater than", "more than", "above", "or more", "at least", "or higher"]) and nums:
            lo, hi = nums[0], np.nan
        else:
            continue
        br.append({"condition_id": mk["conditionId"], "event_id": int(e["id"]), "area": area, "lo": lo, "hi": hi})
br = pd.DataFrame(br)
width = (br.hi - br.lo).groupby(br.event_id).transform("median")
br["mid"] = np.where(br.lo.isna(), br.hi - width / 2, np.where(br.hi.isna(), br.lo + width / 2, (br.lo + br.hi) / 2))
h = t.merge(br[["condition_id", "area", "mid"]], on="condition_id")
h["yes_price"] = np.where(h.outcome == "Yes", h.price, 1 - h.price)
h["pw"] = h.yes_price * h["size"]
pk = h.groupby(["event_id", "condition_id", "mid"])[["pw", "size"]].sum().reset_index()
pk["p"] = pk.pw / pk["size"]
pk["p"] = pk.p / pk.groupby("event_id").p.transform("sum")
consensus = (pk.p * pk.mid).groupby(pk.event_id).sum().rename("consensus")
ps = h.groupby(["wallet", "event_id", "area", "month", "condition_id", "mid"]).agg(
    net=("signed", "sum"), gross=("size", "sum"), usd=("usd", "sum")).reset_index().join(consensus, on="event_id")
ps["tilt_num"] = ps.net * (ps.mid - ps.consensus) / ps.consensus
ps["absnet"] = ps.net.abs()
we = ps.groupby(["wallet", "event_id", "area", "month"])[["tilt_num", "absnet", "gross", "usd"]].sum().reset_index()
we["below"] = we.tilt_num < 0
area_usd = we.groupby(["wallet", "area"]).usd.sum().groupby("wallet").max()
hs = we.groupby("wallet").agg(usd=("usd", "sum"), months=("month", "nunique"), below_share=("below", "mean"),
                              absnet=("absnet", "sum"), gross=("gross", "sum"), max_net_one_event=("absnet", "max"))
hs["top_area_share"] = area_usd / hs.usd
hs["net_to_gross"] = hs.absnet / hs.gross
hs["one_sided"] = hs.below_share.map(lambda x: max(x, 1 - x))      # below consensus (owner) or above it (renter)
hs.reset_index(drop=True).to_csv(ROOT / "data/derived/polymarket_hedger_screen.csv", index=False)
cand = hs[(hs.usd >= 1000) & (hs.months >= 2)]
like = cand[(cand.top_area_share >= 0.8) & (cand.one_sided >= 0.8) & (cand.net_to_gross >= 0.5)]
print(f"hedger screen: {len(cand)} wallets with $1,000+ in 2+ launch months; {(cand.top_area_share >= 0.8).sum()} trade one area; "
      f"{len(like)} of those hold a one-sided position; largest net position in one event {hs.max_net_one_event.max():,.0f} contracts")
