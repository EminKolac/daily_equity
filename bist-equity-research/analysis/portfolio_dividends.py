"""Portfolio-level dividend aggregation for the Temettü & Sermaye dashboard.

Given per-ticker raw dividend records (DPS, yield, payout ratio) and the
portfolio tranche ledger, this module produces:

1. A long-form detail table (Ticker, Year, DPS, Gross_Income_TRY,
   Net_Income_TRY, Yield, Payout_Ratio) — the bottom grid in the
   dashboard mock.

2. Ticker-level totals (Gross_Income_TRY, Net_Income_TRY) — feeds the
   horizontal stacked bar chart.

3. Yearly trend of average yield and average payout — feeds the line
   chart on the right.

4. Top-line KPIs (Total Gross, Total Net, Avg Yield, Avg Payout).

The Turkish withholding tax rate on dividend income for corporate
shareholders is currently 15 %.  When the raw feed provides both brüt
(gross) and net values we use them directly; otherwise we derive net
from gross using this default rate.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from config.portfolio import shares_held_on

logger = logging.getLogger(__name__)

DEFAULT_WITHHOLDING_RATE = 0.15


@dataclass
class DividendDashboardData:
    """Container for all data powering the Temettü & Sermaye dashboard."""

    detail: pd.DataFrame = field(default_factory=pd.DataFrame)
    by_ticker: pd.DataFrame = field(default_factory=pd.DataFrame)
    by_year: pd.DataFrame = field(default_factory=pd.DataFrame)
    kpis: dict[str, float] = field(default_factory=dict)

    def filter(
        self,
        tickers: list[str] | None = None,
        years: list[int] | None = None,
    ) -> "DividendDashboardData":
        """Return a new container filtered by ticker and/or year slicers."""
        det = self.detail
        if tickers:
            det = det[det["Ticker"].isin(tickers)]
        if years:
            det = det[det["Year"].isin(years)]
        return build_dashboard(det)


def _normalise_dividend_row(row: dict[str, Any]) -> dict[str, Any] | None:
    """Coerce one raw dividend record into a common schema.

    Supports both evofin/temettüler column names and generic English
    names.  Returns None if we cannot extract a year.
    """
    keys = {k.lower(): k for k in row.keys()}

    def _pick(*candidates: str) -> Any:
        for cand in candidates:
            if cand in keys:
                return row[keys[cand]]
        return None

    tarih = _pick("tarih", "date", "year")
    if tarih is None:
        return None
    try:
        year = pd.to_datetime(tarih).year
    except Exception:
        try:
            year = int(str(tarih)[:4])
        except Exception:
            return None

    dps = _pick("hisse_basina_temettü", "hisse_basina_temettu", "dps")
    yield_ = _pick("temettü_verimi", "temettu_verimi", "yield")
    gross = _pick("brüt_nakit_temettü", "brut_nakit_temettu",
                   "gross_cash_dividend", "total_dividend_gross")
    net = _pick("net_nakit_temettü", "net_nakit_temettu",
                 "net_cash_dividend", "total_dividend_net")
    payout = _pick("payout_ratio", "dagitim_orani", "dağıtım_oranı")

    def _f(v: Any) -> float:
        if v is None or pd.isna(v):
            return float("nan")
        try:
            return float(v)
        except (TypeError, ValueError):
            s = str(v).replace(".", "").replace(",", ".")
            try:
                return float(s)
            except ValueError:
                return float("nan")

    return {
        "Year": int(year),
        "DPS": _f(dps),
        "Yield": _f(yield_),
        "Gross_Per_Share": _f(gross),
        "Net_Per_Share": _f(net),
        "Payout_Ratio": _f(payout),
    }


def _compute_income_rows(
    ticker: str,
    records: list[dict[str, Any]] | pd.DataFrame,
) -> list[dict[str, Any]]:
    """Combine raw dividend records with the portfolio share ledger.

    For each (ticker, year) row the gross/net dividend income to the
    portfolio is  shares_held_on(year_end) * dps_gross  (or net).  When
    the raw feed already supplies per-share gross/net values we use
    them; otherwise we derive net from gross via the default
    withholding rate.
    """
    if isinstance(records, pd.DataFrame):
        raw_iter = records.to_dict(orient="records")
    else:
        raw_iter = list(records or [])

    out: list[dict[str, Any]] = []
    for raw in raw_iter:
        norm = _normalise_dividend_row(raw)
        if norm is None:
            continue

        year = norm["Year"]
        dps = norm["DPS"]
        if pd.isna(dps):
            dps = 0.0

        # Per-share gross/net:  prefer feed values, else derive.
        gross_ps = norm["Gross_Per_Share"]
        net_ps = norm["Net_Per_Share"]
        if pd.isna(gross_ps):
            gross_ps = dps
        if pd.isna(net_ps):
            net_ps = gross_ps * (1 - DEFAULT_WITHHOLDING_RATE)

        shares = shares_held_on(ticker, f"{year}-12-31")
        gross_income = gross_ps * shares
        net_income = net_ps * shares

        out.append({
            "Ticker": ticker,
            "Year": year,
            "DPS": dps,
            "Gross_Income_TRY": gross_income,
            "Net_Income_TRY": net_income,
            "Yield": norm["Yield"] if not pd.isna(norm["Yield"]) else 0.0,
            "Payout_Ratio": norm["Payout_Ratio"] if not pd.isna(norm["Payout_Ratio"]) else 0.0,
            "Shares_Held": shares,
        })
    return out


def build_dashboard(detail: pd.DataFrame) -> DividendDashboardData:
    """Derive aggregate tables + KPIs from an already-built detail frame."""
    if detail is None or detail.empty:
        return DividendDashboardData()

    detail = detail.copy()
    detail["Year"] = detail["Year"].astype(int)

    by_ticker = (
        detail.groupby("Ticker", as_index=False)
        .agg(
            Total_Div_Gross=("Gross_Income_TRY", "sum"),
            Total_Div_Net=("Net_Income_TRY", "sum"),
        )
        .sort_values("Total_Div_Gross", ascending=True)
        .reset_index(drop=True)
    )

    by_year = (
        detail.groupby("Year", as_index=False)
        .agg(
            Avg_Yield=("Yield", "mean"),
            Avg_Payout=("Payout_Ratio", "mean"),
            Total_Gross=("Gross_Income_TRY", "sum"),
            Total_Net=("Net_Income_TRY", "sum"),
        )
        .sort_values("Year")
        .reset_index(drop=True)
    )

    kpis = {
        "gross_try": float(detail["Gross_Income_TRY"].sum()),
        "net_try": float(detail["Net_Income_TRY"].sum()),
        "avg_yield": float(detail.loc[detail["Yield"] > 0, "Yield"].mean() or 0.0),
        "avg_payout": float(detail.loc[detail["Payout_Ratio"] > 0, "Payout_Ratio"].mean() or 0.0),
    }

    return DividendDashboardData(
        detail=detail.sort_values(["Ticker", "Year"]).reset_index(drop=True),
        by_ticker=by_ticker,
        by_year=by_year,
        kpis=kpis,
    )


def build_from_raw(
    dividend_feeds: dict[str, list[dict[str, Any]] | pd.DataFrame],
) -> DividendDashboardData:
    """Top-level entry point.

    *dividend_feeds* maps ticker -> list/DataFrame of raw dividend
    records (as returned by :meth:`EvofinFetcher.get_dividends`).  Any
    ticker without records contributes nothing to the dashboard.
    """
    rows: list[dict[str, Any]] = []
    for ticker, records in dividend_feeds.items():
        rows.extend(_compute_income_rows(ticker, records))

    if not rows:
        return DividendDashboardData()

    detail = pd.DataFrame(rows)
    return build_dashboard(detail)
