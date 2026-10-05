"""Download the S&P/Case-Shiller indices used in the hedging test from FRED (no key needed).

Output: data/raw/case_shiller_chicago_CHXRNSA.csv, data/raw/case_shiller_newyork_NYXRNSA.csv
"""
import requests

from common import RAW, stamp

for city, series in [("chicago", "CHXRNSA"), ("newyork", "NYXRNSA")]:
    r = requests.get("https://fred.stlouisfed.org/graph/fredgraph.csv", params={"id": series}, timeout=120)
    r.raise_for_status()
    assert r.text.startswith("observation_date"), r.text[:100]
    (RAW / f"case_shiller_{city}_{series}.csv").write_text(r.text)
    print(series, r.text.strip().splitlines()[-1])
stamp("case_shiller")
