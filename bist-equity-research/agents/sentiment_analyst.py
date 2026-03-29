"""Agent 5: Sentiment Analyst — earnings, consensus, news, Twitter commentary."""

import json
import logging
from typing import Any

from config.settings import MODEL

logger = logging.getLogger(__name__)


def create_sentiment_analyst(llm=None):
    """Factory: returns a sentiment analyst node."""

    async def sentiment_analyst_node(state: dict) -> dict:
        ticker = state["ticker"]
        logger.info("Sentiment Analyst: analyzing %s", ticker)

        earnings_data = state.get("earnings_data", {})
        isyatirim_coverage = state.get("isyatirim_coverage", {})
        social_media_data = state.get("social_media_data", {})
        kap_disclosures = state.get("kap_disclosures", [])

        transcript = earnings_data.get("earnings_transcript", "")
        quartr_consensus = earnings_data.get("quartr_consensus", {})
        tweets = social_media_data.get("twitter_tweets", [])

        # Channel 1: Earnings tone
        management_tone = "Neutral"
        guidance_changes = []
        key_quotes = []
        red_flags = []

        if transcript and llm:
            try:
                prompt = f"""You are an expert at analyzing earnings call transcripts. Given the transcript below:
1. Rate management's tone: Very Negative / Negative / Neutral / Positive / Very Positive
2. Extract the top 3 guidance changes or forward-looking statements
3. Identify any red flags (hedging language, topic avoidance, analyst pushback)
4. Extract 2 key quotes

Transcript (abbreviated): {transcript[:3000]}

Output as JSON: {{"tone": "...", "guidance": [...], "red_flags": [...], "key_quotes": [...]}}"""
                response = await llm.ainvoke(prompt)
                content = response.content if hasattr(response, "content") else str(response)
                # Try to parse JSON from response
                try:
                    # Find JSON block
                    if "```json" in content:
                        content = content.split("```json")[1].split("```")[0]
                    elif "```" in content:
                        content = content.split("```")[1].split("```")[0]
                    parsed = json.loads(content)
                    management_tone = parsed.get("tone", "Neutral")
                    guidance_changes = parsed.get("guidance", [])
                    red_flags = parsed.get("red_flags", [])
                    key_quotes = parsed.get("key_quotes", [])
                except (json.JSONDecodeError, IndexError):
                    pass
            except Exception as e:
                logger.error("Earnings analysis LLM failed: %s", e)

        # Channel 2: Analyst consensus
        coverage = isyatirim_coverage
        buy_count = 0
        hold_count = 0
        sell_count = 0
        avg_target = 0
        high_target = 0
        low_target = 0

        if isinstance(coverage, dict):
            recs = coverage.get("recommendations", coverage.get("value", []))
            if isinstance(recs, list):
                for rec in recs:
                    r = str(rec.get("recommendation", "")).lower()
                    if "buy" in r or "al" in r:
                        buy_count += 1
                    elif "sell" in r or "sat" in r:
                        sell_count += 1
                    else:
                        hold_count += 1
                    tp = rec.get("targetPrice", rec.get("target", 0))
                    if tp:
                        targets = [t for t in [tp] if t > 0]
                        if targets:
                            if not avg_target:
                                avg_target = sum(targets) / len(targets)
                            high_target = max(high_target, max(targets))
                            low_target = min(low_target, min(targets)) if low_target else min(targets)

        current_price = state.get("fundamental_analysis", {}).get("valuation", {}).get("current_price", 0)
        target_vs_current = (
            round((avg_target / current_price - 1) * 100, 1) if avg_target and current_price else 0
        )

        # Channel 3: Twitter/X commentary (qualitative only)
        twitter_commentary = {
            "label": "Neutral",
            "confidence": 0.0,
            "top_themes": [],
            "tweet_count": len(tweets),
            "retail_vs_analyst_gap": "N/A",
            "verified_sentiment": "Neutral",
            "narrative_summary": "No Twitter data available.",
            "source": "apify",
        }

        if tweets and llm:
            try:
                sorted_tweets = sorted(tweets, key=lambda t: t.get("likes", 0), reverse=True)[:30]
                tweets_text = json.dumps(sorted_tweets[:20], ensure_ascii=False, default=str)

                prompt = f"""You are a Turkish financial social media analyst. Analyze the following tweets about {ticker} scraped from X/Twitter via Apify.

Your output will be used as a QUALITATIVE COMMENTARY in the report, not as a numerical score input.

For each tweet batch:
1. Classify overall sentiment: Very Bearish / Bearish / Neutral / Bullish / Very Bullish
2. Identify recurring themes
3. Weight by engagement: tweets with >100 likes from accounts with >10k followers are "high-signal"
4. Separate verified/Blue accounts from retail — flag sentiment divergence
5. Write a 2-3 sentence narrative summary suitable for an equity research report

Tweets (sorted by engagement):
{tweets_text}

Output as JSON: {{"label": "...", "confidence": 0.X, "top_themes": [...], "retail_vs_analyst_gap": "...", "verified_sentiment": "...", "narrative_summary": "..."}}"""

                response = await llm.ainvoke(prompt)
                content = response.content if hasattr(response, "content") else str(response)
                try:
                    if "```json" in content:
                        content = content.split("```json")[1].split("```")[0]
                    elif "```" in content:
                        content = content.split("```")[1].split("```")[0]
                    parsed = json.loads(content)
                    twitter_commentary.update(parsed)
                    twitter_commentary["tweet_count"] = len(tweets)
                    twitter_commentary["source"] = "apify"
                except (json.JSONDecodeError, IndexError):
                    pass
            except Exception as e:
                logger.error("Twitter sentiment LLM failed: %s", e)

        # Channel 4: News sentiment (KAP)
        news_sentiment = "Neutral"
        if kap_disclosures and llm:
            try:
                kap_text = json.dumps(kap_disclosures[:10], ensure_ascii=False, default=str)
                prompt = f"""Classify the overall sentiment of these KAP disclosures for {ticker}:
{kap_text}
Output one word: Very Negative / Negative / Neutral / Positive / Very Positive"""
                response = await llm.ainvoke(prompt)
                news_sentiment = (response.content if hasattr(response, "content") else str(response)).strip()
            except Exception as e:
                logger.error("News sentiment LLM failed: %s", e)

        # Sentiment fusion (3 channels, NOT Twitter)
        tone_scores = {
            "Very Positive": 90, "Positive": 70, "Neutral": 50,
            "Negative": 30, "Very Negative": 10,
        }
        earnings_score = tone_scores.get(management_tone, 50)

        consensus_score = 50
        total_recs = buy_count + hold_count + sell_count
        if total_recs > 0:
            consensus_score = int((buy_count * 90 + hold_count * 50 + sell_count * 10) / total_recs)
        if target_vs_current > 20:
            consensus_score += 10
        elif target_vs_current < -10:
            consensus_score -= 10

        news_score = tone_scores.get(news_sentiment, 50)

        sentiment_score = round(
            0.35 * earnings_score +
            0.35 * consensus_score +
            0.30 * news_score
        )
        sentiment_score = max(0, min(100, sentiment_score))

        # Summary
        sentiment_summary = ""
        if llm:
            try:
                prompt = f"""Write a 2-sentence sentiment summary for {ticker}:
- Management tone: {management_tone}
- Analyst consensus: {buy_count} Buy, {hold_count} Hold, {sell_count} Sell. Avg target: {avg_target:.2f} ({target_vs_current:+.1f}% vs current)
- News (KAP): {news_sentiment}
- Twitter: {twitter_commentary.get('narrative_summary', 'N/A')}
Sentiment Score: {sentiment_score}/100"""
                response = await llm.ainvoke(prompt)
                sentiment_summary = response.content if hasattr(response, "content") else str(response)
            except Exception as e:
                logger.error("Sentiment summary LLM failed: %s", e)

        if not sentiment_summary:
            sentiment_summary = (
                f"Analyst consensus is {buy_count}B/{hold_count}H/{sell_count}S "
                f"with avg target implying {target_vs_current:+.1f}% upside. "
                f"Management tone is {management_tone.lower()}. News sentiment: {news_sentiment.lower()}."
            )

        return {
            "sentiment_analysis": {
                "management_tone": management_tone,
                "guidance_changes": guidance_changes,
                "key_quotes": key_quotes,
                "red_flags": red_flags,
                "analyst_consensus": {
                    "buy": buy_count,
                    "hold": hold_count,
                    "sell": sell_count,
                    "avg_target": round(avg_target, 2),
                    "high_target": round(high_target, 2),
                    "low_target": round(low_target, 2),
                    "target_vs_current": target_vs_current,
                    "source": "isyatirim+quartr",
                },
                "twitter_commentary": twitter_commentary,
                "news_sentiment": news_sentiment,
                "sentiment_score": sentiment_score,
                "sentiment_summary": sentiment_summary,
            },
            "agent_logs": state.get("agent_logs", []) + [
                {"agent": "sentiment_analyst", "status": "complete", "score": sentiment_score}
            ],
        }

    return sentiment_analyst_node
