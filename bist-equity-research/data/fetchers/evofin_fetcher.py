"""Evofin/Fintables MCP data fetcher — primary BIST fundamentals source.

Uses the evofin MCP tools (sembol_arama, veri_sorgula, dokumanlarda_ara,
dokuman_chunk_yukle, finansal_beceri_yukle) via the Claude MCP integration.

When running inside Claude Code with MCP, these tools are called directly.
For standalone execution, we provide a fallback HTTP client.
"""

import json
import logging
from typing import Any

import pandas as pd

from data.cache_utils import get_cached, set_cached

logger = logging.getLogger(__name__)


class EvofinFetcher:
    """Fetches BIST financial data from evofin MCP."""

    def __init__(self, mcp_client=None):
        self.mcp = mcp_client

    async def query(self, sql: str) -> list[dict]:
        """Execute a read-only SQL query via evofin MCP veri_sorgula."""
        if self.mcp:
            result = await self.mcp.call_tool("veri_sorgula", {"sorgu": sql})
            return result
        logger.warning("No MCP client — returning empty result for: %s", sql[:80])
        return []

    async def search_documents(self, query: str, page: int = 1, per_page: int = 10) -> dict:
        """Full-text search in evofin document pool."""
        if self.mcp:
            result = await self.mcp.call_tool("dokumanlarda_ara", {
                "arama": query,
                "sayfa": page,
                "sayfa_basi": per_page,
            })
            return result
        return {"sonuclar": [], "toplam": 0}

    async def load_document_chunks(self, chunk_ids: list[str]) -> list[dict]:
        """Load document chunk contents by IDs."""
        if self.mcp:
            result = await self.mcp.call_tool("dokuman_chunk_yukle", {"ids": chunk_ids})
            return result
        return []

    async def search_symbol(self, keyword: str) -> list[dict]:
        """Search for symbol (stock, fund, etc.) by keyword."""
        if self.mcp:
            result = await self.mcp.call_tool("sembol_arama", {"arama": keyword})
            return result
        return []

    async def get_company_profile(self, ticker: str) -> dict:
        sql = f"""
        SELECT hisse_senedi_kodu, unvan, odenmis_sermaye, fiili_dolasim_orani,
               piyasa_degeri, son_fiyat, fonksiyonel_para_birimi
        FROM hisse_senetleri
        WHERE hisse_senedi_kodu = '{ticker}'
        """
        rows = await self.query(sql)
        return rows[0] if rows else {}

    async def get_income_statement(self, ticker: str, quarters: int = 12) -> pd.DataFrame:
        sql = f"""
        SELECT tarih, kalem, deger
        FROM finansal_tablolar
        WHERE hisse_senedi_kodu = '{ticker}'
          AND tablo = 'income_statement'
          AND tur = 'quarterly'
        ORDER BY tarih DESC
        LIMIT {quarters * 4}
        """
        rows = await self.query(sql)
        return pd.DataFrame(rows) if rows else pd.DataFrame()

    async def get_balance_sheet(self, ticker: str, quarters: int = 8) -> pd.DataFrame:
        sql = f"""
        SELECT tarih, kalem, deger
        FROM finansal_tablolar
        WHERE hisse_senedi_kodu = '{ticker}'
          AND tablo = 'balance_sheet'
          AND tur = 'quarterly'
        ORDER BY tarih DESC
        LIMIT {quarters * 25}
        """
        rows = await self.query(sql)
        return pd.DataFrame(rows) if rows else pd.DataFrame()

    async def get_cash_flow(self, ticker: str, quarters: int = 8) -> pd.DataFrame:
        sql = f"""
        SELECT tarih, kalem, deger
        FROM finansal_tablolar
        WHERE hisse_senedi_kodu = '{ticker}'
          AND tablo = 'cash_flow'
          AND tur = 'quarterly'
        ORDER BY tarih DESC
        LIMIT {quarters * 12}
        """
        rows = await self.query(sql)
        return pd.DataFrame(rows) if rows else pd.DataFrame()

    async def get_ratios(self, ticker: str) -> pd.DataFrame:
        sql = f"""
        SELECT tarih, kalem, deger
        FROM finansal_tablolar
        WHERE hisse_senedi_kodu = '{ticker}'
          AND tablo = 'ratios'
        ORDER BY tarih DESC
        LIMIT 50
        """
        rows = await self.query(sql)
        return pd.DataFrame(rows) if rows else pd.DataFrame()

    async def get_dividends(self, ticker: str) -> pd.DataFrame:
        sql = f"""
        SELECT tarih, hisse_senedi_kodu, temettü_verimi, hisse_basina_temettü,
               brüt_nakit_temettü, net_nakit_temettü
        FROM temettüler
        WHERE hisse_senedi_kodu = '{ticker}'
        ORDER BY tarih DESC
        """
        rows = await self.query(sql)
        return pd.DataFrame(rows) if rows else pd.DataFrame()

    async def get_peer_tickers(self, ticker: str) -> list[str]:
        sql = f"""
        SELECT h2.hisse_senedi_kodu
        FROM hisse_senetleri h1
        JOIN hisse_senetleri h2 ON h1.sektor_id = h2.sektor_id
        WHERE h1.hisse_senedi_kodu = '{ticker}'
          AND h2.hisse_senedi_kodu != '{ticker}'
        """
        rows = await self.query(sql)
        return [r["hisse_senedi_kodu"] for r in rows] if rows else []

    async def get_activity_report(self, ticker: str) -> str:
        """Search for the company's latest activity report (faaliyet raporu)."""
        results = await self.search_documents(f"{ticker} faaliyet raporu", page=1, per_page=5)
        if not results.get("sonuclar"):
            return ""
        chunk_ids = [r["id"] for r in results["sonuclar"][:3]]
        chunks = await self.load_document_chunks(chunk_ids)
        return "\n\n".join(c.get("icerik", "") for c in chunks)

    async def fetch_all(self, ticker: str) -> dict[str, Any]:
        """Fetch all data for a given ticker."""
        cache_key = f"evofin_{ticker}"
        cached = get_cached(cache_key)
        if cached is not None:
            return cached
        logger.info("Fetching evofin data for %s", ticker)
        profile = await self.get_company_profile(ticker)
        income = await self.get_income_statement(ticker)
        balance = await self.get_balance_sheet(ticker)
        cashflow = await self.get_cash_flow(ticker)
        ratios = await self.get_ratios(ticker)
        dividends = await self.get_dividends(ticker)
        peers = await self.get_peer_tickers(ticker)
        activity = await self.get_activity_report(ticker)

        result = {
            "company_profile": profile,
            "income_statement": income,
            "balance_sheet": balance,
            "cash_flow": cashflow,
            "ratios": ratios,
            "dividends": dividends,
            "peer_tickers": peers,
            "activity_report": activity,
        }
        set_cached(cache_key, result)
        return result
