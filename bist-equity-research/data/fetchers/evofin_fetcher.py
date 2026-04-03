"""Evofin/Fintables MCP data fetcher — primary BIST fundamentals source.

Uses the evofin MCP tools (sembol_arama, veri_sorgula, dokumanlarda_ara,
dokuman_chunk_yukle, finansal_beceri_yukle) via the Claude MCP integration.

Real evofin schema (validated April 2026):
  - hisse_senetleri: company profile (hisse_senedi_kodu, unvan, piyasa_degeri, son_fiyat, ...)
  - hisse_finansal_tablolari: periods index (hisse_senedi_kodu, yil, ay)
  - hisse_finansal_tablolari_gelir_tablosu_kalemleri: income statement items
  - hisse_finansal_tablolari_bilanco_kalemleri: balance sheet items
  - hisse_finansal_tablolari_nakit_akis_tablosu_kalemleri: cash flow items
  - hisse_finansal_tablolari_finansal_oranlari: financial ratios
  - hisse_senedi_araci_kurum_hedef_fiyatlari: analyst target prices
  - mumlar_gunluk_gh: daily OHLCV candles

MCP response format:
  {"row_count": N, "table": "| col1 | col2 |\n| --- | --- |\n| val1 | val2 |", "notes": [], "canonical_sql": "..."}
  The 'table' field is a markdown table string that must be parsed into list[dict].

All financial item tables use: hisse_senedi_kodu, yil, ay, kalem, try_donemsel
Output is normalized to: tarih (YYYY-MM), kalem, deger — for downstream compatibility.
"""

import logging
import re
from typing import Any

import pandas as pd

from data.cache_utils import get_cached, set_cached

logger = logging.getLogger(__name__)


def _parse_markdown_table(response: Any) -> list[dict]:
    """Parse evofin MCP response into list of dicts.

    The MCP returns either:
      1. A dict with {"row_count": N, "table": "markdown string", ...}
      2. A raw markdown table string
      3. Already a list[dict] (pass through)
    """
    if isinstance(response, list):
        return response

    if isinstance(response, str):
        table_str = response
    elif isinstance(response, dict):
        if "table" in response:
            table_str = response["table"]
        else:
            return [response]
    else:
        logger.warning("Unexpected MCP response type: %s", type(response))
        return []

    if not table_str or not isinstance(table_str, str):
        return []

    lines = [line.strip() for line in table_str.strip().split("\n") if line.strip()]

    if len(lines) < 3:
        return []

    # Parse header row: "| col1 | col2 | col3 |"
    header_line = lines[0]
    headers = [h.strip() for h in header_line.split("|") if h.strip()]

    # Skip separator row (line[1]): "| --- | --- | --- |"
    # Parse data rows starting from line[2]
    rows = []
    for line in lines[2:]:
        values = [v.strip() for v in line.split("|") if v.strip() != ""]
        # Handle lines that are just "| |" separators
        if not values:
            continue
        # Pad or truncate to match header count
        while len(values) < len(headers):
            values.append("")
        values = values[:len(headers)]

        row = {}
        for header, value in zip(headers, values):
            # Convert numeric strings
            if value == "" or value is None:
                row[header] = None
            else:
                try:
                    # Try int first, then float
                    if "." in value or "e" in value.lower():
                        row[header] = float(value)
                    else:
                        row[header] = int(value)
                except (ValueError, TypeError):
                    row[header] = value
        rows.append(row)

    return rows


