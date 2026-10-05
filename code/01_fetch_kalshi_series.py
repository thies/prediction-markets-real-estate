"""Download the full Kalshi series list and flag real-estate-related series.

Output: data/raw/kalshi_series.json (all series), data/derived/kalshi_series.csv
"""
import json
import re
from pathlib import Path

import pandas as pd
import requests

from common import stamp

BASE = "https://api.elections.kalshi.com/trade-api/v2"
ROOT = Path(__file__).resolve().parents[1]

RE_PATTERN = re.compile(
    r"hous|home|mortgage|rent\b|rents\b|rental|real estate|case.?shiller|zillow|redfin|"
    r"realtor|property|foreclos|housing start|building permit|reit|apartment|fhfa|"
    r"vacanc|office|construction|landlord|evict|airbnb|parcl|hotel|data cent|warehouse|occupanc|commercial prop",
    re.I,
)

# include_volume adds each series' lifetime volume in contracts, for every category
r = requests.get(f"{BASE}/series", params={"include_volume": "true"}, timeout=300)
r.raise_for_status()
series = r.json()["series"]
(ROOT / "data/raw/kalshi_series.json").write_text(json.dumps(series))
stamp("kalshi_series")

rows = []
for s in series:
    text = " ".join([s.get("title") or "", s.get("ticker") or "", " ".join(s.get("tags") or [])])
    rows.append({
        "ticker": s.get("ticker"),
        "title": s.get("title"),
        "category": s.get("category"),
        "frequency": s.get("frequency"),
        "volume": float(s.get("volume_fp") or 0),
        "tags": "|".join(s.get("tags") or []),
        "settlement_sources": "|".join(x.get("name", "") for x in (s.get("settlement_sources") or [])),
        "re_keyword": bool(RE_PATTERN.search(text)),
    })
df = pd.DataFrame(rows)
df.to_csv(ROOT / "data/derived/kalshi_series.csv", index=False)
print(len(df), "series;", df.re_keyword.sum(), "keyword hits")
print(df.category.value_counts().to_string())
pd.set_option("display.width", 250, "display.max_rows", 500, "display.max_colwidth", 70)
# New series that match a real-estate keyword but are not yet classified in 03_build_market_panel.py
# are listed by 12_make_numbers.py, so that new contract types do not go unnoticed.
