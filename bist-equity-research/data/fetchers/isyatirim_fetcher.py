"""İş Yatırım API fetcher — prices, financials, analyst coverage.

When evofin MCP is unavailable (e.g. in GitHub Actions), this serves as the
primary financial data source alongside Yahoo Finance.
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Any

import pandas as pd
import requests

from data.cache_utils import get_cached, set_cached

logger = logging.getLogger(__name__)

BASE_URL = "https://www.isyatirim.com.tr/_layouts/15/Isyatirim.Website/Common/Data.aspx"


class IsYatirimFetcher:
    """Fetches data from İş Yatırım public JSON API."""

    def __init__(self, timeout: int = 30):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (compatible; BISTResearch/1.0)",
            "Accept": "application/json",
        })

    def get_historical_prices(self, ticker: str, days: int = 730) -> pd.DataFrame:
        end = datetime.now()
        start = end - timedelta(days=days)
        start_str = start.strftime("%d-%m-%Y")
        end_str = end.strftime("%d-%m-%Y")

        url = f"{BASE_URL}/HisseTekil"
        params = {
            "hession": ticker,
            "startdate": start_str,
            "enddate": end_str,
        }
        try:
            resp = self.session.get(url, params=params, timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json()
            values = data.get("value", [])
            if not values:
                logger.warning("No İş Yatırım price data for %s", ticker)
                return pd.DataFrame()
            df = pd.DataFrame(values)
            if "HGDG_TARIH" in df.columns:
                df["HGDG_TARIH"] = pd.to_datetime(df["HGDG_TARIH"])
                df = df.sort_values("HGDG_TARIH")
            return df
        except Exception as e:
            logger.error("İş Yatırım prices failed for %s: %s", ticker, e)
            return pd.DataFrame()

    def _get_mali_tablo(self, ticker: str, tip: str) -> pd.DataFrame:
        """Fetch a specific financial table type from İş Yatırım.

        Args:
            tip: "bilanço" (balance sheet), "gelir" (income stmt), "nakit" (cash flow)
        """
        url = f"{BASE_URL}/MaliTablo"
        params = {
            "tip": tip,
            "hession": ticker,
            "baession": "",
            "doession": datetime.now().strftime("%Y-12-31"),
            "currency": "TRY",
        }
        try:
            resp = self.session.get(url, params=params, timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json()
            values = data.get("value", [])
            return pd.DataFrame(values) if values else pd.DataFrame()
        except Exception as e:
            logger.error("İş Yatırım %s failed for %s: %s", tip, ticker, e)
            return pd.DataFrame()

    def get_financials(self, ticker: str) -> pd.DataFrame:
        """Fetch balance sheet (legacy method name)."""
        return self._get_mali_tablo(ticker, "bilanço")

    def get_income_statement(self, ticker: str) -> pd.DataFrame:
        return self._get_mali_tablo(ticker, "gelir")

    def get_cash_flow(self, ticker: str) -> pd.DataFrame:
        return self._get_mali_tablo(ticker, "nakit")

    def get_analyst_coverage(self, ticker: str) -> dict:
        """Get analyst target prices and recommendations."""
        url = f"{BASE_URL}/Hisse"
        params = {"hession": ticker}
        try:
            resp = self.session.get(url, params=params, timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json()
            return data
        except Exception as e:
            logger.error("İş Yatırım coverage failed for %s: %s", ticker, e)
            return {}

    def normalize_to_evofin_format(self, df: pd.DataFrame, table_type: str) -> pd.DataFrame:
        """Convert İş Yatırım financial table to evofin-compatible format.

        İş Yatırım returns columns like: itemCode, itemDescTr, value1, value2, ...
        where value columns correspond to different periods.
        We normalize to: tarih, kalem, deger (same as evofin output).
        """
        if df.empty:
            return pd.DataFrame(columns=["tarih", "kalem", "deger"])

        # İş Yatırım table structure varies; detect column layout
        # Common patterns: itemDescTr for item name, then period columns
        desc_col = None
        for candidate in ["itemDescTr", "itemDescEn", "KALEM", "itemDesc"]:
            if candidate in df.columns:
                desc_col = candidate
                break

        if desc_col is None:
            # Try to find a text column
            str_cols = [c for c in df.columns if df[c].dtype == object and c not in ("itemCode",)]
            desc_col = str_cols[0] if str_cols else None

        if desc_col is None:
            logger.warning("Cannot identify item description column in İş Yatırım %s", table_type)
            return pd.DataFrame(columns=["tarih", "kalem", "deger"])

        # Identify period/value columns (numeric columns that aren't itemCode)
        period_cols = []
        for c in df.columns:
            if c in (desc_col, "itemCode", "itemDescEn", "itemDescTr"):
                continue
            # Check if column name looks like a date or period
            try:
                if df[c].dtype in ("float64", "int64") or c.startswith("value"):
                    period_cols.append(c)
            except Exception:
                continue

        if not period_cols:
            logger.warning("No period columns found in İş Yatırım %s", table_type)
            return pd.DataFrame(columns=["tarih", "kalem", "deger"])

        records = []
        for _, row in df.iterrows():
            kalem = str(row.get(desc_col, ""))
            if not kalem:
                continue
            for pc in period_cols:
                val = row.get(pc)
                try:
                    deger = float(val) if val is not None and str(val).strip() != "" else None
                except (ValueError, TypeError):
                    deger = None
                records.append({
                    "tarih": str(pc),
                    "kalem": kalem,
                    "deger": deger,
                })

        return pd.DataFrame(records)

    def fetch_all(self, ticker: str) -> dict[str, Any]:
        cache_key = f"isyatirim_{ticker}"
        cached = get_cached(cache_key)
        if cached is not None:
            return cached
        logger.info("Fetching İş Yatırım data for %s", ticker)
        result = {
            "isyatirim_prices": self.get_historical_prices(ticker),
            "isyatirim_financials": self.get_financials(ticker),
            "isyatirim_income": self.get_income_statement(ticker),
            "isyatirim_cashflow": self.get_cash_flow(ticker),
            "isyatirim_coverage": self.get_analyst_coverage(ticker),
        }
        set_cached(cache_key, result)
        return result