class EvofinFetcher:
    """Fetches BIST financial data from evofin MCP."""

    def __init__(self, mcp_client=None):
        self.mcp = mcp_client

    async def query(self, sql: str, purpose: str = "") -> list[dict]:
        """Execute a read-only SQL query via evofin MCP veri_sorgula."""
        if self.mcp:
            try:
                result = await self.mcp(sql=sql, purpose=purpose)
                return _parse_markdown_table(result)
            except Exception as e:
                logger.error("MCP query failed: %s", e)
                return []
        logger.warning("No MCP client — returning empty result for: %s", sql[:80])
        return []

    async def search_documents(self, query_text: str, page: int = 1, per_page: int = 10) -> dict:
        """Full-text search in evofin document pool."""
        if self.mcp:
            try:
                result = await self.mcp.search_documents(
                    arama=query_text, sayfa=page, sayfa_basi=per_page,
                )
                return result if isinstance(result, dict) else {"sonuclar": [], "toplam": 0}
            except Exception as e:
                logger.error("MCP document search failed: %s", e)
        return {"sonuclar": [], "toplam": 0}

    async def load_document_chunks(self, chunk_ids: list[str]) -> list[dict]:
        """Load document chunk contents by IDs."""
        if self.mcp:
            try:
                result = await self.mcp.load_chunks(ids=chunk_ids)
                return result if isinstance(result, list) else []
            except Exception as e:
                logger.error("MCP chunk load failed: %s", e)
        return []

    async def search_symbol(self, keyword: str) -> list[dict]:
        """Search for symbol (stock, fund, etc.) by keyword."""
        if self.mcp:
            try:
                result = await self.mcp.search_symbol(kod_ve_unvan=keyword)
                return _parse_markdown_table(result) if result else []
            except Exception as e:
                logger.error("MCP symbol search failed: %s", e)
        return []

    def _normalize_financials(self, rows: list[dict]) -> pd.DataFrame:
        """Normalize evofin financial rows (yil/ay/kalem/try_donemsel)
        into downstream-compatible format (tarih/kalem/deger)."""
        if not rows:
            return pd.DataFrame(columns=["tarih", "kalem", "deger"])

        records = []
        for r in rows:
            yil = r.get("yil", "")
            ay = r.get("ay", 0)
            try:
                tarih = f"{yil}-{int(ay):02d}"
            except (ValueError, TypeError):
                tarih = f"{yil}-00"
            records.append({
                "tarih": tarih,
                "kalem": r.get("kalem", ""),
                "deger": r.get("try_donemsel"),
            })
        df = pd.DataFrame(records)
        return df

    def _normalize_ratios(self, rows: list[dict]) -> pd.DataFrame:
        """Normalize evofin ratio rows (yil/ay/kategori/oran/deger)
        into downstream-compatible format (tarih/kalem/deger)."""
        if not rows:
            return pd.DataFrame(columns=["tarih", "kalem", "deger"])

        records = []
        for r in rows:
            yil = r.get("yil", "")
            ay = r.get("ay", 0)
            try:
                tarih = f"{yil}-{int(ay):02d}"
            except (ValueError, TypeError):
                tarih = f"{yil}-00"
            records.append({
                "tarih": tarih,
                "kalem": r.get("oran", ""),
                "deger": r.get("deger"),
                "kategori": r.get("kategori", ""),
            })
        return pd.DataFrame(records)

    async def get_company_profile(self, ticker: str) -> dict:
        sql = f"""
        SELECT hisse_senedi_kodu, unvan, odenmis_sermaye, fiili_dolasim_orani,
               piyasa_degeri, son_fiyat, fonksiyonel_para_birimi
        FROM hisse_senetleri
        WHERE hisse_senedi_kodu = '{ticker}'
        LIMIT 1
        """
        rows = await self.query(sql, purpose=f"{ticker} company profile")
        return rows[0] if rows else {}

    async def get_income_statement(self, ticker: str, periods: int = 10) -> pd.DataFrame:
        """Fetch income statement items for recent periods.

        Real table: hisse_finansal_tablolari_gelir_tablosu_kalemleri
        Columns: hisse_senedi_kodu, yil, ay, satir_no, kalem, try_donemsel, try_ceyreklik, try_ttm
        """
        sql = f"""
        SELECT yil, ay, kalem, try_donemsel
        FROM hisse_finansal_tablolari_gelir_tablosu_kalemleri
        WHERE hisse_senedi_kodu = '{ticker}'
          AND (yil, ay) IN (
            SELECT yil, ay FROM hisse_finansal_tablolari
            WHERE hisse_senedi_kodu = '{ticker}'
            ORDER BY yil DESC, ay DESC
            LIMIT {periods}
          )
        ORDER BY yil DESC, ay DESC, satir_no ASC
        """
        rows = await self.query(sql, purpose=f"{ticker} income statement ({periods} periods)")
        return self._normalize_financials(rows)

    async def get_balance_sheet(self, ticker: str, periods: int = 8) -> pd.DataFrame:
        """Fetch balance sheet items for recent periods.

        Real table: hisse_finansal_tablolari_bilanco_kalemleri
        Columns: hisse_senedi_kodu, yil, ay, satir_no, kalem, try_donemsel
        """
        sql = f"""
        SELECT yil, ay, kalem, try_donemsel
        FROM hisse_finansal_tablolari_bilanco_kalemleri
        WHERE hisse_senedi_kodu = '{ticker}'
          AND (yil, ay) IN (
            SELECT yil, ay FROM hisse_finansal_tablolari
            WHERE hisse_senedi_kodu = '{ticker}'
            ORDER BY yil DESC, ay DESC
            LIMIT {periods}
          )
        ORDER BY yil DESC, ay DESC, satir_no ASC
        """
        rows = await self.query(sql, purpose=f"{ticker} balance sheet ({periods} periods)")
        return self._normalize_financials(rows)

    async def get_cash_flow(self, ticker: str, periods: int = 8) -> pd.DataFrame:
        """Fetch cash flow statement items for recent periods.

        Real table: hisse_finansal_tablolari_nakit_akis_tablosu_kalemleri
        Columns: hisse_senedi_kodu, yil, ay, satir_no, kalem, try_donemsel, try_ceyreklik, try_ttm
        """
        sql = f"""
        SELECT yil, ay, kalem, try_donemsel
        FROM hisse_finansal_tablolari_nakit_akis_tablosu_kalemleri
        WHERE hisse_senedi_kodu = '{ticker}'
          AND (yil, ay) IN (
            SELECT yil, ay FROM hisse_finansal_tablolari
            WHERE hisse_senedi_kodu = '{ticker}'
            ORDER BY yil DESC, ay DESC
            LIMIT {periods}
          )
        ORDER BY yil DESC, ay DESC, satir_no ASC
        """
        rows = await self.query(sql, purpose=f"{ticker} cash flow ({periods} periods)")
        return self._normalize_financials(rows)

    async def get_ratios(self, ticker: str, periods: int = 8) -> pd.DataFrame:
        """Fetch financial ratios for recent periods.

        Real table: hisse_finansal_tablolari_finansal_oranlari
        Columns: hisse_senedi_kodu, yil, ay, satir_no, kategori, oran, deger
        """
        sql = f"""
        SELECT yil, ay, kategori, oran, deger
        FROM hisse_finansal_tablolari_finansal_oranlari
        WHERE hisse_senedi_kodu = '{ticker}'
          AND (yil, ay) IN (
            SELECT yil, ay FROM hisse_finansal_tablolari
            WHERE hisse_senedi_kodu = '{ticker}'
            ORDER BY yil DESC, ay DESC
            LIMIT {periods}
          )
        ORDER BY yil DESC, ay DESC, satir_no ASC
        """
        rows = await self.query(sql, purpose=f"{ticker} financial ratios ({periods} periods)")
        return self._normalize_ratios(rows)

    async def get_analyst_targets(self, ticker: str) -> list[dict]:
        """Fetch analyst target prices and recommendations.

        Real table: hisse_senedi_araci_kurum_hedef_fiyatlari
        """
        sql = f"""
        SELECT hf.araci_kurum_kodu,
               ak.kisa_unvan,
               hf.hedef_fiyat,
               hf.tavsiye,
               hf.yayin_tarihi_europe_istanbul
        FROM hisse_senedi_araci_kurum_hedef_fiyatlari hf
        LEFT JOIN araci_kurumlar ak ON hf.araci_kurum_kodu = ak.araci_kurum_kodu
        WHERE hf.hisse_senedi_kodu = '{ticker}'
        ORDER BY hf.yayin_tarihi_europe_istanbul DESC
        LIMIT 20
        """
        rows = await self.query(sql, purpose=f"{ticker} analyst target prices")
        return rows if rows else []

    async def get_dividends(self, ticker: str) -> pd.DataFrame:
        """Fetch dividend data — try the temettüler table, fall back gracefully."""
        try:
            sql = f"""
            SELECT tarih, hisse_senedi_kodu, temettü_verimi, hisse_basina_temettü,
                   brüt_nakit_temettü, net_nakit_temettü
            FROM temettüler
            WHERE hisse_senedi_kodu = '{ticker}'
            ORDER BY tarih DESC
            LIMIT 20
            """
            rows = await self.query(sql, purpose=f"{ticker} dividends")
            return pd.DataFrame(rows) if rows else pd.DataFrame()
        except Exception:
            logger.debug("Dividends table not available for %s", ticker)
            return pd.DataFrame()

    async def get_peer_tickers(self, ticker: str) -> list[str]:
        sql = f"""
        SELECT h2.hisse_senedi_kodu
        FROM hisse_senetleri h1
        JOIN hisse_senetleri h2 ON h1.sektor_id = h2.sektor_id
        WHERE h1.hisse_senedi_kodu = '{ticker}'
          AND h2.hisse_senedi_kodu != '{ticker}'
        LIMIT 15
        """
        rows = await self.query(sql, purpose=f"{ticker} sector peers")
        return [r["hisse_senedi_kodu"] for r in rows if "hisse_senedi_kodu" in r] if rows else []

    async def get_activity_report(self, ticker: str) -> str:
        """Search for the company's latest activity report (faaliyet raporu)."""
        results = await self.search_documents(f"{ticker} faaliyet raporu", page=1, per_page=5)
        if not results.get("sonuclar"):
            return ""
        chunk_ids = [r["id"] for r in results["sonuclar"][:3] if "id" in r]
        if not chunk_ids:
            return ""
        chunks = await self.load_document_chunks(chunk_ids)
        return "\n\n".join(c.get("icerik", "") for c in chunks if isinstance(c, dict))

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
        analyst_targets = await self.get_analyst_targets(ticker)
        activity = await self.get_activity_report(ticker)

        result = {
            "company_profile": profile,
            "income_statement": income,
            "balance_sheet": balance,
            "cash_flow": cashflow,
            "ratios": ratios,
            "dividends": dividends,
            "peer_tickers": peers,
            "analyst_targets": analyst_targets,
            "activity_report": activity,
        }
        set_cached(cache_key, result)
        return result
