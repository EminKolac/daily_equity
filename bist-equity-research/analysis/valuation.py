"""Valuation models: DCF, DDM, relative valuation, football field."""

import logging
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def dcf_valuation(
    fcf_last: float,
    growth_rate_5y: float,
    terminal_growth: float = 0.03,
    wacc: float = 0.15,
    shares_outstanding: float = 1.0,
    projection_years: int = 5,
) -> dict[str, Any]:
    """Simplified DCF model."""
    if wacc <= terminal_growth:
        terminal_growth = wacc - 0.02

    projected_fcf = []
    fcf = fcf_last
    for year in range(1, projection_years + 1):
        fcf = fcf * (1 + growth_rate_5y)
        projected_fcf.append(fcf)

    # Terminal value (Gordon growth)
    terminal_value = projected_fcf[-1] * (1 + terminal_growth) / (wacc - terminal_growth)

    # Discount back
    pv_fcfs = sum(
        cf / (1 + wacc) ** i for i, cf in enumerate(projected_fcf, 1)
    )
    pv_terminal = terminal_value / (1 + wacc) ** projection_years
    enterprise_value = pv_fcfs + pv_terminal
    equity_value_per_share = enterprise_value / shares_outstanding if shares_outstanding else 0

    return {
        "fair_value": round(equity_value_per_share, 2),
        "enterprise_value": round(enterprise_value, 2),
        "pv_fcfs": round(pv_fcfs, 2),
        "pv_terminal": round(pv_terminal, 2),
        "terminal_value": round(terminal_value, 2),
        "assumptions": {
            "fcf_last": fcf_last,
            "growth_rate_5y": growth_rate_5y,
            "terminal_growth": terminal_growth,
            "wacc": wacc,
            "projection_years": projection_years,
        },
        "projected_fcf": [round(f, 2) for f in projected_fcf],
    }


def dcf_sensitivity(
    fcf_last: float,
    shares_outstanding: float,
    wacc_range: list[float] | None = None,
    growth_range: list[float] | None = None,
) -> pd.DataFrame:
    """WACC vs terminal growth sensitivity table."""
    if wacc_range is None:
        wacc_range = [0.10, 0.12, 0.14, 0.16, 0.18]
    if growth_range is None:
        growth_range = [0.01, 0.02, 0.03, 0.04, 0.05]

    matrix = {}
    for tg in growth_range:
        row = {}
        for w in wacc_range:
            result = dcf_valuation(
                fcf_last=fcf_last,
                growth_rate_5y=0.10,
                terminal_growth=tg,
                wacc=w,
                shares_outstanding=shares_outstanding,
            )
            row[f"WACC {w:.0%}"] = result["fair_value"]
        matrix[f"g={tg:.0%}"] = row
    return pd.DataFrame(matrix).T


def ddm_valuation(
    dps_last: float,
    dps_growth: float = 0.05,
    cost_of_equity: float = 0.15,
) -> dict[str, Any]:
    """Gordon Growth / Dividend Discount Model."""
    if cost_of_equity <= dps_growth:
        return {"fair_value": None, "error": "Cost of equity must exceed growth rate"}

    fair_value = dps_last * (1 + dps_growth) / (cost_of_equity - dps_growth)
    return {
        "fair_value": round(fair_value, 2),
        "assumptions": {
            "dps_last": dps_last,
            "dps_growth": dps_growth,
            "cost_of_equity": cost_of_equity,
        },
    }


def relative_valuation(
    company_ratios: dict[str, float],
    sector_medians: dict[str, float],
    historical_averages: dict[str, float],
) -> dict[str, Any]:
    """Compare P/E, P/B, EV/EBITDA vs sector and history."""
    result = {}
    for metric in ["pe", "pb", "ev_ebitda"]:
        comp_val = company_ratios.get(metric)
        sect_val = sector_medians.get(metric)
        hist_val = historical_averages.get(metric)
        if comp_val is not None:
            result[metric] = {
                "current": comp_val,
                "sector_median": sect_val,
                "historical_avg": hist_val,
                "vs_sector": (
                    round((comp_val / sect_val - 1) * 100, 1) if sect_val else None
                ),
                "vs_history": (
                    round((comp_val / hist_val - 1) * 100, 1) if hist_val else None
                ),
            }
    return result


def football_field(
    current_price: float,
    dcf_value: float | None,
    ddm_value: float | None,
    pe_implied: float | None,
    pb_implied: float | None,
    ev_ebitda_implied: float | None,
    analyst_low: float | None = None,
    analyst_high: float | None = None,
    analyst_avg: float | None = None,
) -> dict[str, Any]:
    """Build football field chart data — value ranges per methodology."""
    methods = {}

    if dcf_value:
        methods["DCF"] = {
            "low": round(dcf_value * 0.85, 2),
            "base": round(dcf_value, 2),
            "high": round(dcf_value * 1.15, 2),
        }
    if ddm_value:
        methods["DDM"] = {
            "low": round(ddm_value * 0.85, 2),
            "base": round(ddm_value, 2),
            "high": round(ddm_value * 1.15, 2),
        }
    if pe_implied:
        methods["P/E Relative"] = {
            "low": round(pe_implied * 0.85, 2),
            "base": round(pe_implied, 2),
            "high": round(pe_implied * 1.15, 2),
        }
    if pb_implied:
        methods["P/B Relative"] = {
            "low": round(pb_implied * 0.85, 2),
            "base": round(pb_implied, 2),
            "high": round(pb_implied * 1.15, 2),
        }
    if ev_ebitda_implied:
        methods["EV/EBITDA"] = {
            "low": round(ev_ebitda_implied * 0.85, 2),
            "base": round(ev_ebitda_implied, 2),
            "high": round(ev_ebitda_implied * 1.15, 2),
        }
    if analyst_avg:
        methods["Analyst Consensus"] = {
            "low": analyst_low or round(analyst_avg * 0.9, 2),
            "base": round(analyst_avg, 2),
            "high": analyst_high or round(analyst_avg * 1.1, 2),
        }

    # Composite
    all_bases = [m["base"] for m in methods.values()]
    all_lows = [m["low"] for m in methods.values()]
    all_highs = [m["high"] for m in methods.values()]

    composite = {}
    if all_bases:
        composite = {
            "low": round(min(all_lows), 2),
            "base": round(np.median(all_bases), 2),
            "high": round(max(all_highs), 2),
        }

    return {
        "current_price": current_price,
        "methods": methods,
        "composite": composite,
        "upside_to_base": (
            round((composite["base"] / current_price - 1) * 100, 1)
            if composite and current_price
            else None
        ),
    }
