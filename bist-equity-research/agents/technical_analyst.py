"""Agent 3: Technical Analyst — price action + indicator analysis."""

import logging
from typing import Any

import pandas as pd

from analysis.technicals import compute_all_indicators
from config.settings import MODEL

logger = logging.getLogger(__name__)


def create_technical_analyst(llm=None):
    """Factory: returns a technical analyst node."""

    async def technical_analyst_node(state: dict) -> dict:
        ticker = state["ticker"]
        logger.info("Technical Analyst: analyzing %s", ticker)

        price_data = state.get("price_data", {})
        df = price_data.get("price_history_2y")

        if df is None or (isinstance(df, pd.DataFrame) and df.empty):
            logger.warning("No price data for technical analysis")
            return {
                "technical_analysis": {
                    "indicators": {},
                    "signals": {},
                    "technical_score": 50,
                    "technical_summary": "Insufficient price data for technical analysis.",
                    "key_levels": {"support": [], "resistance": []},
                },
                "agent_logs": state.get("agent_logs", []) + [
                    {"agent": "technical_analyst", "status": "no_data"}
                ],
            }

        # Compute all indicators
        result = compute_all_indicators(df)

        # Generate narrative
        summary = ""
        if llm:
            try:
                indicators = result["indicators"]
                signals = result["signals"]
                prompt = f"""You are a chartered technical analyst. Given the indicators below for {ticker}, write a concise 3-sentence technical summary suitable for an equity research report.

Last Close: {result['last_close']} TRY
SMA(20): {indicators['trend']['sma_20']}, SMA(50): {indicators['trend']['sma_50']}, SMA(200): {indicators['trend']['sma_200']}
Price vs SMA200: {indicators['trend']['price_vs_sma200']}
Golden Cross: {indicators['trend']['golden_cross']}
RSI(14): {indicators['momentum']['rsi_14']}
MACD Histogram: {indicators['momentum']['macd_histogram']}
Bollinger Position: Close between {indicators['volatility']['bb_lower']} and {indicators['volatility']['bb_upper']}
OBV Trend: {indicators['volume']['obv_trend']}
Technical Score: {result['technical_score']}/100
Signals — Trend: {signals['trend']}, Momentum: {signals['momentum']}, Volume: {signals['volume']}
Support Levels: {result['key_levels']['support']}
Resistance Levels: {result['key_levels']['resistance']}

Write a professional, data-backed summary. No disclaimers."""
                response = await llm.ainvoke(prompt)
                summary = response.content if hasattr(response, "content") else str(response)
            except Exception as e:
                logger.error("LLM tech summary failed: %s", e)

        if not summary:
            ind = result["indicators"]
            summary = (
                f"{ticker} is trading at {result['last_close']} TRY, "
                f"{ind['trend']['price_vs_sma200']} its 200-day SMA ({ind['trend']['sma_200']}). "
                f"RSI at {ind['momentum']['rsi_14']:.0f} suggests "
                f"{'overbought' if ind['momentum']['rsi_14'] > 70 else 'oversold' if ind['momentum']['rsi_14'] < 30 else 'neutral momentum'}. "
                f"Overall technical signal: {signals['overall']}."
            )

        # Remove heavy series data before passing to state
        output = {
            "indicators": result["indicators"],
            "signals": result["signals"],
            "technical_score": result["technical_score"],
            "technical_summary": summary,
            "key_levels": result["key_levels"],
            "last_close": result["last_close"],
        }

        # Keep series for chart generation
        chart_data = {
            "bb_series": result.get("bb_series"),
            "macd_series": result.get("macd_series"),
            "rsi_series": result.get("rsi_series"),
            "price_df": df,
        }

        return {
            "technical_analysis": output,
            "_technical_chart_data": chart_data,
            "agent_logs": state.get("agent_logs", []) + [
                {"agent": "technical_analyst", "status": "complete",
                 "score": result["technical_score"]}
            ],
        }

    return technical_analyst_node
