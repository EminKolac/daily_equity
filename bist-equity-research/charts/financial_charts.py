"""Financial charts — revenue/margins, EPS/P-E, balance sheet, cash flow waterfall, dividends."""

import logging

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from charts.style import COLORS, apply_style, create_figure, save_chart, format_turkish_number

logger = logging.getLogger(__name__)


def revenue_margins_chart(
    dates: list[str],
    revenue: list[float],
    gross_margin: list[float],
    ebitda_margin: list[float],
    net_margin: list[float],
    ticker: str,
) -> bytes:
    """Revenue bars + margin lines."""
    fig, ax1 = create_figure(7, 3.5)
    ax2 = ax1.twinx()

    x = np.arange(len(dates))
    ax1.bar(x, revenue, color=COLORS["light_blue"], alpha=0.7, label="Revenue", width=0.6)

    ax2.plot(x, gross_margin, color=COLORS["positive"], marker="o", markersize=3,
             linewidth=1.5, label="Gross Margin %")
    ax2.plot(x, ebitda_margin, color=COLORS["secondary"], marker="s", markersize=3,
             linewidth=1.5, label="EBITDA Margin %")
    ax2.plot(x, net_margin, color=COLORS["accent"], marker="^", markersize=3,
             linewidth=1.5, label="Net Margin %")

    ax1.set_xticks(x)
    ax1.set_xticklabels(dates, fontsize=7, rotation=45, ha="right")
    apply_style(ax1, f"{ticker} — Revenue & Margins", ylabel="Revenue (TRY)")
    ax2.set_ylabel("Margin (%)", fontsize=9, color=COLORS["dark_text"])
    ax2.spines["top"].set_visible(False)

    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, fontsize=7, loc="upper left")

    fig.tight_layout()
    return save_chart(fig)


def eps_pe_chart(
    dates: list[str],
    eps: list[float],
    pe_ratio: list[float],
    ticker: str,
) -> bytes:
    """EPS bars + P/E line."""
    fig, ax1 = create_figure(7, 3.5)
    ax2 = ax1.twinx()

    x = np.arange(len(dates))
    colors = [COLORS["positive"] if e >= 0 else COLORS["negative"] for e in eps]
    ax1.bar(x, eps, color=colors, alpha=0.7, label="EPS (TRY)", width=0.6)

    ax2.plot(x, pe_ratio, color=COLORS["primary"], marker="o", markersize=3,
             linewidth=1.5, label="P/E Ratio")

    ax1.set_xticks(x)
    ax1.set_xticklabels(dates, fontsize=7, rotation=45, ha="right")
    apply_style(ax1, f"{ticker} — EPS & P/E Ratio", ylabel="EPS (TRY)")
    ax2.set_ylabel("P/E Ratio", fontsize=9, color=COLORS["dark_text"])

    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, fontsize=7, loc="upper left")

    fig.tight_layout()
    return save_chart(fig)


def balance_sheet_chart(
    dates: list[str],
    current_assets: list[float],
    non_current_assets: list[float],
    current_liabilities: list[float],
    non_current_liabilities: list[float],
    equity: list[float],
    ticker: str,
) -> bytes:
    """Stacked bar — assets vs liabilities+equity."""
    fig, (ax1, ax2) = create_figure(7, 3.5, ncols=2)

    x = np.arange(len(dates))
    width = 0.6

    # Assets
    ax1.bar(x, current_assets, width, label="Current Assets", color=COLORS["secondary"], alpha=0.8)
    ax1.bar(x, non_current_assets, width, bottom=current_assets,
            label="Non-Current Assets", color=COLORS["primary"], alpha=0.8)
    ax1.set_xticks(x)
    ax1.set_xticklabels(dates, fontsize=7, rotation=45, ha="right")
    apply_style(ax1, "Assets", ylabel="TRY")
    ax1.legend(fontsize=6)

    # Liabilities + Equity
    ax2.bar(x, current_liabilities, width, label="Current Liab.", color=COLORS["negative"], alpha=0.6)
    ax2.bar(x, non_current_liabilities, width, bottom=current_liabilities,
            label="Non-Current Liab.", color=COLORS["accent"], alpha=0.6)
    nc_cl = [c + n for c, n in zip(current_liabilities, non_current_liabilities)]
    ax2.bar(x, equity, width, bottom=nc_cl, label="Equity", color=COLORS["positive"], alpha=0.7)
    ax2.set_xticks(x)
    ax2.set_xticklabels(dates, fontsize=7, rotation=45, ha="right")
    apply_style(ax2, "Liabilities & Equity", ylabel="TRY")
    ax2.legend(fontsize=6)

    fig.suptitle(f"{ticker} — Balance Sheet Composition", fontsize=11,
                 fontweight="bold", color=COLORS["primary"], y=1.02)
    fig.tight_layout()
    return save_chart(fig)


def cash_flow_waterfall(
    operating_cf: float,
    capex: float,
    fcf: float,
    dividends: float,
    ticker: str,
) -> bytes:
    """Cash flow waterfall: Operating CF → CapEx → FCF → Dividends."""
    fig, ax = create_figure(7, 3.5)

    categories = ["Operating CF", "CapEx", "FCF", "Dividends Paid"]
    values = [operating_cf, capex, fcf, -abs(dividends)]

    colors = []
    for v in values:
        colors.append(COLORS["positive"] if v >= 0 else COLORS["negative"])

    bottoms = [0, 0, 0, 0]
    # Waterfall logic: each bar starts where previous ended
    running = 0
    bar_vals = []
    for i, v in enumerate(values):
        if i == 0:
            bottoms[i] = 0
            bar_vals.append(v)
        elif i == 2:  # FCF is independent (OCF + CapEx)
            bottoms[i] = 0
            bar_vals.append(v)
        else:
            bottoms[i] = running
            bar_vals.append(v)
        running += v if i != 2 else 0

    x = np.arange(len(categories))
    bars = ax.bar(x, bar_vals, bottom=bottoms, color=colors, width=0.5, alpha=0.85)

    for bar, val in zip(bars, values):
        h = bar.get_height()
        y_pos = bar.get_y() + h
        ax.text(bar.get_x() + bar.get_width() / 2, y_pos,
                format_turkish_number(val), ha="center", va="bottom", fontsize=8)

    ax.set_xticks(x)
    ax.set_xticklabels(categories, fontsize=9)
    ax.axhline(y=0, color=COLORS["dark_text"], linewidth=0.5)
    apply_style(ax, f"{ticker} — Cash Flow Waterfall", ylabel="TRY")

    fig.tight_layout()
    return save_chart(fig)


def dividend_history_chart(
    years: list[str],
    dps: list[float],
    div_yield: list[float],
    ticker: str,
) -> bytes:
    """Dividend per share bars + yield line."""
    fig, ax1 = create_figure(7, 3)
    ax2 = ax1.twinx()

    x = np.arange(len(years))
    ax1.bar(x, dps, color=COLORS["secondary"], alpha=0.7, label="DPS (TRY)", width=0.5)
    ax2.plot(x, div_yield, color=COLORS["accent"], marker="o", markersize=4,
             linewidth=1.5, label="Yield (%)")

    ax1.set_xticks(x)
    ax1.set_xticklabels(years, fontsize=8)
    apply_style(ax1, f"{ticker} — Dividend History", ylabel="DPS (TRY)")
    ax2.set_ylabel("Dividend Yield (%)", fontsize=9, color=COLORS["dark_text"])

    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, fontsize=7, loc="upper left")

    fig.tight_layout()
    return save_chart(fig)
