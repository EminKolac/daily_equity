"""Financial health scoring — Piotroski F-Score, Altman Z-Score, DuPont."""

import logging
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


def piotroski_f_score(data: dict[str, float | None]) -> dict[str, Any]:
    """Compute Piotroski F-Score (0-9).

    Expected keys in data:
        net_income, operating_cf, roa_current, roa_prior,
        long_term_debt_current, long_term_debt_prior,
        current_ratio_current, current_ratio_prior,
        shares_current, shares_prior,
        gross_margin_current, gross_margin_prior,
        asset_turnover_current, asset_turnover_prior
    """
    score = 0
    details = {}

    # Profitability (4 points)
    ni = data.get("net_income", 0) or 0
    ocf = data.get("operating_cf", 0) or 0
    roa_c = data.get("roa_current") or 0
    roa_p = data.get("roa_prior") or 0

    details["positive_net_income"] = int(ni > 0)
    details["positive_operating_cf"] = int(ocf > 0)
    details["roa_improving"] = int(roa_c > roa_p)
    details["accruals_quality"] = int(ocf > ni)
    score += sum([
        details["positive_net_income"],
        details["positive_operating_cf"],
        details["roa_improving"],
        details["accruals_quality"],
    ])

    # Leverage (3 points)
    ltd_c = data.get("long_term_debt_current") or 0
    ltd_p = data.get("long_term_debt_prior") or 0
    cr_c = data.get("current_ratio_current") or 0
    cr_p = data.get("current_ratio_prior") or 0
    shares_c = data.get("shares_current") or 0
    shares_p = data.get("shares_prior") or 0

    details["debt_decreasing"] = int(ltd_c < ltd_p)
    details["current_ratio_improving"] = int(cr_c > cr_p)
    details["no_dilution"] = int(shares_c <= shares_p)
    score += sum([
        details["debt_decreasing"],
        details["current_ratio_improving"],
        details["no_dilution"],
    ])

    # Efficiency (2 points)
    gm_c = data.get("gross_margin_current") or 0
    gm_p = data.get("gross_margin_prior") or 0
    at_c = data.get("asset_turnover_current") or 0
    at_p = data.get("asset_turnover_prior") or 0

    details["gross_margin_improving"] = int(gm_c > gm_p)
    details["asset_turnover_improving"] = int(at_c > at_p)
    score += sum([
        details["gross_margin_improving"],
        details["asset_turnover_improving"],
    ])

    interpretation = "Strong" if score >= 7 else "Moderate" if score >= 4 else "Weak"

    return {
        "score": score,
        "max_score": 9,
        "interpretation": interpretation,
        "details": details,
    }


def altman_z_score(data: dict[str, float | None]) -> dict[str, Any]:
    """Compute Altman Z-Score for manufacturing companies.

    Z = 1.2*A + 1.4*B + 3.3*C + 0.6*D + 1.0*E
    A = Working Capital / Total Assets
    B = Retained Earnings / Total Assets
    C = EBIT / Total Assets
    D = Market Value of Equity / Total Liabilities
    E = Sales / Total Assets
    """
    ta = data.get("total_assets") or 1
    a = (data.get("working_capital") or 0) / ta
    b = (data.get("retained_earnings") or 0) / ta
    c = (data.get("ebit") or 0) / ta
    total_liabilities = data.get("total_liabilities") or 1
    d = (data.get("market_cap") or 0) / total_liabilities
    e = (data.get("revenue") or 0) / ta

    z = 1.2 * a + 1.4 * b + 3.3 * c + 0.6 * d + 1.0 * e

    if z > 2.99:
        zone = "Safe"
    elif z > 1.81:
        zone = "Grey"
    else:
        zone = "Distress"

    return {
        "z_score": round(z, 2),
        "zone": zone,
        "components": {
            "A_working_capital_ta": round(a, 4),
            "B_retained_earnings_ta": round(b, 4),
            "C_ebit_ta": round(c, 4),
            "D_market_equity_tl": round(d, 4),
            "E_sales_ta": round(e, 4),
        },
    }


def dupont_decomposition(
    net_income: float,
    revenue: float,
    total_assets: float,
    total_equity: float,
) -> dict[str, Any]:
    """DuPont 3-factor decomposition of ROE.

    ROE = Net Margin × Asset Turnover × Equity Multiplier
    """
    net_margin = net_income / revenue if revenue else 0
    asset_turnover = revenue / total_assets if total_assets else 0
    equity_multiplier = total_assets / total_equity if total_equity else 0
    roe = net_margin * asset_turnover * equity_multiplier

    return {
        "roe": round(roe * 100, 2),
        "net_margin": round(net_margin * 100, 2),
        "asset_turnover": round(asset_turnover, 4),
        "equity_multiplier": round(equity_multiplier, 2),
        "decomposition": (
            f"ROE {roe*100:.1f}% = "
            f"Margin {net_margin*100:.1f}% × "
            f"Turnover {asset_turnover:.2f}x × "
            f"Leverage {equity_multiplier:.2f}x"
        ),
    }


def earnings_quality(
    operating_cf: float,
    net_income: float,
    total_assets: float,
    receivables_current: float,
    receivables_prior: float,
    revenue: float,
) -> dict[str, Any]:
    """Assess earnings quality via accruals and receivables analysis."""
    accruals_ratio = (net_income - operating_cf) / total_assets if total_assets else 0
    cf_vs_ni = operating_cf / net_income if net_income else 0
    recv_to_rev_current = receivables_current / revenue if revenue else 0
    recv_to_rev_prior = receivables_prior / revenue if revenue else 0
    recv_trend = recv_to_rev_current - recv_to_rev_prior

    quality = "High"
    if cf_vs_ni < 0.8 or accruals_ratio > 0.10:
        quality = "Low"
    elif cf_vs_ni < 1.0 or accruals_ratio > 0.05:
        quality = "Moderate"

    return {
        "accruals_ratio": round(accruals_ratio, 4),
        "cf_vs_net_income": round(cf_vs_ni, 2),
        "receivables_to_revenue_change": round(recv_trend, 4),
        "quality": quality,
    }
