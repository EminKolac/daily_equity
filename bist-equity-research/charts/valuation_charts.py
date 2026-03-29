"""Valuation charts — football field, P/E band."""

import logging

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from charts.style import COLORS, apply_style, create_figure, save_chart

logger = logging.getLogger(__name__)


def football_field_chart(
    valuation_data: dict,
    ticker: str,
) -> bytes:
    """Horizontal bar chart showing value range per methodology."""
    fig, ax = create_figure(7, 3)

    methods = valuation_data.get("methods", {})
    current_price = valuation_data.get("current_price", 0)

    if not methods:
        apply_style(ax, f"{ticker} — Valuation Range (No Data)")
        return save_chart(fig)

    labels = list(methods.keys())
    lows = [methods[m]["low"] for m in labels]
    bases = [methods[m]["base"] for m in labels]
    highs = [methods[m]["high"] for m in labels]

    y = np.arange(len(labels))
    ranges = [h - l for l, h in zip(lows, highs)]

    ax.barh(y, ranges, left=lows, height=0.5, color=COLORS["light_blue"], alpha=0.6)

    # Base markers
    ax.scatter(bases, y, color=COLORS["primary"], zorder=5, s=50, marker="D", label="Base Case")

    # Current price line
    ax.axvline(x=current_price, color=COLORS["negative"], linestyle="--",
               linewidth=1.5, label=f"Current: {current_price:.2f}")

    # Composite range
    composite = valuation_data.get("composite", {})
    if composite:
        ax.axvspan(composite.get("low", 0), composite.get("high", 0),
                    alpha=0.08, color=COLORS["positive"])

    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=9)
    apply_style(ax, f"{ticker} — Valuation Football Field", xlabel="Price (TRY)")
    ax.legend(fontsize=7, loc="lower right")

    fig.tight_layout()
    return save_chart(fig)
