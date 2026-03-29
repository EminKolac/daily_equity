"""Technical analysis — indicators, signals, scoring."""

import logging
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def compute_sma(series: pd.Series, window: int) -> pd.Series:
    return series.rolling(window=window, min_periods=1).mean()


def compute_ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False).mean()


def compute_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0.0)).rolling(window=period).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def compute_macd(
    series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9
) -> dict[str, pd.Series]:
    ema_fast = compute_ema(series, fast)
    ema_slow = compute_ema(series, slow)
    macd_line = ema_fast - ema_slow
    signal_line = compute_ema(macd_line, signal)
    histogram = macd_line - signal_line
    return {"macd": macd_line, "signal": signal_line, "histogram": histogram}


def compute_bollinger_bands(
    series: pd.Series, window: int = 20, num_std: float = 2.0
) -> dict[str, pd.Series]:
    sma = compute_sma(series, window)
    std = series.rolling(window=window, min_periods=1).std()
    return {
        "upper": sma + num_std * std,
        "middle": sma,
        "lower": sma - num_std * std,
    }


def compute_stochastic(
    high: pd.Series, low: pd.Series, close: pd.Series,
    k_period: int = 14, d_period: int = 3
) -> dict[str, pd.Series]:
    lowest_low = low.rolling(window=k_period).min()
    highest_high = high.rolling(window=k_period).max()
    k = 100 * (close - lowest_low) / (highest_high - lowest_low).replace(0, np.nan)
    d = k.rolling(window=d_period).mean()
    return {"k": k, "d": d}


def compute_atr(
    high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14
) -> pd.Series:
    tr1 = high - low
    tr2 = (high - close.shift()).abs()
    tr3 = (low - close.shift()).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.rolling(window=period).mean()


def compute_obv(close: pd.Series, volume: pd.Series) -> pd.Series:
    direction = np.sign(close.diff())
    return (volume * direction).cumsum()


def compute_adx(
    high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14
) -> pd.Series:
    plus_dm = high.diff()
    minus_dm = -low.diff()
    plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0.0)
    minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0.0)
    atr = compute_atr(high, low, close, period)
    plus_di = 100 * compute_ema(plus_dm, period) / atr.replace(0, np.nan)
    minus_di = 100 * compute_ema(minus_dm, period) / atr.replace(0, np.nan)
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    adx = compute_ema(dx, period)
    return adx


def compute_fibonacci_levels(high: float, low: float) -> dict[str, float]:
    diff = high - low
    return {
        "0.0%": high,
        "23.6%": high - 0.236 * diff,
        "38.2%": high - 0.382 * diff,
        "50.0%": high - 0.500 * diff,
        "61.8%": high - 0.618 * diff,
        "78.6%": high - 0.786 * diff,
        "100.0%": low,
    }


def compute_pivot_points(high: float, low: float, close: float) -> dict[str, float]:
    pivot = (high + low + close) / 3
    return {
        "r3": high + 2 * (pivot - low),
        "r2": pivot + (high - low),
        "r1": 2 * pivot - low,
        "pivot": pivot,
        "s1": 2 * pivot - high,
        "s2": pivot - (high - low),
        "s3": low - 2 * (high - pivot),
    }


def score_signal(value: float, thresholds: dict) -> str:
    """Convert a numeric value to a signal string."""
    if value >= thresholds.get("strong_buy", 80):
        return "Strong Buy"
    elif value >= thresholds.get("buy", 60):
        return "Buy"
    elif value >= thresholds.get("neutral_high", 40):
        return "Neutral"
    elif value >= thresholds.get("sell", 20):
        return "Sell"
    return "Strong Sell"


