"""Composite scoring — aggregate multi-factor scores."""

from typing import Any


WEIGHTS = {
    "fundamental": 0.30,
    "technical": 0.25,
    "macro": 0.20,
    "sentiment": 0.25,
}


def composite_score(scores: dict[str, float]) -> dict[str, Any]:
    """Compute weighted composite score from sub-scores (each 0-100)."""
    weighted = 0
    total_weight = 0
    details = {}

    for factor, weight in WEIGHTS.items():
        val = scores.get(factor)
        if val is not None:
            weighted += val * weight
            total_weight += weight
            details[factor] = {"score": round(val, 1), "weight": weight}

    overall = round(weighted / total_weight, 1) if total_weight > 0 else 50

    if overall >= 75:
        recommendation = "OUTPERFORM"
    elif overall >= 45:
        recommendation = "MARKET PERFORM"
    else:
        recommendation = "UNDERPERFORM"

    if overall >= 80:
        conviction = "High"
    elif overall >= 60:
        conviction = "Medium"
    else:
        conviction = "Low"

    return {
        "overall": overall,
        "recommendation": recommendation,
        "conviction": conviction,
        "details": details,
    }
