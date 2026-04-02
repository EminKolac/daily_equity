"""Agent 1: Data Collector — multi-source data acquisition, no analysis."""

import asyncio
import logging
from typing import Any

from data.fetchers.evofin_fetcher import EvofinFetcher
from data.fetchers.yahoo_fetcher import YahooFetcher
from data.fetchers.isyatirim_fetcher import IsYatirimFetcher
from data.fetchers.tcmb_fetcher import TCMBFetcher
from data.fetchers.twitter_fetcher import TwitterFetcher
from data.fetchers.kap_fetcher import KAPFetcher
from data.fetchers.quartr_fetcher import QuartrFetcher

logger = logging.getLogger(__name__)


def _build_coverage_from_evofin(analyst_targets: list[dict]) -> dict:
    """Convert evofin analyst_targets to the coverage format expected by sentiment_analyst.

    Evofin returns: [{araci_kurum_kodu, kisa_unvan, hedef_fiyat, tavsiye, yayin_tarihi_europe_istanbul}]
    Sentiment analyst expects: {recommendations: [{recommendation, targetPrice, ...}]}
    """
    if not analyst_targets:
        return {}
    recs = []
    for t in analyst_targets:
        tavsiye = str(t.get("tavsiye", "")).lower()
        # Map Turkish recommendation to standard
        if tavsiye in ("al", "güçlü al", "endeks_ustu"):
            rec = "Buy"
        elif tavsiye in ("sat", "güçlü sat", "endeks_alti"):
            rec = "Sell"
        else:
            rec = "Hold"
        recs.append({
            "recommendation": rec,
            "targetPrice": float(t.get("hedef_fiyat", 0) or 0),
            "broker": t.get("kisa_unvan", t.get("araci_kurum_kodu", "")),
            "date": str(t.get("yayin_tarihi_europe_istanbul", "")),
        })
    return {"recommendations": recs}


def create_data_collector(mcp_client=None):
    """Factory: returns a data collector node function."""

    evofin = EvofinFetcher(mcp_client=mcp_client)
    yahoo = YahooFetcher()
    isyatirim = IsYatirimFetcher()
    tcmb = TCMBFetcher()
    twitter = TwitterFetcher()
    kap = KAPFetcher()
    quartr = QuartrFetcher(mcp_client=mcp_client)

    async def data_collector_node(state: dict) -> dict:
        """Fetch all data for the given ticker."""
        ticker = state["ticker"]
        logger.info("Data Collector: fetching all data for %s", ticker)
        errors = list(state.get("errors", []))

        collected = {}

        # Async fetchers (evofin, quartr)
        try:
            evofin_data = await evofin.fetch_all(ticker)
            collected.update(evofin_data)
        except Exception as e:
            logger.error("Evofin fetch failed: %s", e)
            errors.append(f"evofin: {e}")

        try:
            quartr_data = await quartr.fetch_all(ticker)
            collected.update(quartr_data)
        except Exception as e:
            logger.error("Quartr fetch failed: %s", e)
            errors.append(f"quartr: {e}")

        # Sync fetchers (run in thread pool)
        loop = asyncio.get_event_loop()

        try:
            yahoo_data = await loop.run_in_executor(None, yahoo.fetch_all, ticker)
            collected.update(yahoo_data)
        except Exception as e:
            logger.error("Yahoo fetch failed: %s", e)
            errors.append(f"yahoo: {e}")

        try:
            isy_data = await loop.run_in_executor(None, isyatirim.fetch_all, ticker)
            collected.update(isy_data)
        except Exception as e:
            logger.error("İş Yatırım fetch failed: %s", e)
            errors.append(f"isyatirim: {e}")

        try:
            tcmb_data = await loop.run_in_executor(None, tcmb.fetch_all)
            collected.update(tcmb_data)
        except Exception as e:
            logger.error("TCMB fetch failed: %s", e)
            errors.append(f"tcmb: {e}")

        try:
            twitter_data = await loop.run_in_executor(None, twitter.fetch_all, ticker)
            collected.update(twitter_data)
        except Exception as e:
            logger.error("Twitter/Apify fetch failed: %s", e)
            errors.append(f"twitter: {e}")

        try:
            kap_data = await loop.run_in_executor(None, kap.fetch_all, ticker)
            collected.update(kap_data)
        except Exception as e:
            logger.error("KAP fetch failed: %s", e)
            errors.append(f"kap: {e}")

        # Build output state
        update = {
            "company_profile": collected.get("company_profile", {}),
            "financial_data": {
                "income_statement": collected.get("income_statement"),
                "balance_sheet": collected.get("balance_sheet"),
                "cash_flow": collected.get("cash_flow"),
                "ratios": collected.get("ratios"),
                "dividends": collected.get("dividends"),
                "activity_report": collected.get("activity_report", ""),
            },
            "price_data": {
                "price_history_2y": collected.get("price_history_2y"),
                "price_history_5y": collected.get("price_history_5y"),
                "stock_info": collected.get("stock_info", {}),
                "yahoo_dividends": collected.get("yahoo_dividends"),
            },
            "macro_data": {
                "macro_series": collected.get("macro_series", {}),
                "macro_latest": collected.get("macro_latest", {}),
            },
            "earnings_data": {
                "earnings_transcript": collected.get("earnings_transcript", ""),
                "quartr_consensus": collected.get("quartr_consensus", {}),
            },
            "isyatirim_coverage": collected.get("isyatirim_coverage", {})
                if collected.get("isyatirim_coverage") else
                _build_coverage_from_evofin(collected.get("analyst_targets", [])),
            "social_media_data": {
                "twitter_tweets": collected.get("twitter_tweets", []),
                "twitter_count": collected.get("twitter_count", 0),
            },
            "benchmark_2y": collected.get("benchmark_2y"),
            "peer_tickers": collected.get("peer_tickers", []),
            "isyatirim_financials": collected.get("isyatirim_financials"),
            "kap_disclosures": collected.get("kap_disclosures", []),
            "errors": errors,
            "agent_logs": state.get("agent_logs", []) + [
                {"agent": "data_collector", "status": "complete", "errors": len(errors)}
            ],
        }
        logger.info("Data Collector: complete for %s (%d errors)", ticker, len(errors))
        return update

    return data_collector_node
