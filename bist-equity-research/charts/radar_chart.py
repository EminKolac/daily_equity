"""Multi-factor scoring radar chart."""

import logging
import math

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from charts.style import COLORS, save_chart

logger = logging.getLogger(__name__)


def radar_chart(
    scores: dict[str, float],
    ticker: str,
) -> bytes:
    """5-axis spider/radar chart for composite scoring.

    scores: dict like {"Fundamental": 72, "Technical": 58, ...}
    Values should be 0-100.
    """
    categories = list(scores.keys())
    values = [scores[c] for c in categories]
    N = len(categories)

    if N < 3:
        fig, ax = plt.subplots(figsize=(5, 5))
        ax.text(0.5, 0.5, "Insufficient data for radar", ha="center", va="center")
        return save_chart(fig)

    # Angles for each axis
    angles = [n / float(N) * 2 * math.pi for n in range(N)]
    values_plot = values + [values[0]]  # Close the polygon
    angles_plot = angles + [angles[0]]

    fig, ax = plt.subplots(figsize=(5, 5), subplot_kw=dict(polar=True))
    fig.patch.set_facecolor(COLORS["background"])
    ax.set_facecolor(COLORS["background"])

    # Draw the radar
    ax.plot(angles_plot, values_plot, color=COLORS["secondary"], linewidth=2)
    ax.fill(angles_plot, values_plot, alpha=0.15, color=COLORS["secondary"])

    # Draw reference circles
    for level in [25, 50, 75, 100]:
        circle = [level] * (N + 1)
        ax.plot(angles_plot, circle, color=COLORS["grid"], linewidth=0.5, linestyle="--")

    # Labels
    ax.set_xticks(angles)
    ax.set_xticklabels(categories, fontsize=9, color=COLORS["primary"], fontweight="bold")
    ax.set_ylim(0, 100)
    ax.set_yticks([25, 50, 75])
    ax.set_yticklabels(["25", "50", "75"], fontsize=7, color=COLORS["neutral"])

    # Value annotations
    for angle, val, cat in zip(angles, values, categories):
        ax.annotate(f"{val:.0f}", xy=(angle, val), fontsize=8,
                    ha="center", va="bottom", color=COLORS["primary"], fontweight="bold")

    ax.set_title(f"{ticker} — Composite Score", fontsize=12,
                 fontweight="bold", color=COLORS["primary"], pad=20)

    return save_chart(fig)
