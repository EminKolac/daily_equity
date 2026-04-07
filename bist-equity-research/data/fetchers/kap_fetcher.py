"""KAP (Public Disclosure Platform) disclosures scraper.

KAP uses a POST-based JSON API for disclosure queries. The endpoints below are
derived from the public KAP website's AJAX calls.
"""

import logging
from datetime import datetime, timedelta
from typing import Any

import requests

from data.cache_utils import get_cached, set_cached

logger = logging.getLogger(__name__)

KAP_BASE = "https://www.kap.org.tr"


class KAPFetcher:
    """Fetches KAP material event disclosures."""

    def __init__(self, timeout: int = 30):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json",
            "Referer": "https://www.kap.org.tr/tr/bildirim-sorgu",
        })

    def get_disclosures(self, ticker: str, limit: int = 20) -> list[dict]:
        """Fetch recent KAP disclosures using the POST-based query API."""
        url = f"{KAP_BASE}/tr/api/memberDisclosureQuery"
        end_date = datetime.now()
        start_date = end_date - timedelta(days=90)
        import time

        payload = {
            "fromDate": start_date.strftime("%Y-%m-%d"),
            "toDate": end_date.strftime("%Y-%m-%d"),
            "year": "",
            "ppiList": [],
            "bdkReviewStatusList": [],
            "disclosureClass": [],
            "disclosureType": [],
            "subjectList": [],
            "mpiList": [],
            "isLate": "",
            "term": ticker,
            "memberOidList": [],
            "hideMy498": "",
            "assignedMemberOid": "",
        }

        for attempt in range(2):
            try:
                resp = self.session.post(url, json=payload, timeout=self.timeout)
                resp.raise_for_status()
                data = resp.json()

                disclosures = []
                items = data if isinstance(data, list) else data.get("disclosures", [])
                for item in items[:limit]:
                    disclosures.append({
                        "date": item.get("publishDate", item.get("disclosureDate", "")),
                        "title": item.get("title", item.get("subject", "")),
                        "type": item.get("disclosureType", item.get("type", "")),
                        "summary": item.get("summary", item.get("title", "")),
                    })
                return disclosures
            except Exception as e:
                if attempt == 0:
                    logger.warning("KAP retry for %s: %s", ticker, e)
                    time.sleep(3)
                else:
                    logger.error("KAP disclosures fetch failed for %s: %s", ticker, e)
        return []

    def get_insider_trades(self, ticker: str) -> list[dict]:
        """Fetch insider trading disclosures via KAP."""
        try:
            disclosures = self.get_disclosures(ticker, limit=50)
            insider_keywords = ["İçsel Bilgi", "Pay Alım", "Pay Satım", "Yönetici İşlemleri"]
            insider_trades = [
                d for d in disclosures
                if any(kw.lower() in (d.get("title", "") + d.get("type", "")).lower()
                       for kw in insider_keywords)
            ]
            return insider_trades[:10]
        except Exception as e:
            logger.error("KAP insider trades filter failed for %s: %s", ticker, e)
            return []

    def fetch_all(self, ticker: str) -> dict[str, Any]:
        cache_key = f"kap_{ticker}"
        cached = get_cached(cache_key)
        if cached is not None:
            return cached
        logger.info("Fetching KAP disclosures for %s", ticker)
        disclosures = self.get_disclosures(ticker)
        insider_trades = self.get_insider_trades(ticker)
        result = {
            "kap_disclosures": disclosures,
            "kap_insider_trades": insider_trades,
        }
        set_cached(cache_key, result)
        return result
