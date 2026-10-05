"""Download New York City property sales, 2016-2025 (NYC Department of Finance annualised sales, w2pb-icbu).

Only the columns needed for repeat sales. Output: data/raw/nyc_sales.csv
"""
from io import StringIO
from pathlib import Path

import pandas as pd
import requests

from common import stamp

URL = "https://data.cityofnewyork.us/resource/w2pb-icbu.csv"
ROOT = Path(__file__).resolve().parents[1]
COLS = "bbl,borough,building_class_category,sale_price,sale_date"
PAGE = 200000

parts, offset = [], 0
while True:
    r = requests.get(URL, params={"$select": COLS, "$order": ":id", "$limit": PAGE, "$offset": offset}, timeout=600)
    r.raise_for_status()
    d = pd.read_csv(StringIO(r.text), dtype={"bbl": str})
    parts.append(d)
    print(offset, len(d), flush=True)
    if len(d) < PAGE:
        break
    offset += PAGE
df = pd.concat(parts)
df.to_csv(ROOT / "data/raw/nyc_sales.csv", index=False)
stamp("nyc_sales")
print(len(df), "rows;", df.sale_date.min(), "to", df.sale_date.max())
