"""Agent 6: Thesis Writer — bull/bear debate + investment thesis synthesis."""

import json
import logging
from typing import Any

from analysis.scoring import composite_score
from config.settings import MODEL

logger = logging.getLogger(__name__)


def create_thesis_writer(llm=None):
    """Factory: returns a thesis writer node with bull-bear debate."""

    async def thesis_writer_node(state: dict) -> dict:
        ticker = state["ticker"]
        logger.info("Thesis Writer: synthesizing thesis for %s", ticker)

        fundamental = state.get("fundamental_analysis", {})
        technical = state.get("technical_analysis", {})
        macro = state.get("macro_analysis", {})
        sentiment = state.get("sentiment_analysis", {})

        # Composite scoring
        scores = {
            "fundamental": fundamental.get("fundamental_score", 50),
            "technical": technical.get("technical_score", 50),
            "macro": macro.get("macro_score", 50),
            "sentiment": sentiment.get("sentiment_score", 50),
        }
        comp = composite_score(scores)

        current_price = fundamental.get("valuation", {}).get("current_price", 0)
        ff = fundamental.get("valuation", {}).get("football_field", {})

        if not llm:
            # Fallback without LLM
            return {
                "investment_thesis": {
                    "bull_case": {"thesis": "N/A", "key_drivers": [], "upside_target": 0},
                    "bear_case": {"thesis": "N/A", "key_risks": [], "downside_target": 0},
                    "debate_summary": "LLM not available for thesis generation.",
                    "final_thesis": "Analysis incomplete.",
                    "conviction": comp["conviction"],
                    "composite_score": {**scores, "overall": comp["overall"]},
                    "catalysts": [],
                    "risk_reward_ratio": 1.0,
                    "recommendation": comp["recommendation"],
                },
                "agent_logs": state.get("agent_logs", []) + [
                    {"agent": "thesis_writer", "status": "no_llm"}
                ],
            }

        # Data summary for prompts
        data_summary = f"""
COMPANY: {ticker}
CURRENT PRICE: {current_price} TRY

FUNDAMENTAL:
- Score: {fundamental.get('fundamental_score', 'N/A')}/100
- Thesis: {fundamental.get('fundamental_thesis', 'N/A')[:500]}
- DCF Fair Value: {fundamental.get('valuation', {}).get('dcf', {}).get('fair_value', 'N/A')}
- P/E: {fundamental.get('valuation', {}).get('pe', 'N/A')}
- Piotroski F-Score: {fundamental.get('financial_health', {}).get('piotroski_f', {}).get('score', 'N/A')}
- Football Field: {ff.get('composite', 'N/A')}

TECHNICAL:
- Score: {technical.get('technical_score', 'N/A')}/100
- Summary: {technical.get('technical_summary', 'N/A')[:300]}
- Key Levels: {technical.get('key_levels', {})}

MACRO:
- Score: {macro.get('macro_score', 'N/A')}/100
- Thesis: {macro.get('macro_thesis', 'N/A')[:300]}

SENTIMENT:
- Score: {sentiment.get('sentiment_score', 'N/A')}/100
- Summary: {sentiment.get('sentiment_summary', 'N/A')[:300]}
- Consensus: {sentiment.get('analyst_consensus', {})}
"""

        # Step 1: Bull case
        try:
            bull_prompt = f"""You must argue the strongest possible bullish case for {ticker}.
Use specific data points from the analysis. Be quantitative. Include an upside target price.

{data_summary}

Output as JSON: {{"thesis": "...", "key_drivers": [...3 items...], "upside_target": float}}"""
            bull_resp = await llm.ainvoke(bull_prompt)
            bull_text = bull_resp.content if hasattr(bull_resp, "content") else str(bull_resp)
        except Exception as e:
            logger.error("Bull case LLM failed: %s", e)
            bull_text = '{"thesis": "Data unavailable", "key_drivers": [], "upside_target": 0}'

        # Step 2: Bear case
        try:
            bear_prompt = f"""You must argue the strongest possible bearish case for {ticker}.
Counter every bull argument with data. Identify what could go wrong. Include a downside target.

{data_summary}

Bull case argued: {bull_text[:500]}

Output as JSON: {{"thesis": "...", "key_risks": [...3 items...], "downside_target": float}}"""
            bear_resp = await llm.ainvoke(bear_prompt)
            bear_text = bear_resp.content if hasattr(bear_resp, "content") else str(bear_resp)
        except Exception as e:
            logger.error("Bear case LLM failed: %s", e)
            bear_text = '{"thesis": "Data unavailable", "key_risks": [], "downside_target": 0}'

        # Step 3: Debate synthesis
        try:
            synthesis_prompt = f"""Given the bull and bear arguments for {ticker}:

BULL CASE:
{bull_text[:800]}

BEAR CASE:
{bear_text[:800]}

COMPOSITE SCORES:
- Overall: {comp['overall']}/100
- Recommendation: {comp['recommendation']}
- Conviction: {comp['conviction']}

Synthesize a balanced investment thesis. Output as JSON:
{{
    "debate_summary": "2-3 sentence debate summary",
    "final_thesis": "3-4 sentence final investment thesis",
    "catalysts": ["catalyst1", "catalyst2", "catalyst3"],
    "risk_reward_ratio": float (>1 = favorable),
    "conviction": "High/Medium/Low"
}}"""
            synth_resp = await llm.ainvoke(synthesis_prompt)
            synth_text = synth_resp.content if hasattr(synth_resp, "content") else str(synth_resp)
        except Exception as e:
            logger.error("Synthesis LLM failed: %s", e)
            synth_text = '{"debate_summary": "", "final_thesis": "", "catalysts": [], "risk_reward_ratio": 1.0, "conviction": "Low"}'

        # Parse JSON outputs
        def parse_json(text: str) -> dict:
            try:
                if "```json" in text:
                    text = text.split("```json")[1].split("```")[0]
                elif "```" in text:
                    text = text.split("```")[1].split("```")[0]
                return json.loads(text)
            except (json.JSONDecodeError, IndexError):
                return {}

        bull_parsed = parse_json(bull_text)
        bear_parsed = parse_json(bear_text)
        synth_parsed = parse_json(synth_text)

        return {
            "investment_thesis": {
                "bull_case": {
                    "thesis": bull_parsed.get("thesis", bull_text[:500]),
                    "key_drivers": bull_parsed.get("key_drivers", []),
                    "upside_target": bull_parsed.get("upside_target", 0),
                },
                "bear_case": {
                    "thesis": bear_parsed.get("thesis", bear_text[:500]),
                    "key_risks": bear_parsed.get("key_risks", []),
                    "downside_target": bear_parsed.get("downside_target", 0),
                },
                "debate_summary": synth_parsed.get("debate_summary", ""),
                "final_thesis": synth_parsed.get("final_thesis", ""),
                "conviction": synth_parsed.get("conviction", comp["conviction"]),
                "composite_score": {**scores, "overall": comp["overall"]},
                "catalysts": synth_parsed.get("catalysts", []),
                "risk_reward_ratio": synth_parsed.get("risk_reward_ratio", 1.0),
                "recommendation": comp["recommendation"],
            },
            "agent_logs": state.get("agent_logs", []) + [
                {"agent": "thesis_writer", "status": "complete",
                 "recommendation": comp["recommendation"]}
            ],
        }

    return thesis_writer_node
