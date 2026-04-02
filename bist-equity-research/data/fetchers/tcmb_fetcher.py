"""TCMB EVDS macro data fetcher — rates, CPI, FX."""

import logging
from datetime import datetime, timedelta
from typing import Any

import pandas as pd
import requests

from config.settings import TCMB_EVDS_API_KEY
from data.cache_utils import get_cached, set_cached

logger = logging.getLogger(__name__)

EVDS_BASE = "https://evds2.tcmb.gov.tr/service/evds"

SERIES = {
    "policy_rate": "TP.PF.PF01",
    "cpi_yoy": "TP.FG.J0",
    "usd_try": "TP.DK.USD.A.YTL",
    "eur_try": "TP.DK.EUR.A.YTL",
}


class TCMBFetcher:
    """Fetches macroeconomic data from TCMB EVDS API."""

    def __init__(self):
        self.api_key = TCMB_EVDS_API_KEY
        self.session = requests.Session()

    def _fetch_series(self, series_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        if not self.api_key:
            logger.warning("No TCMB API key — using fallback for %s", series_code)
            return pd.DataFrame()

        url = f"{EVDS_BASE}/series={series_code}"
        params = {
            "startDate": start_date,
            "endDate": end_date,
            "type": "json",
            "key": self.api_key,
        }
        try:
            resp = self.session.get(url, params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            items = data.get("items", [])
            if not items:
                return pd.DataFrame()
            df = pd.DataFrame(items)
            if "Tarih" in df.columns:
                df["Tarih"] = pd.to_datetime(df["Tarih"], format="%d-%m-%Y")
            return df
        except Exception as e:
            logger.error("TCMB fetch failed for %s: %s", series_code, e)
            return pd.DataFrame()

    def get_macro_indicators(self, lookback_days: int = 365) -> dict[str, pd.DataFrame]:
        end = datetime.now()
        start = end - timedelta(days=lookback_days)
        start_str = start.strftime("%d-%m-%Y")
        end_str = end.strftime("%d-%m-%Y")

        result = {}
        for name, code in SERIES.items():
            result[name] = self._fetch_series(code, start_str, end_str)
        return result

    def get_latest_values(self) -> dict[str, float | None]:
        """Get latest value for each macro series."""
        indicators = self.get_macro_indicators(lookback_days=90)
        latest = {}
        for name, df in indicators.items():
            if df.empty:
                latest[name] = None
                continue
            value_cols = [c for c in df.columns if c not in ("Tarih", "UNIXTIME")]
            if value_cols:
                try:
                    latest[name] = float(df[value_cols[0]].dropna().iloc[-1])
                except (IndexError, ValueError):
                    latest[name] = None
            else:
                latest[name] = None
        return latest

    def fetch_all(self) -> dict[str, Any]:
        cache_key = "tcmb_macro"
        cached = get_cached(cache_key)
        if cached is not None:
            return cached
        logger.info("Fetching TCMB macro data")
        result = {
            "macro_series": self.get_macro_indicators(),
            "macro_latest": self.get_latest_values(),
        }
        set_cached(cache_key, result)
        return result
