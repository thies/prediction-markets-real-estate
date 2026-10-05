#!/usr/bin/env python3
"""Rebuild the paper. With --refresh, download fresh data first.

    python3 run_all.py                 # rerun the analysis on the data on disk, rebuild the PDF
    python3 run_all.py --refresh       # update the exchange data first (about 30-60 minutes)
    python3 run_all.py --refresh --sales   # also re-download the Cook County and New York sales files
    python3 run_all.py --from-step 8   # skip earlier steps

The exchange data change daily; the property sales files change slowly and are
large, so they are refreshed only on request. After the run, read the output of
step 12: it lists qualitative claims in the prose that the new data no longer
support, and new real-estate-looking series that need classifying by hand.
"""
import argparse
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ap = argparse.ArgumentParser()
ap.add_argument("--refresh", action="store_true", help="download fresh exchange data")
ap.add_argument("--sales", action="store_true", help="with --refresh: also re-download property sales")
ap.add_argument("--from-step", type=int, default=1)
args = ap.parse_args()
py, R = [sys.executable], ["Rscript"]

# (step, what, command, kind) with kind: "fetch" = only with --refresh, "sales" = only with --refresh --sales
STEPS = [
    (1, "Kalshi series list", py + ["code/01_fetch_kalshi_series.py"], "fetch"),
    (2, "Kalshi markets", py + ["code/02_fetch_kalshi_markets.py", "--refresh"], "fetch"),
    (3, "Market panel and classification", py + ["code/03_build_market_panel.py"], "run"),
    (4, "Event liquidity regressions", py + ["code/04_event_liquidity.py"], "run"),
    (6, "Kalshi candlesticks (new markets only)", py + ["code/06_fetch_kalshi_candles.py"], "fetch"),
    (7, "Polymarket events", py + ["code/07_fetch_polymarket_re.py"], "fetch"),
    (8, "Spreads and calibration", py + ["code/08_spreads_calibration.py"], "run"),
    (9, "Cook County sales", py + ["code/09_fetch_cook_county_sales.py"], "sales"),
    (9, "New York City sales", py + ["code/09b_fetch_nyc_sales.py"], "sales"),
    (9, "Case-Shiller indices", py + ["code/09c_fetch_case_shiller.py"], "fetch"),
    (10, "Hedging test, Cook County (main)", py + ["code/10_hedging_test.py", "--warranty"], "run"),
    (10, "Hedging test, Cook County (all deeds)", py + ["code/10_hedging_test.py"], "run"),
    (10, "Hedging test, New York", py + ["code/10_hedging_test.py", "--nyc"], "run"),
    (11, "Polymarket trades and wallets", py + ["code/11_polymarket_traders.py"] + (["--refresh"] if args.refresh else []), "run"),
    (11, "Order book depth snapshot", py + ["code/13_depth_snapshot.py"], "fetch"),
    (12, "Tables", py + ["code/05_make_tables.py"], "run"),
    (12, "Figures", ["sh", "-c", "for f in figures/plot_*.R; do Rscript $f || exit 1; done; cp figures/*.png latex/figures/"], "run"),
    (12, "Numbers and claim checks", py + ["code/12_make_numbers.py"], "run"),
    (13, "PDF", ["sh", "-c", "cd latex && pdflatex -interaction=nonstopmode -halt-on-error main.tex >/dev/null && "
                 "bibtex main >/dev/null; pdflatex -interaction=nonstopmode -halt-on-error main.tex >/dev/null && "
                 "pdflatex -interaction=nonstopmode -halt-on-error main.tex | grep -E 'Output written|undefined'"], "run"),
]

for step, what, cmd, kind in STEPS:
    if step < args.from_step or (kind == "fetch" and not args.refresh) or (kind == "sales" and not (args.refresh and args.sales)):
        continue
    print(f"\n=== {step:>2}  {what}", flush=True)
    t0 = time.time()
    quiet = what not in ("Numbers and claim checks", "PDF")
    r = subprocess.run(cmd, cwd=ROOT, stdout=subprocess.PIPE if quiet else None, stderr=subprocess.STDOUT if quiet else None, text=True)
    if r.returncode != 0:
        print((r.stdout or "")[-3000:])
        sys.exit(f"step {step} ({what}) failed")
    if quiet and r.stdout:
        print("    " + r.stdout.strip().splitlines()[-1][:160])
    print(f"    {time.time() - t0:.0f}s", flush=True)
