"""İş Yatırım API fetcher — prices, financials, analyst coverage cross-validation."""

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

    def get_financials(self, ticker: str) -> pd.DataFrame:
        url = f"{BASE_URL}/MaliTablo"
        params = {
            "tip": "bilanço",
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
            logger.error("İş Yatırım financials failed for %s: %s", ticker, e)
            return pd.DataFrame()

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

    def fetch_all(self, ticker: str) -> dict[str, Any]:
        cache_key = f"isyatirim_{ticker}"
        cached = get_cached(cache_key)
        if cached is not None:
            return cached
        logger.info("Fetching İş Yatırım data for %s", ticker)
        result = {
            "isyatirim_prices": self.get_historical_prices(ticker),
            "isyatirim_financials": self.get_financials(ticker),
            "isyatirim_coverage": self.get_analyst_coverage(ticker),
        }
        set_cached(cache_key, result)
        return result
