"""MCP adapter — provides a callable interface for evofin MCP tools.

When running inside Claude Code with MCP tools available, the adapter wraps
the tool calls. When running standalone (e.g., GitHub Actions), returns None
so fetchers fall back gracefully.

Usage in main.py:
    from data.fetchers.mcp_adapter import create_mcp_client
    mcp = create_mcp_client()  # Returns None if MCP unavailable
    state = await run_research_pipeline(ticker, llm, mcp_client=mcp)

Usage in evofin_fetcher.py:
    The mcp_client is expected to be a callable with:
        await mcp_client(sql=..., purpose=...) → MCP response dict
    Plus optional methods:
        mcp_client.search_documents(arama=..., sayfa=..., sayfa_basi=...)
        mcp_client.load_chunks(ids=[...])
        mcp_client.search_symbol(kod_ve_unvan=...)
"""

import logging

logger = logging.getLogger(__name__)


class MCPClient:
    """Adapter that wraps MCP tool callables into a unified interface.

    The __call__ method maps to veri_sorgula (SQL queries).
    """

    def __init__(self, veri_sorgula=None, dokumanlarda_ara=None,
                 dokuman_chunk_yukle=None, sembol_arama=None):
        self._veri_sorgula = veri_sorgula
        self._dokumanlarda_ara = dokumanlarda_ara
        self._dokuman_chunk_yukle = dokuman_chunk_yukle
        self._sembol_arama = sembol_arama

    async def __call__(self, sql: str, purpose: str = "") -> dict:
        """Execute SQL query via veri_sorgula."""
        if self._veri_sorgula:
            return await self._veri_sorgula(sql=sql, purpose=purpose)
        return {}

    async def search_documents(self, arama: str, sayfa: int = 1, sayfa_basi: int = 10) -> dict:
        if self._dokumanlarda_ara:
            return await self._dokumanlarda_ara(arama=arama, sayfa=sayfa, sayfa_basi=sayfa_basi)
        return {"sonuclar": [], "toplam": 0}

    async def load_chunks(self, ids: list[str]) -> list:
        if self._dokuman_chunk_yukle:
            return await self._dokuman_chunk_yukle(ids=ids)
        return []

    async def search_symbol(self, kod_ve_unvan: str):
        if self._sembol_arama:
            return await self._sembol_arama(kod_ve_unvan=kod_ve_unvan)
        return []

    def __bool__(self):
        return self._veri_sorgula is not None


def create_mcp_client(**tool_callables) -> MCPClient | None:
    """Create an MCP client from tool callables.

    Args:
        veri_sorgula: async callable for SQL queries
        dokumanlarda_ara: async callable for document search
        dokuman_chunk_yukle: async callable for loading document chunks
        sembol_arama: async callable for symbol search

    Returns:
        MCPClient if at least veri_sorgula is provided, else None.
    """
    if not tool_callables.get("veri_sorgula"):
        return None
    return MCPClient(**tool_callables)
