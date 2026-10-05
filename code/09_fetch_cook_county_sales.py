"""Download residential parcel sales for Cook County, Illinois (Chicago), 1999 to present.

Source: Cook County Assessor, "Parcel Sales" open dataset (wvhk-k5uv). Only
residential classes (2xx) and only the columns needed for repeat sales; buyer
and seller names are not downloaded.

Output: data/raw/cook_county_sales.csv
"""
from io import StringIO
from pathlib import Path

import pandas as pd
import requests

from common import stamp

URL = "https://datacatalog.cookcountyil.gov/resource/wvhk-k5uv.csv"
ROOT = Path(__file__).resolve().parents[1]
COLS = ("row_id,pin,class,township_code,nbhd,sale_date,sale_price,deed_type,is_multisale,num_parcels_sale,"
        "sale_filter_same_sale_within_365,sale_filter_less_than_10k,sale_filter_deed_type")
PAGE = 200000

parts, offset = [], 0
while True:
    r = requests.get(URL, params={"$select": COLS, "$where": "starts_with(class, '2')", "$order": "row_id",
                                  "$limit": PAGE, "$offset": offset}, timeout=600)
    r.raise_for_status()
    d = pd.read_csv(StringIO(r.text), dtype={"pin": str, "class": str, "nbhd": str, "township_code": str})
    parts.append(d)
    print(offset, len(d), flush=True)
    if len(d) < PAGE:
        break
    offset += PAGE
df = pd.concat(parts)
df.to_csv(ROOT / "data/raw/cook_county_sales.csv", index=False)
stamp("cook_county_sales")
print(len(df), "rows;", df.sale_date.min(), "to", df.sale_date.max())
