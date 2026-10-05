"""Collect Polymarket events on real-estate statistics through the public search endpoint.

Polymarket has no category for housing, so events are found by keyword search
and then filtered on their titles. The exchange's volume field counts contracts
(shares) traded, not dollars paid; 12_make_numbers.py checks this against the trade file.

Output: data/raw/polymarket_re_events.json, data/derived/polymarket_re_events.csv
"""
import json
import re
from pathlib import Path

import pandas as pd
import requests

from common import stamp

G = "https://gamma-api.polymarket.com"
ROOT = Path(__file__).resolve().parents[1]
QUERIES = ["housing", "home value", "home price", "house price", "mortgage", "rent", "real estate",
           "Case-Shiller", "Zillow", "home sales", "housing starts", "office vacancy", "foreclosure"]
KEEP = re.compile(r"home value|home price|house price|housing|mortgage|\brents?\b|rental|real estate|"
                  r"case.?shiller|zillow|home sales|foreclos|office vacanc|building permit", re.I)
# Keep contracts on a published statistic. Drop name collisions (GPU rental prices, a film
# title) and contracts on political acts (bills, emergencies, rent freezes, ballot measures).
DROP = re.compile(r"white house|house of|home run|\(KBH\)|earnings|speaker|senate|trump|mention|GPU|"
                  r"rotten tomatoes|mamdani|proposition|GSE-eligible", re.I)

events = {}
for q in QUERIES:
    page = 1
    while True:
        r = requests.get(G + "/public-search", params={"q": q, "limit_per_type": 50, "events_status": "all",
                                                         "page": page}, timeout=60)
        r.raise_for_status()
        j = r.json()
        for e in j.get("events") or []:
            events[e["id"]] = e
        if not (j.get("pagination") or {}).get("hasMore") or page >= 20:
            break
        page += 1
(ROOT / "data/raw/polymarket_re_events.json").write_text(json.dumps(list(events.values())))
stamp("polymarket_events")

rows = []
for e in events.values():
    t = e.get("title") or ""
    if not KEEP.search(t) or DROP.search(t):
        continue
    group = ("price" if re.search(r"home value|home price|house price|case.?shiller", t, re.I)
             else "mortgage rate" if re.search(r"mortgage (rate|average)", t, re.I)
             else "rent" if re.search(r"\brents?\b|rental", t, re.I) else "other real estate")
    rows.append({"id": e["id"], "title": t, "group": group, "start": (e.get("startDate") or "")[:10],
                 "end": (e.get("endDate") or "")[:10], "closed": bool(e.get("closed")),
                 "markets": len(e.get("markets") or []), "volume_contracts": float(e.get("volume") or 0),
                 "liquidity_usd": float(e.get("liquidity") or 0)})
df = pd.DataFrame(rows).sort_values("start")
df["horizon_days"] = (pd.to_datetime(df.end) - pd.to_datetime(df.start)).dt.days
df.to_csv(ROOT / "data/derived/polymarket_re_events.csv", index=False)
pd.set_option("display.width", 220, "display.max_rows", 300, "display.max_colwidth", 78,
              "display.float_format", lambda x: f"{x:,.0f}")
print(len(events), "events returned by search;", len(df), "kept")
pd.set_option("display.float_format", lambda x: f"{x:,.0f}")
print(df.groupby("group").agg(events=("id", "size"), markets=("markets", "sum"), volume_contracts=("volume_contracts", "sum"),
                              median_event_vol=("volume_contracts", "median"), first=("start", "min"),
                              max_horizon=("horizon_days", "max")).to_string())
df["month"] = df.start.str[:7]
print(df[df.group == "price"].groupby("month").agg(events=("id", "size"), volume_contracts=("volume_contracts", "sum"), median_horizon=("horizon_days", "median")).to_string())
print(df[df.group != "price"][["start", "end", "group", "markets", "volume_contracts", "title"]].to_string(index=False))
