"""Portfolio tranche configuration.

Each entry represents a single acquisition event (devir / satın alım).
All cost/ownership data comes from the user's portfolio workbook
(Temettü & Sermaye tab source table).

Fields
------
tranche_id      : Unique identifier for the tranche.
ticker          : BIST ticker code.
acq_date        : Acquisition date (ISO YYYY-MM-DD).
acq_type        : "Devir" (carry-over) or "Satın Alım" (purchase).
own_pct         : Ownership percentage acquired in this tranche (0-1).
shares          : Number of shares acquired.
input_mode      : "UC_TRY" or "UC_USD" — which currency the unit cost
                  was originally entered in.
uc_try          : Unit cost in TRY.
uc_usd          : Unit cost in USD.
usdtry_at_acq   : USD/TRY rate on acquisition date.
cost_basis_try  : Total cost basis in TRY (shares * uc_try).
cost_basis_usd  : Total cost basis in USD (shares * uc_usd).

The data is intentionally kept as plain Python so it is trivially
editable and diff-friendly.  Helper functions below expose the data as
pandas DataFrames for downstream consumption.
"""

from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd

PORTFOLIO_TRANCHES: list[dict[str, Any]] = [
    {
        "tranche_id": "HALKB-1", "ticker": "HALKB",
        "acq_date": "2017-02-06", "acq_type": "Devir",
        "own_pct": 0.5111, "shares": 3_672_140_057,
        "input_mode": "UC_TRY", "uc_try": 1.7200, "uc_usd": 0.4562,
        "usdtry_at_acq": 3.77,
        "cost_basis_try": 6_316_080_898, "cost_basis_usd": 1_675_353_023,
    },
    {
        "tranche_id": "HALKB-2", "ticker": "HALKB",
        "acq_date": "2020-05-20", "acq_type": "Satın Alım",
        "own_pct": 0.2419, "shares": 1_737_997_808,
        "input_mode": "UC_USD", "uc_try": 6.0286, "uc_usd": 0.8600,
        "usdtry_at_acq": 7.01,
        "cost_basis_try": 10_477_693_585, "cost_basis_usd": 1_494_678_115,
    },
    {
        "tranche_id": "HALKB-3", "ticker": "HALKB",
        "acq_date": "2022-03-09", "acq_type": "Satın Alım",
        "own_pct": 0.1240, "shares": 890_912_477,
        "input_mode": "UC_USD", "uc_try": 7.4750, "uc_usd": 0.5000,
        "usdtry_at_acq": 14.95,
        "cost_basis_try": 6_659_570_766, "cost_basis_usd": 445_456_239,
    },
    {
        "tranche_id": "HALKB-4", "ticker": "HALKB",
        "acq_date": "2023-03-29", "acq_type": "Satın Alım",
        "own_pct": 0.0380, "shares": 273_021_566,
        "input_mode": "UC_USD", "uc_try": 13.1580, "uc_usd": 0.6800,
        "usdtry_at_acq": 19.35,
        "cost_basis_try": 3_592_417_765, "cost_basis_usd": 185_654_665,
    },
    {
        "tranche_id": "THYAO-1", "ticker": "THYAO",
        "acq_date": "2017-02-03", "acq_type": "Devir",
        "own_pct": 0.4912, "shares": 677_856_000,
        "input_mode": "UC_TRY", "uc_try": 5.9500, "uc_usd": 1.6081,
        "usdtry_at_acq": 3.70,
        "cost_basis_try": 4_033_243_200, "cost_basis_usd": 1_090_065_730,
    },
    {
        "tranche_id": "VAKBN-1", "ticker": "VAKBN",
        "acq_date": "2020-05-20", "acq_type": "Satın Alım",
        "own_pct": 0.3599, "shares": 3_568_740_156,
        "input_mode": "UC_USD", "uc_try": 4.4163, "uc_usd": 0.6300,
        "usdtry_at_acq": 7.01,
        "cost_basis_try": 15_760_627_151, "cost_basis_usd": 2_248_306_298,
    },
    {
        "tranche_id": "VAKBN-2", "ticker": "VAKBN",
        "acq_date": "2022-03-09", "acq_type": "Satın Alım",
        "own_pct": 0.2881, "shares": 2_856_776_990,
        "input_mode": "UC_USD", "uc_try": 3.8870, "uc_usd": 0.2600,
        "usdtry_at_acq": 14.95,
        "cost_basis_try": 11_104_292_160, "cost_basis_usd": 742_762_017,
    },
    {
        "tranche_id": "VAKBN-3", "ticker": "VAKBN",
        "acq_date": "2023-03-29", "acq_type": "Satın Alım",
        "own_pct": 0.0999, "shares": 990_600_560,
        "input_mode": "UC_USD", "uc_try": 8.1270, "uc_usd": 0.4200,
        "usdtry_at_acq": 19.35,
        "cost_basis_try": 8_050_610_751, "cost_basis_usd": 416_052_235,
    },
    {
        "tranche_id": "KRDMD-1", "ticker": "KRDMD",
        "acq_date": "2022-12-05", "acq_type": "Satın Alım",
        "own_pct": 0.0441, "shares": 50_274_000,
        "input_mode": "UC_USD", "uc_try": 14.7098, "uc_usd": 0.7900,
        "usdtry_at_acq": 18.62,
        "cost_basis_try": 739_520_485, "cost_basis_usd": 39_716_460,
    },
    {
        "tranche_id": "KAYSE-1", "ticker": "KAYSE",
        "acq_date": "2023-05-12", "acq_type": "Devir",
        "own_pct": 0.0941, "shares": 282_300_000,
        "input_mode": "UC_TRY", "uc_try": 8.8200, "uc_usd": 0.4443,
        "usdtry_at_acq": 19.85,
        "cost_basis_try": 2_489_886_000, "cost_basis_usd": 125_435_063,
    },
    {
        "tranche_id": "TCELL-1", "ticker": "TCELL",
        "acq_date": "2022-10-22", "acq_type": "Satın Alım",
        "own_pct": 0.2620, "shares": 576_400_000,
        "input_mode": "UC_USD", "uc_try": 15.7930, "uc_usd": 0.8500,
        "usdtry_at_acq": 18.58,
        "cost_basis_try": 9_103_085_200, "cost_basis_usd": 489_940_000,
    },
    {
        "tranche_id": "TURSG-1", "ticker": "TURSG",
        "acq_date": "2022-04-22", "acq_type": "Satın Alım",
        "own_pct": 0.8100, "shares": 8_100_000_000,
        "input_mode": "UC_USD", "uc_try": 7.5480, "uc_usd": 0.5100,
        "usdtry_at_acq": 14.80,
        "cost_basis_try": 61_138_800_000, "cost_basis_usd": 4_131_000_000,
    },
    {
        "tranche_id": "TTKOM-1", "ticker": "TTKOM",
        "acq_date": "2017-01-24", "acq_type": "Devir",
        "own_pct": 0.0668, "shares": 233_800_000,
        "input_mode": "UC_TRY", "uc_try": 6.5500, "uc_usd": 1.7374,
        "usdtry_at_acq": 3.77,
        "cost_basis_try": 1_531_390_000, "cost_basis_usd": 406_204_244,
    },
    {
        "tranche_id": "TTKOM-2", "ticker": "TTKOM",
        "acq_date": "2022-10-03", "acq_type": "Satın Alım",
        "own_pct": 0.5500, "shares": 1_925_000_000,
        "input_mode": "UC_USD", "uc_try": 7.9894, "uc_usd": 0.4300,
        "usdtry_at_acq": 18.58,
        "cost_basis_try": 15_379_595_000, "cost_basis_usd": 827_750_000,
    },
    {
        "tranche_id": "TRENJ-1", "ticker": "TRENJ",
        "acq_date": "2024-08-19", "acq_type": "Devir",
        "own_pct": 0.6212, "shares": 161_378_790,
        "input_mode": "UC_TRY", "uc_try": 9.2000, "uc_usd": 0.2734,
        "usdtry_at_acq": 33.65,
        "cost_basis_try": 1_484_684_868, "cost_basis_usd": 44_121_393,
    },
    {
        "tranche_id": "TRMET-1", "ticker": "TRMET",
        "acq_date": "2024-08-19", "acq_type": "Devir",
        "own_pct": 0.5225, "shares": 202_771_800,
        "input_mode": "UC_TRY", "uc_try": 11.8000, "uc_usd": 0.3507,
        "usdtry_at_acq": 33.65,
        "cost_basis_try": 2_392_707_240, "cost_basis_usd": 71_105_713,
    },
    {
        "tranche_id": "TRALT-1", "ticker": "TRALT",
        "acq_date": "2024-08-19", "acq_type": "Devir",
        "own_pct": 0.4801, "shares": 1_537_520_250,
        "input_mode": "UC_TRY", "uc_try": 3.1500, "uc_usd": 0.0936,
        "usdtry_at_acq": 33.65,
        "cost_basis_try": 4_843_188_788, "cost_basis_usd": 143_928_344,
    },
]


