# Real Estate Derivatives at Last? An Exploration of Prediction Markets

Code and LaTeX source for the paper by Thies Lindenthal (University of Cambridge). The compiled paper is `latex/main.pdf`.

The paper asks whether event contracts on prediction markets (Kalshi, Polymarket) succeed where thirty years of property derivatives did not. It is built to be re-run: no result is typed into the text. Every number in the prose is generated from the data, and the pipeline checks the qualitative claims the text makes against each new download.

## Replicating and updating

```bash
pip install -r requirements.txt        # R with ggplot2 and scales is needed for the figures; pdflatex and bibtex for the PDF
python3 run_all.py --refresh --sales   # download everything, run the analysis, build latex/main.pdf
```

`--refresh` downloads the exchange data again (30 to 60 minutes; the exchanges rate-limit). `--sales` also downloads the property sales files, which are large and change slowly. Without flags the script reruns the analysis on the data already on disk. `--from-step N` skips earlier steps.

Because the markets change, a fresh run will not reproduce the numbers of an earlier version exactly. The data date is printed on the title page of the paper. After a run, read the output of the step "Numbers and claim checks": it lists any statement in the text that the new data no longer support, and any new real-estate-looking contract series that has not been classified.

## Data

Nothing is stored in this repository. The scripts download from public sources that need no key:

| Source | Used for | Script |
|---|---|---|
| Kalshi public API | markets, volume, daily quotes, order books | `code/01`, `02`, `06`, `13` |
| Polymarket public APIs | events, trades by wallet, order books | `code/07`, `11`, `13` |
| Cook County Assessor, parcel sales (open data) | repeat sales for the hedging test | `code/09` |
| New York City Department of Finance, annualised sales (open data) | second city for the hedging test | `code/09b` |
| S&P CoreLogic Case-Shiller indices via FRED | the index the hedge is written on | `code/09c` |

Two things cannot be recovered after the fact. Neither exchange archives its order book, so `code/13_depth_snapshot.py` records depth only from the day it is first run. And Polymarket reports liquidity rewards for open contracts only.

Polymarket trades carry wallet addresses, which are public on the blockchain. The scripts keep them in the raw download and drop them from every derived file and from the paper.

## Layout

- `run_all.py` runs everything in order.
- `code/` holds one script per step, numbered. `code/common.py` has the real-estate classification of Kalshi series (`RE_GROUPS`), which is the one hand-made input. `code/12_make_numbers.py` writes every number used in the text and the claim checks.
- `figures/` holds the R scripts for the figures and their output.
- `latex/` holds the paper: `main.tex`, `references.bib`, generated `numbers.tex` and `tables/`.

The papers cited are not included.
