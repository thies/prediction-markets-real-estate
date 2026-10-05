"""Shared paths and the data vintage for the pipeline.

Every download script records when it last ran in data/vintage.json. Analysis
scripts read the Kalshi market vintage from there instead of hard-coding a
date, so the paper's sample window moves with the data.
"""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data/raw"
DERIVED = ROOT / "data/derived"
VINTAGE = ROOT / "data/vintage.json"


def read_vintage():
    return json.loads(VINTAGE.read_text()) if VINTAGE.exists() else {}


def stamp(source):
    """Record that `source` was downloaded now."""
    v = read_vintage()
    v[source] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    VINTAGE.write_text(json.dumps(v, indent=1, sort_keys=True))


def vintage(source):
    """Download time of `source` as a UTC timestamp."""
    return pd.Timestamp(read_vintage()[source])


def in_hash_sample(ticker, rate):
    """Deterministic sample membership. A market is in or out for good, so the
    sample stays the same across updates and grows as new markets are listed."""
    h = int(hashlib.md5(ticker.encode()).hexdigest()[:8], 16)
    return h / 0xFFFFFFFF < rate


# Hand-curated: series whose settlement statistic is a real-estate price, rent,
# financing cost, activity or credit measure. Prefix "KX" variants share a group.
RE_GROUPS = {
    "price": ["HPI", "HOMEUS", "HOMEUSY", "EXUSHOME", "USHOME", "USHOMEVAL", "NYCHOMEVAL",
              "SFHOMEVAL", "MIAHOMEVAL", "SEAHOMEVAL", "HOUHOMEVAL", "PHXHOMEVAL", "DENHOMEVAL",
              "SDHOMEVAL", "BOSHOMEVAL", "DCHOMEVAL", "NVHOMEPRICE", "RIHOMEPRICE", "UTHOMEPRICE",
              "NHHOMEPRICE", "COHPIYOY", "CAHPIYOY", "ILHPIYOY", "VANCONDO", "TORCONDO",
              "OTTAWAHOME", "CALHOME", "MTLHOME", "EDMHOME", "CANHOME"],
    "rent": ["NYCRENTSM", "NYCRENTSY", "RENTNYCM", "RENTNYCY", "SFRENTSY", "MANHATTANRENT",
             "NYCASKRENT", "MEDIANRENTHOU", "MEDIANRENTLA", "MEDIANRENTCHI", "MEDIANRENTMIA",
             "CPISHELTER", "OER", "TRUFHOUCPI"],
    "mortgage rate": ["FRM", "FRMMIN", "FRMMAX", "30YMORTW", "FM30YMTG", "MORTGAGERATE"],
    "activity": ["HOME", "NHSALES", "EHSALES", "EHSHARE", "HOUSESTART", "HOUSINGSTART",
                 "BUILDPERMS", "CABUILDPERMITS", "COBUILDPERMITS", "VTPERMITS", "BOZPERMITS",
                 "CTMFPERMITS", "CANHOUSTART", "HOUSELENGTH", "USHOMEINVENT"],
    "credit and CRE": ["MORTGAGEDEF", "CREDEF", "CREDEFMINMAX", "CREDEFMAX", "MANOFFVAC"],
}
GROUP_OF = {t: g for g, ts in RE_GROUPS.items() for t in ts}

# Series that match a real-estate keyword, were looked at, and are not real estate statistics.
# Anything matching a keyword that is in neither list is reported by 12_make_numbers.py.
REVIEWED_NOT_REAL_ESTATE = {
    "CAFAIRPLAN",      # home insurance policies in force
    "MANUCON",         # manufacturing construction spending
    "WHCA2",           # White House Correspondents' Dinner (keyword collision)
}

# Series on activity in commercial property sectors. They measure neither prices, rents nor
# returns, so they stay in the comparison group, but the paper reports their size.
COMMERCIAL_ADJACENT = {
    "DATACENTCON",     # data centre construction spending
    "USDCCAPACITY",    # operational data centre capacity
    "ORLHOTELDEMAND",  # Orlando hotel room demand
}
