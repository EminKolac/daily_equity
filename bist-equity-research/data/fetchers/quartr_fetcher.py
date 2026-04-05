"""Quartr MCP fetcher — earnings transcripts + consensus (supplementary).

Uses the Quartr MCP endpoint (mcp.quartr.com) for earnings call transcripts
and analyst consensus data. Falls back gracefully when MCP is unavailable.
"""

import logging
from typing import Any

from data.cache_utils import get_cached, set_cached

logger = logging.getLogger(__name__)


class QuartrFetcher:
    """Fetches earnings call data from Quartr MCP (supplementary source)."""

    def __init__(self, mcp_client=None):
        self.mcp = mcp_client

    async def get_latest_transcript(self, ticker: str) -> str:
        """Get the latest earnings call transcript via MCP SQL query."""
        if self.mcp:
            try:
                # Use the MCPClient's __call__ method (veri_sorgula pattern)
                result = await self.mcp(
                    sql=f"SELECT transcript FROM earnings_calls WHERE ticker = '{ticker}' ORDER BY date DESC LIMIT 1",
                    purpose=f"{ticker} latest earnings transcript",
                )
                if isinstance(result, dict) and result.get("table"):
                    return result["table"]
                if isinstance(result, str):
                    return result
                return ""
            except Exception as e:
                logger.warning("Quartr transcript unavailable for %s: %s", ticker, e)
        return ""

    async def get_consensus_estimates(self, ticker: str) -> dict:
        """Get analyst consensus estimates from Quartr via MCP."""
        if self.mcp:
            try:
                result = await self.mcp(
                    sql=f"SELECT * FROM consensus_estimates WHERE ticker = '{ticker}' ORDER BY date DESC LIMIT 10",
                    purpose=f"{ticker} consensus estimates",
                )
                if isinstance(result, dict):
                    return result
                return {}
            except Exception as e:
                logger.warning("Quartr consensus unavailable for %s: %s", ticker, e)
        return {}

    async def fetch_all(self, ticker: str) -> dict[str, Any]:
        cache_key = f"quartr_{ticker}"
        cached = get_cached(cache_key)
        if cached is not None:
            return cached
        logger.info("Fetching Quartr data for %s", ticker)
        transcript = await self.get_latest_transcript(ticker)
        consensus = await self.get_consensus_estimates(ticker)
        result = {
            "earnings_transcript": transcript,
            "quartr_consensus": consensus,
        }
        set_cached(cache_key, result)
        return result
