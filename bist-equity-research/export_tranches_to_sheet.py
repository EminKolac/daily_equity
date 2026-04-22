#!/usr/bin/env python3
"""Render the portfolio tranche ledger as a paste-ready TSV for the
Borsada bi' Başına "Portföy Takip" sheet.

Usage
-----
    python export_tranches_to_sheet.py            # TSV to stdout
    python export_tranches_to_sheet.py -o f.tsv   # write to file

Then open the target tab in the Google Sheet, select cell A2, paste.
Turkish locale (tr_TR) will parse the formatted numbers natively.

Target tab:
    https://docs.google.com/spreadsheets/d/1tbvgtCXtx7l8TTESpoSgofFC4GAMPhMtBeNxRy1swyE/edit?gid=968651022
"""

from __future__ import annotations

import argparse
import os
import sys

# Make the project root importable regardless of CWD.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config.portfolio import PORTFOLIO_TRANCHES

HEADERS = [
    "Tranche_ID", "Ticker", "Acq_Date", "Acq_Type", "Own_Pct", "Shares",
    "Input_Mode", "UC_TRY_Input", "UC_USD_Input", "USDTRY_at_Acq",
    "UC_TRY", "UC_USD", "Cost_Basis_TRY", "Cost_Basis_USD",
]


def _format_int_tr(n: float) -> str:
    """Whole-number formatter with `.` as thousands separator."""
    return f"{int(round(n)):,}".replace(",", ".")


def _format_dec_tr(n: float, decimals: int) -> str:
    """Decimal formatter: `,` decimal, `.` thousands, fixed precision."""
    s = f"{n:,.{decimals}f}"
    # en-US "1,234.56"  ->  tr-TR "1.234,56"
    return s.replace(",", "\x00").replace(".", ",").replace("\x00", ".")


def _format_pct_tr(ratio: float) -> str:
    """Percentage formatter: 0.5111 -> '51,11%'."""
    return _format_dec_tr(ratio * 100, 2) + "%"


def _row_to_tsv(t: dict) -> str:
    uc_try_input = (
        _format_dec_tr(t["uc_try"], 2) if t["input_mode"] == "UC_TRY" else ""
    )
    uc_usd_input = (
        _format_dec_tr(t["uc_usd"], 4) if t["input_mode"] == "UC_USD" else ""
    )

    cells = [
        t["tranche_id"],
        t["ticker"],
        t["acq_date"],
        t["acq_type"],
        _format_pct_tr(t["own_pct"]),
        _format_int_tr(t["shares"]),
        t["input_mode"],
        uc_try_input,
        uc_usd_input,
        _format_dec_tr(t["usdtry_at_acq"], 2),
        _format_dec_tr(t["uc_try"], 4),
        _format_dec_tr(t["uc_usd"], 4),
        _format_int_tr(t["cost_basis_try"]),
        _format_int_tr(t["cost_basis_usd"]),
    ]
    return "\t".join(cells)


def render_tranches_tsv() -> str:
    """Return the 18-line TSV (header + 17 tranches)."""
    lines = ["\t".join(HEADERS)]
    lines.extend(_row_to_tsv(t) for t in PORTFOLIO_TRANCHES)
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Render portfolio tranches as a paste-ready TSV.",
    )
    parser.add_argument("-o", "--output",
                        help="Write TSV to this path (default: stdout)")
    args = parser.parse_args()

    tsv = render_tranches_tsv()
    if args.output:
        with open(args.output, "w", encoding="utf-8", newline="\n") as f:
            f.write(tsv)
    else:
        sys.stdout.write(tsv)


if __name__ == "__main__":
    main()
