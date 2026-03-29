"""Technical analysis charts — price + Bollinger, RSI, MACD subplots."""

import logging

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from charts.style import COLORS, apply_style, create_figure, save_chart

logger = logging.getLogger(__name__)


def technical_indicator_chart(
    df: pd.DataFrame,
    bb: dict[str, pd.Series],
    rsi: pd.Series,
    macd_data: dict[str, pd.Series],
    ticker: str,
) -> bytes:
    """3-panel chart: Price + Bollinger, RSI, MACD."""
    fig, (ax1, ax2, ax3) = create_figure(
        7, 5, nrows=3, gridspec_kw={"height_ratios": [3, 1, 1]}
    )

    close = df["Close"]
    x = np.arange(len(df))

    # Panel 1: Price + Bollinger Bands
    ax1.plot(x, close.values, color=COLORS["primary"], linewidth=1, label="Close")
    ax1.plot(x, bb["upper"].values, color=COLORS["neutral"], linewidth=0.7, linestyle="--")
    ax1.plot(x, bb["middle"].values, color=COLORS["accent"], linewidth=0.7, linestyle="-")
    ax1.plot(x, bb["lower"].values, color=COLORS["neutral"], linewidth=0.7, linestyle="--")
    ax1.fill_between(x, bb["upper"].values, bb["lower"].values,
                      alpha=0.08, color=COLORS["secondary"])
    apply_style(ax1, f"{ticker} — Technical Analysis")
    ax1.legend(["Close", "BB Upper", "BB Middle", "BB Lower"], fontsize=6, loc="upper left")

    # Panel 2: RSI
    rsi_vals = rsi.values
    ax2.plot(x, rsi_vals, color=COLORS["secondary"], linewidth=1)
    ax2.axhline(y=70, color=COLORS["negative"], linestyle="--", linewidth=0.7, alpha=0.7)
    ax2.axhline(y=30, color=COLORS["positive"], linestyle="--", linewidth=0.7, alpha=0.7)
    ax2.fill_between(x, 70, rsi_vals, where=rsi_vals >= 70,
                      alpha=0.2, color=COLORS["negative"])
    ax2.fill_between(x, 30, rsi_vals, where=rsi_vals <= 30,
                      alpha=0.2, color=COLORS["positive"])
    ax2.set_ylim(0, 100)
    apply_style(ax2, ylabel="RSI(14)")

    # Panel 3: MACD
    macd_line = macd_data["macd"].values
    signal_line = macd_data["signal"].values
    histogram = macd_data["histogram"].values

    hist_colors = [COLORS["positive"] if h >= 0 else COLORS["negative"] for h in histogram]
    ax3.bar(x, histogram, color=hist_colors, alpha=0.5, width=1)
    ax3.plot(x, macd_line, color=COLORS["secondary"], linewidth=1, label="MACD")
    ax3.plot(x, signal_line, color=COLORS["accent"], linewidth=1, label="Signal")
    ax3.axhline(y=0, color=COLORS["dark_text"], linewidth=0.3)
    apply_style(ax3, ylabel="MACD")
    ax3.legend(fontsize=6, loc="upper left")

    # X-axis ticks on bottom panel
    tick_step = max(1, len(df) // 8)
    tick_positions = x[::tick_step]
    tick_labels = [df.index[i].strftime("%b %y") if i < len(df) else "" for i in tick_positions]
    ax3.set_xticks(tick_positions)
    ax3.set_xticklabels(tick_labels, fontsize=7)
    ax1.set_xticks([])
    ax2.set_xticks([])

    fig.tight_layout()
    return save_chart(fig)
