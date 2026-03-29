"""KAP (Public Disclosure Platform) disclosures scraper."""

import logging
from typing import Any

import pandas as pd
import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

KAP_BASE = "https://www.kap.org.tr"


class KAPFetcher:
    """Fetches KAP material event disclosures."""

    def __init__(self, timeout: int = 30):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (compatible; BISTResearch/1.0)",
        })

    def get_disclosures(self, ticker: str, limit: int = 20) -> list[dict]:
        """Fetch recent KAP disclosures for a ticker."""
        url = f"{KAP_BASE}/tr/api/disclosures"
        params = {
            "companyCode": ticker,
            "limit": limit,
        }
        try:
            resp = self.session.get(url, params=params, timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json()
            disclosures = []
            for item in data if isinstance(data, list) else data.get("disclosures", []):
                disclosures.append({
                    "date": item.get("publishDate", ""),
                    "title": item.get("title", ""),
                    "type": item.get("type", ""),
                    "summary": item.get("summary", ""),
                })
            return disclosures
        except Exception as e:
            logger.error("KAP fetch failed for %s: %s", ticker, e)
            return []

    def get_insider_trades(self, ticker: str) -> list[dict]:
        """Fetch insider trading disclosures."""
        url = f"{KAP_BASE}/tr/api/insider-trading"
        params = {"companyCode": ticker, "limit": 10}
        try:
            resp = self.session.get(url, params=params, timeout=self.timeout)
            resp.raise_for_status()
            return resp.json() if isinstance(resp.json(), list) else []
        except Exception as e:
            logger.error("KAP insider trades failed for %s: %s", ticker, e)
            return []

    def fetch_all(self, ticker: str) -> dict[str, Any]:
        logger.info("Fetching KAP disclosures for %s", ticker)
        return {
            "kap_disclosures": self.get_disclosures(ticker),
            "kap_insider_trades": self.get_insider_trades(ticker),
        }