def compute_all_indicators(df: pd.DataFrame) -> dict[str, Any]:
    """Compute all technical indicators from an OHLCV DataFrame.

    Expects columns: Open, High, Low, Close, Volume
    """
    close = df["Close"]
    high = df["High"]
    low = df["Low"]
    volume = df["Volume"]

    last_close = float(close.iloc[-1])

    # Trend
    sma_20 = float(compute_sma(close, 20).iloc[-1])
    sma_50 = float(compute_sma(close, 50).iloc[-1])
    sma_200 = float(compute_sma(close, 200).iloc[-1])
    adx = float(compute_adx(high, low, close).iloc[-1]) if len(df) > 30 else 0

    # Momentum
    rsi_14 = float(compute_rsi(close).iloc[-1])
    macd_data = compute_macd(close)
    macd_val = float(macd_data["macd"].iloc[-1])
    macd_signal = float(macd_data["signal"].iloc[-1])
    macd_hist = float(macd_data["histogram"].iloc[-1])
    stoch = compute_stochastic(high, low, close)
    stoch_k = float(stoch["k"].iloc[-1]) if not stoch["k"].isna().all() else 50
    stoch_d = float(stoch["d"].iloc[-1]) if not stoch["d"].isna().all() else 50

    # Volatility
    bb = compute_bollinger_bands(close)
    bb_upper = float(bb["upper"].iloc[-1])
    bb_lower = float(bb["lower"].iloc[-1])
    bb_middle = float(bb["middle"].iloc[-1])
    atr = float(compute_atr(high, low, close).iloc[-1]) if len(df) > 20 else 0
    hist_vol_30 = float(close.pct_change().tail(30).std() * np.sqrt(252) * 100) if len(df) > 30 else 0

    # Volume
    obv = compute_obv(close, volume)
    obv_trend = "Rising" if obv.iloc[-1] > obv.iloc[-20] else "Falling" if len(obv) > 20 else "N/A"
    vol_avg_20 = float(volume.rolling(20).mean().iloc[-1]) if len(df) > 20 else 0
    vol_vs_avg = float(volume.iloc[-1] / vol_avg_20) if vol_avg_20 > 0 else 1.0

    # Support/Resistance
    high_52w = float(high.tail(252).max()) if len(df) >= 252 else float(high.max())
    low_52w = float(low.tail(252).min()) if len(df) >= 252 else float(low.min())
    fib_levels = compute_fibonacci_levels(high_52w, low_52w)
    pivots = compute_pivot_points(float(high.iloc[-1]), float(low.iloc[-1]), last_close)

    # Scoring
    trend_score = 50
    if last_close > sma_200:
        trend_score += 15
    if last_close > sma_50:
        trend_score += 10
    if last_close > sma_20:
        trend_score += 5
    if sma_50 > sma_200:
        trend_score += 10
    if adx > 25:
        trend_score += 10

    momentum_score = 50
    if 40 < rsi_14 < 60:
        momentum_score += 0
    elif rsi_14 < 30:
        momentum_score -= 20
    elif rsi_14 > 70:
        momentum_score -= 10
    elif rsi_14 > 50:
        momentum_score += 10
    if macd_hist > 0:
        momentum_score += 15
    if stoch_k > stoch_d:
        momentum_score += 10

    vol_score = 50
    if vol_vs_avg > 1.5:
        vol_score += 15
    elif vol_vs_avg < 0.5:
        vol_score -= 10
    if obv_trend == "Rising":
        vol_score += 10

    technical_score = round(0.4 * trend_score + 0.35 * momentum_score + 0.25 * vol_score)
    technical_score = max(0, min(100, technical_score))

    thresholds = {"strong_buy": 75, "buy": 60, "neutral_high": 40, "sell": 25}

    indicators = {
        "trend": {
            "sma_20": round(sma_20, 2),
            "sma_50": round(sma_50, 2),
            "sma_200": round(sma_200, 2),
            "adx": round(adx, 2),
            "price_vs_sma200": "Above" if last_close > sma_200 else "Below",
            "golden_cross": sma_50 > sma_200,
        },
        "momentum": {
            "rsi_14": round(rsi_14, 2),
            "macd": round(macd_val, 4),
            "macd_signal": round(macd_signal, 4),
            "macd_histogram": round(macd_hist, 4),
            "stochastic_k": round(stoch_k, 2),
            "stochastic_d": round(stoch_d, 2),
        },
        "volatility": {
            "bb_upper": round(bb_upper, 2),
            "bb_middle": round(bb_middle, 2),
            "bb_lower": round(bb_lower, 2),
            "atr_14": round(atr, 2),
            "hist_volatility_30d": round(hist_vol_30, 2),
        },
        "volume": {
            "obv_trend": obv_trend,
            "volume_vs_avg_20": round(vol_vs_avg, 2),
        },
        "support_resistance": {
            "high_52w": round(high_52w, 2),
            "low_52w": round(low_52w, 2),
            "fibonacci": {k: round(v, 2) for k, v in fib_levels.items()},
            "pivots": {k: round(v, 2) for k, v in pivots.items()},
        },
    }

    signals = {
        "trend": score_signal(trend_score, thresholds),
        "momentum": score_signal(momentum_score, thresholds),
        "volume": score_signal(vol_score, thresholds),
        "overall": score_signal(technical_score, thresholds),
    }

    support_levels = sorted([
        pivots["s1"], pivots["s2"], fib_levels["61.8%"], low_52w
    ])
    resistance_levels = sorted([
        pivots["r1"], pivots["r2"], fib_levels["38.2%"], high_52w
    ])

    return {
        "indicators": indicators,
        "signals": signals,
        "technical_score": technical_score,
        "key_levels": {
            "support": [round(s, 2) for s in support_levels],
            "resistance": [round(r, 2) for r in resistance_levels],
        },
        "last_close": round(last_close, 2),
        "bb_series": bb,
        "macd_series": macd_data,
        "rsi_series": compute_rsi(close),
    }
