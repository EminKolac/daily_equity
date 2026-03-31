"""Quartr MCP fetcher — earnings transcripts + consensus (supplementary)."""

import logging
from typing import Any

logger = logging.getLogger(__name__)


class QuartrFetcher:
    """Fetches earnings call data from Quartr MCP (supplementary source)."""

    def __init__(self, mcp_client=None):
        self.mcp = mcp_client

    async def get_latest_transcript(self, ticker: str) -> str:
        """Get the latest earnings call transcript."""
        if self.mcp:
            try:
                result = await self.mcp.call_tool("quartr_transcript", {"ticker": ticker})
                if isinstance(result, dict):
                    return result.get("transcript", "")
                return str(result) if result else ""
            except Exception as e:
                logger.error("Quartr transcript failed for %s: %s", ticker, e)
        return ""

    async def get_consensus_estimates(self, ticker: str) -> dict:
        """Get analyst consensus estimates from Quartr."""
        if self.mcp:
            try:
                result = await self.mcp.call_tool("quartr_consensus", {"ticker": ticker})
                return result if isinstance(result, dict) else {}
            except Exception as e:
                logger.error("Quartr consensus failed for %s: %s", ticker, e)
        return {}

    async def fetch_all(self, ticker: str) -> dict[str, Any]:
        logger.info("Fetching Quartr data for %s", ticker)
        transcript = await self.get_latest_transcript(ticker)
        consensus = await self.get_consensus_estimates(ticker)
        return {
            "earnings_transcript": transcript,
            "quartr_consensus": consensus,
        }