def get_tranches_df() -> pd.DataFrame:
    """Return all portfolio tranches as a pandas DataFrame."""
    df = pd.DataFrame(PORTFOLIO_TRANCHES)
    df["acq_date"] = pd.to_datetime(df["acq_date"])
    return df


def get_positions_df() -> pd.DataFrame:
    """Return current positions (ticker-level aggregate) across all tranches.

    Columns: ticker, shares, own_pct, cost_basis_try, cost_basis_usd,
    weighted_uc_try, weighted_uc_usd, first_acq_date.
    """
    df = get_tranches_df()
    agg = df.groupby("ticker", as_index=False).agg(
        shares=("shares", "sum"),
        own_pct=("own_pct", "sum"),
        cost_basis_try=("cost_basis_try", "sum"),
        cost_basis_usd=("cost_basis_usd", "sum"),
        first_acq_date=("acq_date", "min"),
    )
    agg["weighted_uc_try"] = agg["cost_basis_try"] / agg["shares"]
    agg["weighted_uc_usd"] = agg["cost_basis_usd"] / agg["shares"]
    return agg.sort_values("ticker").reset_index(drop=True)


def portfolio_tickers() -> list[str]:
    """Unique tickers present in the portfolio, ordered alphabetically."""
    return sorted({t["ticker"] for t in PORTFOLIO_TRANCHES})


def shares_held_on(ticker: str, on: date | str) -> float:
    """Return number of shares held in *ticker* as of *on* (inclusive).

    Tranches acquired after *on* are excluded.  Useful for computing
    historical dividend income correctly.
    """
    if isinstance(on, str):
        on = pd.to_datetime(on).date()
    elif isinstance(on, pd.Timestamp):
        on = on.date()
    total = 0.0
    for t in PORTFOLIO_TRANCHES:
        if t["ticker"] != ticker:
            continue
        acq = pd.to_datetime(t["acq_date"]).date()
        if acq <= on:
            total += t["shares"]
    return total
