"""Peer comparison / comps table builder."""

import logging
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)


def build_comps_table(
    subject_ticker: str,
    subject_metrics: dict[str, float | None],
    peer_data: list[dict[str, Any]],
) -> pd.DataFrame:
    """Build a peer comparison table.

    Args:
        subject_ticker: The ticker being analyzed
        subject_metrics: Dict with keys like pe, pb, ev_ebitda, roe, div_yield, market_cap
        peer_data: List of dicts with same keys plus 'ticker' and 'name'
    """
    rows = []

    # Subject company first
    rows.append({
        "Ticker": subject_ticker,
        "P/E": subject_metrics.get("pe"),
        "P/B": subject_metrics.get("pb"),
        "EV/EBITDA": subject_metrics.get("ev_ebitda"),
        "ROE (%)": subject_metrics.get("roe"),
        "Div. Yield (%)": subject_metrics.get("div_yield"),
        "Market Cap (mn TRY)": subject_metrics.get("market_cap"),
    })

    for peer in peer_data:
        rows.append({
            "Ticker": peer.get("ticker", ""),
            "P/E": peer.get("pe"),
            "P/B": peer.get("pb"),
            "EV/EBITDA": peer.get("ev_ebitda"),
            "ROE (%)": peer.get("roe"),
            "Div. Yield (%)": peer.get("div_yield"),
            "Market Cap (mn TRY)": peer.get("market_cap"),
        })

    df = pd.DataFrame(rows)

    # Add sector median row
    numeric_cols = ["P/E", "P/B", "EV/EBITDA", "ROE (%)", "Div. Yield (%)"]
    median_row = {"Ticker": "Sector Median"}
    for col in numeric_cols:
        vals = df[col].dropna()
        median_row[col] = round(vals.median(), 2) if len(vals) > 0 else None
    median_row["Market Cap (mn TRY)"] = None
    df = pd.concat([df, pd.DataFrame([median_row])], ignore_index=True)

    return df


def relative_performance(
    stock_prices: pd.DataFrame,
    benchmark_prices: pd.DataFrame,
    periods: dict[str, int] | None = None,
) -> dict[str, dict[str, float]]:
    """Compute relative performance over multiple periods.

    Args:
        stock_prices: DataFrame with 'Close' column
        benchmark_prices: DataFrame with 'Close' column
    """
    if periods is None:
        periods = {"1M": 21, "3M": 63, "6M": 126, "1Y": 252, "YTD": None}

    result = {}
    for label, days in periods.items():
        if days is None:
            # YTD: from start of year
            year_start = stock_prices.index[-1].replace(month=1, day=1)
            stock_slice = stock_prices[stock_prices.index >= year_start]
            bench_slice = benchmark_prices[benchmark_prices.index >= year_start]
        else:
            stock_slice = stock_prices.tail(days)
            bench_slice = benchmark_prices.tail(days)

        if stock_slice.empty or bench_slice.empty:
            result[label] = {"stock": None, "benchmark": None, "relative": None}
            continue

        stock_ret = (
            float(stock_slice["Close"].iloc[-1] / stock_slice["Close"].iloc[0] - 1) * 100
        )
        bench_ret = (
            float(bench_slice["Close"].iloc[-1] / bench_slice["Close"].iloc[0] - 1) * 100
        )
        result[label] = {
            "stock": round(stock_ret, 2),
            "benchmark": round(bench_ret, 2),
            "relative": round(stock_ret - bench_ret, 2),
        }

    return result
