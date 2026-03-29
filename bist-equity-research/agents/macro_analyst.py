"""Agent 4: Macro Analyst — macroeconomic overlay + sector context."""

import logging
from typing import Any

from config.tickers import TICKERS
from config.settings import MODEL

logger = logging.getLogger(__name__)


def create_macro_analyst(llm=None):
    """Factory: returns a macro analyst node."""

    async def macro_analyst_node(state: dict) -> dict:
        ticker = state["ticker"]
        logger.info("Macro Analyst: analyzing %s", ticker)

        macro_data = state.get("macro_data", {})
        company_profile = state.get("company_profile", {})
        ticker_meta = TICKERS.get(ticker, {})

        latest = macro_data.get("macro_latest", {})
        policy_rate = latest.get("policy_rate")
        cpi_yoy = latest.get("cpi_yoy")
        usd_try = latest.get("usd_try")
        eur_try = latest.get("eur_try")

        sector = ticker_meta.get("sector", "Unknown")
        fx_revenue_pct = ticker_meta.get("fx_revenue_pct", 0)

        # Generate analysis via LLM
        macro_thesis = ""
        macro_score = 50

        if llm:
            try:
                prompt = f"""You are a Turkish macro strategist. Given the macro data and sector context, assess:
1. How does the current macro environment affect {ticker_meta.get('name', ticker)}?
2. What macro headwinds/tailwinds exist for the next 12 months?
3. Rate the macro environment for this stock: Very Negative / Negative / Neutral / Positive / Very Positive
4. Assign a score from 0-100 (0 = worst macro for this stock, 100 = best)

Macro Data:
- TCMB Policy Rate: {policy_rate}%
- CPI YoY: {cpi_yoy}%
- USD/TRY: {usd_try}
- EUR/TRY: {eur_try}

Company Context:
- Sector: {sector}
- Sub-sector: {ticker_meta.get('sub_sector', 'N/A')}
- FX Revenue %: {fx_revenue_pct*100:.0f}%
- Company: {ticker_meta.get('name', ticker)}

Write a concise 3-paragraph macro assessment. End with the score in format: MACRO_SCORE: XX"""

                response = await llm.ainvoke(prompt)
                macro_thesis = response.content if hasattr(response, "content") else str(response)

                # Extract score
                if "MACRO_SCORE:" in macro_thesis:
                    score_str = macro_thesis.split("MACRO_SCORE:")[-1].strip().split()[0]
                    try:
                        macro_score = int(float(score_str))
                        macro_score = max(0, min(100, macro_score))
                    except ValueError:
                        pass
            except Exception as e:
                logger.error("LLM macro analysis failed: %s", e)

        if not macro_thesis:
            # Fallback heuristic
            macro_score = 50
            if policy_rate and policy_rate > 40:
                macro_score -= 10  # High rates negative
            if cpi_yoy and cpi_yoy < 30:
                macro_score += 5  # Declining inflation positive
            if fx_revenue_pct > 0.5 and usd_try and usd_try > 30:
                macro_score += 10  # FX earners benefit from weak TRY
            macro_thesis = (
                f"Turkey's policy rate at {policy_rate}% reflects a tight monetary stance. "
                f"CPI at {cpi_yoy}% YoY remains elevated. "
                f"USD/TRY at {usd_try} — {ticker} with {fx_revenue_pct*100:.0f}% FX revenue "
                f"{'benefits from' if fx_revenue_pct > 0.3 else 'has limited exposure to'} TRY depreciation."
            )
            macro_score = max(0, min(100, macro_score))

        return {
            "macro_analysis": {
                "rate_environment": {
                    "current_rate": policy_rate,
                    "trajectory": "Easing" if policy_rate and policy_rate < 50 else "Tight",
                    "impact": "High rates compress multiples and increase cost of debt",
                },
                "inflation_impact": {
                    "cpi_current": cpi_yoy,
                    "pricing_power": "Strong" if fx_revenue_pct > 0.3 else "Moderate",
                },
                "fx_exposure": {
                    "usd_try": usd_try,
                    "eur_try": eur_try,
                    "revenue_fx_pct": fx_revenue_pct,
                    "impact": "Positive" if fx_revenue_pct > 0.3 else "Neutral",
                },
                "sector_macro": {"sector": sector},
                "macro_score": macro_score,
                "macro_thesis": macro_thesis,
            },
            "agent_logs": state.get("agent_logs", []) + [
                {"agent": "macro_analyst", "status": "complete", "score": macro_score}
            ],
        }

    return macro_analyst_node
