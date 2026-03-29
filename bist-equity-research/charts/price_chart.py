"""Price charts — candlestick, price vs benchmark, relative performance."""

import io
import logging

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
import pandas as pd

from charts.style import COLORS, apply_style, create_figure, save_chart, DPI

logger = logging.getLogger(__name__)


def price_vs_benchmark(
    stock_prices: pd.DataFrame,
    benchmark_prices: pd.DataFrame,
    ticker: str,
    benchmark_name: str = "BIST 100",
    period_label: str = "1Y",
) -> bytes:
    """Rebased price vs benchmark chart (base = 100)."""
    fig, ax = create_figure(7, 3.5)

    stock = stock_prices["Close"].dropna()
    bench = benchmark_prices["Close"].dropna()

    if stock.empty or bench.empty:
        apply_style(ax, f"{ticker} vs {benchmark_name} — No Data")
        return save_chart(fig)

    # Rebase to 100
    stock_rebased = stock / stock.iloc[0] * 100
    bench_rebased = bench / bench.iloc[0] * 100

    ax.plot(stock_rebased.index, stock_rebased.values,
            color=COLORS["secondary"], linewidth=1.5, label=ticker)
    ax.plot(bench_rebased.index, bench_rebased.values,
            color=COLORS["neutral"], linewidth=1.2, label=benchmark_name, linestyle="--")

    ax.fill_between(stock_rebased.index, stock_rebased.values, bench_rebased.values,
                     where=stock_rebased.values >= bench_rebased.values,
                     alpha=0.1, color=COLORS["positive"])
    ax.fill_between(stock_rebased.index, stock_rebased.values, bench_rebased.values,
                     where=stock_rebased.values < bench_rebased.values,
                     alpha=0.1, color=COLORS["negative"])

    ax.axhline(y=100, color=COLORS["grid"], linestyle="-", alpha=0.5)
    apply_style(ax, f"{ticker} vs {benchmark_name} ({period_label})", ylabel="Rebased (100)")
    ax.legend(fontsize=8, loc="upper left")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %y"))
    fig.autofmt_xdate()

    return save_chart(fig)


def candlestick_chart(
    df: pd.DataFrame,
    ticker: str,
    sma_periods: list[int] | None = None,
) -> bytes:
    """2Y daily candlestick + volume + SMA overlay."""
    if sma_periods is None:
        sma_periods = [50, 200]

    fig, (ax_price, ax_vol) = create_figure(7, 4.5, nrows=2, gridspec_kw={"height_ratios": [3, 1]})

    close = df["Close"]
    opens = df["Open"]
    high = df["High"]
    low = df["Low"]
    volume = df["Volume"]

    # Simplified OHLC as colored bars
    up = close >= opens
    down = ~up

    x = np.arange(len(df))

    # Candle bodies
    ax_price.bar(x[up], (close[up] - opens[up]).values, bottom=opens[up].values,
                  color=COLORS["positive"], width=0.8, alpha=0.9)
    ax_price.bar(x[down], (opens[down] - close[down]).values, bottom=close[down].values,
                  color=COLORS["negative"], width=0.8, alpha=0.9)
    # Wicks
    ax_price.vlines(x[up], low[up].values, high[up].values, color=COLORS["positive"], linewidth=0.5)
    ax_price.vlines(x[down], low[down].values, high[down].values, color=COLORS["negative"], linewidth=0.5)

    # SMAs
    sma_colors = [COLORS["accent"], COLORS["primary"]]
    for i, period in enumerate(sma_periods):
        sma = close.rolling(window=period).mean()
        color = sma_colors[i % len(sma_colors)]
        ax_price.plot(x, sma.values, color=color, linewidth=1.2,
                       label=f"SMA({period})", alpha=0.8)

    apply_style(ax_price, f"{ticker} — Price Chart (2Y)")
    ax_price.legend(fontsize=7, loc="upper left")

    # Volume
    vol_colors = [COLORS["positive"] if u else COLORS["negative"] for u in up]
    ax_vol.bar(x, volume.values, color=vol_colors, alpha=0.6, width=0.8)
    apply_style(ax_vol, ylabel="Volume")

    # X-axis ticks — show every ~60 trading days
    tick_step = max(1, len(df) // 8)
    tick_positions = x[::tick_step]
    tick_labels = [df.index[i].strftime("%b %y") if i < len(df) else "" for i in tick_positions]
    ax_vol.set_xticks(tick_positions)
    ax_vol.set_xticklabels(tick_labels, fontsize=7)
    ax_price.set_xticks([])

    fig.tight_layout()
    return save_chart(fig)


def relative_performance_chart(
    performance: dict[str, dict[str, float | None]],
    ticker: str,
) -> bytes:
    """Bar chart of relative performance across periods."""
    fig, ax = create_figure(7, 3)

    periods = list(performance.keys())
    stock_rets = [performance[p].get("stock") or 0 for p in periods]
    bench_rets = [performance[p].get("benchmark") or 0 for p in periods]

    x = np.arange(len(periods))
    width = 0.35

    bars1 = ax.bar(x - width / 2, stock_rets, width, label=ticker,
                    color=COLORS["secondary"], alpha=0.85)
    bars2 = ax.bar(x + width / 2, bench_rets, width, label="BIST 100",
                    color=COLORS["neutral"], alpha=0.7)

    ax.set_xticks(x)
    ax.set_xticklabels(periods, fontsize=9)
    ax.axhline(y=0, color=COLORS["dark_text"], linewidth=0.5)
    apply_style(ax, f"{ticker} — Relative Performance (%)", ylabel="Return (%)")
    ax.legend(fontsize=8)

    # Value labels
    for bar in bars1:
        h = bar.get_height()
        ax.text(bar.get_x() + bar.get_width() / 2, h, f"{h:.1f}%",
                ha="center", va="bottom" if h >= 0 else "top", fontsize=6)

    fig.tight_layout()
    return save_chart(fig)
