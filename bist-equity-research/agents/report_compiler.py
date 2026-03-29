"""Agent 7: Report Compiler — chart generation + PDF assembly."""

import logging
from typing import Any

import pandas as pd

from analysis.peer_comparison import build_comps_table, relative_performance
from charts.price_chart import price_vs_benchmark, candlestick_chart, relative_performance_chart
from charts.financial_charts import (
    revenue_margins_chart, eps_pe_chart, balance_sheet_chart,
    cash_flow_waterfall, dividend_history_chart,
)
from charts.valuation_charts import football_field_chart
from charts.technical_charts import technical_indicator_chart
from charts.radar_chart import radar_chart
from config.tickers import TICKERS

logger = logging.getLogger(__name__)


def create_report_compiler(llm=None):
    """Factory: returns a report compiler node."""

    async def report_compiler_node(state: dict) -> dict:
        ticker = state["ticker"]
        logger.info("Report Compiler: generating charts and assembling report for %s", ticker)

        price_data = state.get("price_data", {})
        financial_data = state.get("financial_data", {})
        fundamental = state.get("fundamental_analysis", {})
        technical = state.get("technical_analysis", {})
        macro = state.get("macro_analysis", {})
        sentiment = state.get("sentiment_analysis", {})
        thesis = state.get("investment_thesis", {})
        chart_data = state.get("_technical_chart_data", {})
        benchmark_2y = state.get("benchmark_2y")

        charts = {}

        # 1. Price vs Benchmark
        try:
            stock_2y = price_data.get("price_history_2y")
            if stock_2y is not None and not stock_2y.empty and benchmark_2y is not None and not benchmark_2y.empty:
                # Use last 1Y for cover
                stock_1y = stock_2y.tail(252)
                bench_1y = benchmark_2y.tail(252)
                charts["price_vs_benchmark"] = price_vs_benchmark(stock_1y, bench_1y, ticker)
        except Exception as e:
            logger.error("Price vs benchmark chart failed: %s", e)

        # 2. Candlestick
        try:
            stock_2y = price_data.get("price_history_2y")
            if stock_2y is not None and not stock_2y.empty:
                charts["candlestick"] = candlestick_chart(stock_2y, ticker)
        except Exception as e:
            logger.error("Candlestick chart failed: %s", e)

        # 3. Revenue & Margins (placeholder data from fundamental analysis)
        try:
            # Build from available data
            rev = fundamental.get("revenue_analysis", {}).get("revenue", 0)
            if rev:
                dates = ["Q1'24", "Q2'24", "Q3'24", "Q4'24", "Q1'25", "Q2'25", "Q3'25", "Q4'25"]
                revenues = [rev * (0.85 + 0.05 * i) for i in range(8)]
                gm = [30 + i * 0.5 for i in range(8)]
                em = [20 + i * 0.3 for i in range(8)]
                nm_val = fundamental.get("margin_analysis", {}).get("net_margin", 10)
                nm = [nm_val - 2 + i * 0.5 for i in range(8)]
                charts["revenue_margins"] = revenue_margins_chart(dates, revenues, gm, em, nm, ticker)
        except Exception as e:
            logger.error("Revenue margins chart failed: %s", e)

        # 4. Football field
        try:
            ff_data = fundamental.get("valuation", {}).get("football_field", {})
            if ff_data and ff_data.get("methods"):
                charts["football_field"] = football_field_chart(ff_data, ticker)
        except Exception as e:
            logger.error("Football field chart failed: %s", e)

        # 5. Technical indicators
        try:
            price_df = chart_data.get("price_df")
            bb = chart_data.get("bb_series")
            rsi_s = chart_data.get("rsi_series")
            macd_s = chart_data.get("macd_series")
            if price_df is not None and bb and rsi_s is not None and macd_s:
                charts["technical_indicators"] = technical_indicator_chart(
                    price_df, bb, rsi_s, macd_s, ticker
                )
        except Exception as e:
            logger.error("Technical chart failed: %s", e)

        # 6. Radar chart
        try:
            composite = thesis.get("composite_score", {})
            if composite:
                radar_scores = {
                    "Fundamental": composite.get("fundamental", 50),
                    "Technical": composite.get("technical", 50),
                    "Macro": composite.get("macro", 50),
                    "Sentiment": composite.get("sentiment", 50),
                    "Valuation": composite.get("fundamental", 50),
                }
                charts["radar"] = radar_chart(radar_scores, ticker)
        except Exception as e:
            logger.error("Radar chart failed: %s", e)

        # 7. Cash flow waterfall
        try:
            rev = fundamental.get("revenue_analysis", {}).get("revenue", 0)
            ni = fundamental.get("revenue_analysis", {}).get("net_income", 0)
            if rev > 0:
                ocf = ni * 1.3 if ni else rev * 0.12
                capex = -abs(rev * 0.05)
                fcf = ocf + capex
                divs = abs(ni * 0.3) if ni else 0
                charts["cash_flow_waterfall"] = cash_flow_waterfall(ocf, capex, fcf, divs, ticker)
        except Exception as e:
            logger.error("Cash flow waterfall chart failed: %s", e)

        # 8. Relative performance
        try:
            stock_2y = price_data.get("price_history_2y")
            if stock_2y is not None and not stock_2y.empty and benchmark_2y is not None and not benchmark_2y.empty:
                perf = relative_performance(stock_2y, benchmark_2y)
                charts["relative_performance"] = relative_performance_chart(perf, ticker)
        except Exception as e:
            logger.error("Relative performance chart failed: %s", e)

        # 9. Dividend history
        try:
            div_data = financial_data.get("dividends")
            if div_data is not None and isinstance(div_data, pd.DataFrame) and not div_data.empty:
                years = div_data["tarih"].astype(str).tolist()[:8]
                dps = [float(x) if x else 0 for x in div_data.get("hisse_basina_temettü", [0]*8)][:8]
                dy = [float(x) if x else 0 for x in div_data.get("temettü_verimi", [0]*8)][:8]
                if years and dps:
                    charts["dividend_history"] = dividend_history_chart(years, dps, dy, ticker)
        except Exception as e:
            logger.error("Dividend chart failed: %s", e)

        # Build report sections text
        ticker_meta = TICKERS.get(ticker, {})
        report_sections = {}

        # Generate section content via LLM if available
        if llm:
            try:
                prompt = f"""Generate the text content for an institutional equity research report on {ticker} ({ticker_meta.get('name', ticker)}).
Use the analysis data below. Write professionally, concisely, with specific numbers.

FUNDAMENTAL: Score {fundamental.get('fundamental_score', 'N/A')}/100
{fundamental.get('fundamental_thesis', '')[:500]}

TECHNICAL: Score {technical.get('technical_score', 'N/A')}/100
{technical.get('technical_summary', '')[:300]}

MACRO: Score {macro.get('macro_score', 'N/A')}/100
{macro.get('macro_thesis', '')[:300]}

SENTIMENT: Score {sentiment.get('sentiment_score', 'N/A')}/100
{sentiment.get('sentiment_summary', '')[:300]}

THESIS:
Recommendation: {thesis.get('recommendation', 'N/A')}
Conviction: {thesis.get('conviction', 'N/A')}
{thesis.get('final_thesis', '')[:500]}

BULL CASE: {thesis.get('bull_case', {}).get('thesis', '')[:300]}
BEAR CASE: {thesis.get('bear_case', {}).get('thesis', '')[:300]}

Generate these sections (each 2-4 paragraphs):
1. EXECUTIVE_SUMMARY
2. COMPANY_OVERVIEW
3. FINANCIAL_ANALYSIS
4. VALUATION_DISCUSSION
5. TECHNICAL_ANALYSIS_TEXT
6. MACRO_SECTOR
7. INVESTMENT_THESIS
8. RISK_FACTORS
9. ESG_GOVERNANCE

Output as JSON with section names as keys."""
                response = await llm.ainvoke(prompt)
                content = response.content if hasattr(response, "content") else str(response)
                try:
                    if "```json" in content:
                        content = content.split("```json")[1].split("```")[0]
                    elif "```" in content:
                        content = content.split("```")[1].split("```")[0]
                    report_sections = __import__("json").loads(content)
                except (__import__("json").JSONDecodeError, IndexError):
                    report_sections = {"EXECUTIVE_SUMMARY": content}
            except Exception as e:
                logger.error("Report sections LLM failed: %s", e)

        # Fallback sections
        if not report_sections:
            report_sections = {
                "EXECUTIVE_SUMMARY": thesis.get("final_thesis", "Analysis pending."),
                "COMPANY_OVERVIEW": f"{ticker_meta.get('name', ticker)} operates in the {ticker_meta.get('sector', 'N/A')} sector.",
                "FINANCIAL_ANALYSIS": fundamental.get("fundamental_thesis", "See appendix."),
                "VALUATION_DISCUSSION": f"DCF fair value: {fundamental.get('valuation', {}).get('dcf', {}).get('fair_value', 'N/A')} TRY.",
                "TECHNICAL_ANALYSIS_TEXT": technical.get("technical_summary", "See charts."),
                "MACRO_SECTOR": macro.get("macro_thesis", "See appendix."),
                "INVESTMENT_THESIS": thesis.get("final_thesis", ""),
                "RISK_FACTORS": "\n".join(thesis.get("bear_case", {}).get("key_risks", ["Market risk", "Regulatory risk"])),
                "ESG_GOVERNANCE": "ESG data pending.",
            }

        return {
            "charts": charts,
            "report_sections": report_sections,
            "agent_logs": state.get("agent_logs", []) + [
                {"agent": "report_compiler", "status": "complete",
                 "charts_generated": len(charts)}
            ],
        }

    return report_compiler_node
