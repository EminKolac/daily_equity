"""Charts for the Temettü & Sermaye (Dividend & Capital) portfolio dashboard.

Two visualisations that mirror the Power BI dashboard layout:

* :func:`dividend_income_by_ticker_chart` — horizontal stacked bar of
  gross and net dividend income per ticker.
* :func:`yield_payout_trend_chart` — yearly line chart of weighted
  average dividend yield and payout ratio.
"""

from __future__ import annotations

from typing import Iterable

import numpy as np
import pandas as pd

from charts.style import (
    COLORS,
    apply_style,
    create_figure,
    format_turkish_number,
    save_chart,
)


def dividend_income_by_ticker_chart(by_ticker: pd.DataFrame) -> bytes:
    """Horizontal stacked bar — gross + net dividend income per ticker (TRY).

    Expects columns:  Ticker, Total_Div_Gross, Total_Div_Net.
    """
    fig, ax = create_figure(7.2, 3.8)
    if by_ticker is None or by_ticker.empty:
        ax.text(0.5, 0.5, "Veri yok", ha="center", va="center",
                transform=ax.transAxes, color=COLORS["neutral"], fontsize=11)
        apply_style(ax, "Temettü geliri — ticker bazında (brüt + net stacked)")
        fig.tight_layout()
        return save_chart(fig)

    df = by_ticker.sort_values("Total_Div_Gross", ascending=True).reset_index(drop=True)
    y = np.arange(len(df))

    gross = df["Total_Div_Gross"].to_numpy()
    net = df["Total_Div_Net"].to_numpy()

    ax.barh(y, gross, color=COLORS["secondary"], alpha=0.9, label="Total_Div_Gross")
    ax.barh(y, net, left=gross, color=COLORS["accent"], alpha=0.9, label="Total_Div_Net")

    ax.set_yticks(y)
    ax.set_yticklabels(df["Ticker"].tolist(), fontsize=9)

    ax.xaxis.set_major_formatter(
        __import__("matplotlib.ticker", fromlist=["FuncFormatter"]).FuncFormatter(
            lambda v, _pos: format_turkish_number(v)
        )
    )
    apply_style(ax, "Temettü geliri — ticker bazında (brüt + net stacked)",
                xlabel="TRY")
    ax.legend(loc="lower right", fontsize=8, frameon=False)
    fig.tight_layout()
    return save_chart(fig)


def yield_payout_trend_chart(by_year: pd.DataFrame) -> bytes:
    """Line chart of average yield and average payout ratio over time."""
    fig, ax = create_figure(6.0, 3.8)

    if by_year is None or by_year.empty:
        ax.text(0.5, 0.5, "Veri yok", ha="center", va="center",
                transform=ax.transAxes, color=COLORS["neutral"], fontsize=11)
        apply_style(ax, "Yield & Payout — yıllık trend")
        fig.tight_layout()
        return save_chart(fig)

    df = by_year.sort_values("Year").reset_index(drop=True)
    years = df["Year"].astype(int).tolist()

    ax.plot(years, df["Avg_Yield"] * 100, marker="o", markersize=4,
            linewidth=1.8, color=COLORS["secondary"], label="Avg_Yield")
    ax.plot(years, df["Avg_Payout"] * 100, marker="o", markersize=4,
            linewidth=1.8, color=COLORS["accent"], label="Avg_Payout")

    ax.yaxis.set_major_formatter(
        __import__("matplotlib.ticker", fromlist=["FuncFormatter"]).FuncFormatter(
            lambda v, _pos: f"{v:.0f}%"
        )
    )
    ax.set_xticks(years)
    apply_style(ax, "Yield & Payout — yıllık trend", xlabel="Yıl")
    ax.legend(loc="upper left", fontsize=8, frameon=False)
    fig.tight_layout()
    return save_chart(fig)


def portfolio_cost_basis_chart(positions: pd.DataFrame) -> bytes:
    """Optional: horizontal bar of cost basis (TRY) per ticker.

    Provides a Sermaye (capital) reference companion chart.
    """
    fig, ax = create_figure(7.2, 3.4)
    if positions is None or positions.empty:
        ax.text(0.5, 0.5, "Veri yok", ha="center", va="center",
                transform=ax.transAxes, color=COLORS["neutral"], fontsize=11)
        apply_style(ax, "Maliyet bazı — ticker bazında")
        fig.tight_layout()
        return save_chart(fig)

    df = positions.sort_values("cost_basis_try", ascending=True).reset_index(drop=True)
    y = np.arange(len(df))
    ax.barh(y, df["cost_basis_try"], color=COLORS["primary"], alpha=0.9)
    ax.set_yticks(y)
    ax.set_yticklabels(df["ticker"].tolist(), fontsize=9)
    ax.xaxis.set_major_formatter(
        __import__("matplotlib.ticker", fromlist=["FuncFormatter"]).FuncFormatter(
            lambda v, _pos: format_turkish_number(v)
        )
    )
    apply_style(ax, "Maliyet bazı — ticker bazında (TRY)", xlabel="TRY")
    fig.tight_layout()
    return save_chart(fig)
