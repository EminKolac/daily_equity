#!/usr/bin/env python3
"""CLI to generate the Temettü & Sermaye portfolio dashboard.

Usage
-----
Generate a dashboard for the full portfolio using whatever dividend
data is available locally (Yahoo Finance by default; evofin MCP data
if already cached):

    python dividend_dashboard_cli.py

Restrict to specific tickers / years:

    python dividend_dashboard_cli.py --tickers HALKB VAKBN --years 2024 2025

Provide a CSV with manual dividend history — overrides all other
sources.  The CSV must have columns: Ticker, Year, DPS, Yield,
Payout_Ratio (Yield and Payout_Ratio as decimals, e.g. 0.03 for 3%).

    python dividend_dashboard_cli.py --csv data/dividends_manual.csv

Output defaults to ``reports/temettu_sermaye_dashboard_YYYYMMDD.pdf``.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from datetime import datetime

# Make the project root importable regardless of CWD.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pandas as pd

from analysis.portfolio_dividends import DividendDashboardData, build_from_raw
from config.portfolio import portfolio_tickers
from config.settings import REPORT_OUTPUT_DIR
from report.dividend_dashboard import build_dividend_dashboard_pdf

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("dividend_dashboard_cli")


def _load_from_csv(path: str) -> DividendDashboardData:
    df = pd.read_csv(path)
    required = {"Ticker", "Year"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"CSV missing required columns: {missing}")
    feeds: dict[str, list[dict]] = {}
    for ticker, grp in df.groupby("Ticker"):
        feeds[ticker] = [
            {
                "tarih": f"{int(r.Year)}-12-31",
                "hisse_basina_temettü": getattr(r, "DPS", None),
                "temettü_verimi": getattr(r, "Yield", None),
                "payout_ratio": getattr(r, "Payout_Ratio", None),
                "brüt_nakit_temettü": getattr(r, "Gross_Per_Share", getattr(r, "DPS", None)),
                "net_nakit_temettü": getattr(r, "Net_Per_Share", None),
            }
            for r in grp.itertuples(index=False)
        ]
    return build_from_raw(feeds)


def _load_from_yahoo(tickers: list[str]) -> DividendDashboardData:
    from data.fetchers.yahoo_fetcher import YahooFetcher

    fetcher = YahooFetcher()
    feeds: dict[str, pd.DataFrame] = {}
    for tk in tickers:
        divs = fetcher.get_dividends(tk)
        if divs is None or divs.empty:
            logger.info("No Yahoo dividend data for %s", tk)
            continue
        # Yahoo returns a two-column frame: Date, Dividends.
        divs = divs.rename(columns={"Date": "tarih", "Dividends": "hisse_basina_temettü"})
        # Aggregate per year (Yahoo emits one row per distribution).
        divs["year"] = pd.to_datetime(divs["tarih"]).dt.year
        annual = (
            divs.groupby("year", as_index=False)["hisse_basina_temettü"].sum()
        )
        annual["tarih"] = annual["year"].apply(lambda y: f"{int(y)}-12-31")
        feeds[tk] = annual[["tarih", "hisse_basina_temettü"]]
    return build_from_raw(feeds)


async def _load_from_evofin(tickers: list[str]) -> DividendDashboardData:
    from data.fetchers.evofin_fetcher import EvofinFetcher

    fetcher = EvofinFetcher()
    feeds: dict[str, pd.DataFrame] = {}
    for tk in tickers:
        try:
            divs = await fetcher.get_dividends(tk)
        except Exception as e:
            logger.warning("Evofin dividend fetch failed for %s: %s", tk, e)
            continue
        if divs is None or divs.empty:
            logger.info("No Evofin dividend data for %s", tk)
            continue
        feeds[tk] = divs
    return build_from_raw(feeds)


def main() -> None:
    parser = argparse.ArgumentParser(description="Temettü & Sermaye portfolio dashboard")
    parser.add_argument("--tickers", nargs="+",
                        help="Restrict to a subset of portfolio tickers")
    parser.add_argument("--years", nargs="+", type=int,
                        help="Restrict to a subset of years")
    parser.add_argument("--source", choices=["auto", "yahoo", "evofin", "csv"],
                        default="auto",
                        help="Dividend data source (default: auto)")
    parser.add_argument("--csv", help="Manual dividend history CSV "
                                       "(Ticker, Year, DPS, Yield, Payout_Ratio)")
    parser.add_argument("--output", "-o", help="Output PDF path")
    args = parser.parse_args()

    tickers = args.tickers or portfolio_tickers()
    logger.info("Building dashboard for %d tickers: %s", len(tickers), ", ".join(tickers))

    data: DividendDashboardData
    if args.source == "csv" or (args.source == "auto" and args.csv):
        if not args.csv:
            parser.error("--csv PATH is required when --source=csv")
        logger.info("Loading dividend history from CSV: %s", args.csv)
        data = _load_from_csv(args.csv)
    elif args.source == "evofin":
        logger.info("Loading dividend history from evofin (MCP)")
        data = asyncio.run(_load_from_evofin(tickers))
    elif args.source == "yahoo":
        logger.info("Loading dividend history from Yahoo Finance")
        data = _load_from_yahoo(tickers)
    else:  # auto
        logger.info("Loading dividend history (auto: Yahoo)")
        data = _load_from_yahoo(tickers)

    if data.detail.empty:
        logger.warning("No dividend records found — dashboard will show empty panels")

    pdf_bytes = build_dividend_dashboard_pdf(
        data,
        tickers_slicer=args.tickers,
        years_slicer=args.years,
    )

    os.makedirs(REPORT_OUTPUT_DIR, exist_ok=True)
    output = args.output or os.path.join(
        REPORT_OUTPUT_DIR,
        f"temettu_sermaye_dashboard_{datetime.now():%Y%m%d}.pdf",
    )
    with open(output, "wb") as f:
        f.write(pdf_bytes)

    logger.info("Dashboard saved: %s (%d bytes)", output, len(pdf_bytes))
    print(output)


if __name__ == "__main__":
    main()
