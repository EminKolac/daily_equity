"""Quartr MCP fetcher — earnings transcripts + consensus (supplementary).

Note: Quartr MCP (https://mcp.quartr.com/mcp) is an optional supplementary source.
When not available, the pipeline gracefully degrades — earnings analysis uses
evofin activity reports and KAP disclosures instead.
"""

import logging
from typing import Any

from data.cache_utils import get_cached, set_cached

logger = logging.getLogger(__name__)


class QuartrFetcher:
    """Fetches earnings call data from Quartr MCP (supplementary source).

    The Quartr MCP endpoint is optional. When ``mcp_client`` is None or the
    endpoint is unreachable, all methods return empty defaults so the rest of
    the pipeline continues unaffected.
    """

    def __init__(self, mcp_client=None):
        self.mcp = mcp_client

    async def get_latest_transcript(self, ticker: str) -> str:
        """Get the latest earnings call transcript.

        Uses evofin document search as a proxy when Quartr MCP is unavailable:
        searches for the company's latest earnings-related disclosures.
        """
        if self.mcp:
            try:
                # Search evofin documents for earnings-related content
                result = await self.mcp.search_documents(
                    arama=f"{ticker} kazanç çağrısı faaliyet sonuçları",
                    sayfa=1,
                    sayfa_basi=3,
                )
                chunks = result.get("sonuclar", [])
                if chunks:
                    chunk_ids = [c["id"] for c in chunks[:2] if "id" in c]
                    if chunk_ids:
                        loaded = await self.mcp.load_chunks(ids=chunk_ids)
                        texts = [c.get("icerik", "") for c in loaded if isinstance(c, dict)]
                        return "\n\n".join(texts)
            except Exception as e:
                logger.debug("Quartr/evofin transcript search for %s: %s", ticker, e)
        return ""

    async def get_consensus_estimates(self, ticker: str) -> dict:
        """Get analyst consensus estimates.

        Falls back gracefully to empty dict — consensus data is also
        sourced from İş Yatırım coverage in the data_collector.
        """
        # Consensus estimates are primarily sourced from İş Yatırım coverage
        # and evofin analyst targets. This method is a supplementary source.
        return {}

    async def fetch_all(self, ticker: str) -> dict[str, Any]:
        cache_key = f"quartr_{ticker}"
        cached = get_cached(cache_key)
        if cached is not None:
            return cached
        logger.info("Fetching Quartr/supplementary data for %s", ticker)
        transcript = await self.get_latest_transcript(ticker)
        consensus = await self.get_consensus_estimates(ticker)
        result = {
            "earnings_transcript": transcript,
            "quartr_consensus": consensus,
        }
        set_cached(cache_key, result)
        return result
