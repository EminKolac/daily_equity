"""Yahoo Finance data fetcher — price data + benchmark."""

import logging
import time
from typing import Any

import pandas as pd
import yfinance as yf

from data.cache_utils import get_cached, set_cached

logger = logging.getLogger(__name__)


class YahooFetcher:
    """Fetches OHLCV price data and benchmark from Yahoo Finance."""

    BIST_SUFFIX = ".IS"
    BENCHMARK = "XU100.IS"
    MAX_RETRIES = 2
    RETRY_DELAY = 2

    def _with_retry(self, func, *args, **kwargs):
        """Execute function with retry logic."""
        for attempt in range(self.MAX_RETRIES + 1):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                if attempt < self.MAX_RETRIES:
                    logger.warning("Yahoo retry %d/%d: %s", attempt + 1, self.MAX_RETRIES, e)
                    time.sleep(self.RETRY_DELAY * (attempt + 1))
                else:
                    raise

    def get_price_history(self, ticker: str, period: str = "2y") -> pd.DataFrame:
        symbol = f"{ticker}{self.BIST_SUFFIX}"
        try:
            stock = yf.Ticker(symbol)
            df = self._with_retry(stock.history, period=period)
            if df is None or df.empty:
                logger.warning("No price data from Yahoo for %s", symbol)
                return pd.DataFrame()
            return df
        except Exception as e:
            logger.error("Yahoo price fetch failed for %s: %s", symbol, e)
            return pd.DataFrame()

    def get_stock_info(self, ticker: str) -> dict:
        symbol = f"{ticker}{self.BIST_SUFFIX}"
        try:
            stock = yf.Ticker(symbol)
            info = self._with_retry(lambda: stock.info)
            return dict(info) if info else {}
        except Exception as e:
            logger.error("Yahoo info fetch failed for %s: %s", symbol, e)
            return {}

    def get_benchmark(self, period: str = "2y") -> pd.DataFrame:
        try:
            bench = yf.Ticker(self.BENCHMARK)
            df = self._with_retry(bench.history, period=period)
            if df is None or df.empty:
                return pd.DataFrame()
            return df
        except Exception as e:
            logger.error("Yahoo benchmark fetch failed: %s", e)
            return pd.DataFrame()

    def get_dividends(self, ticker: str) -> pd.DataFrame:
        symbol = f"{ticker}{self.BIST_SUFFIX}"
        try:
            stock = yf.Ticker(symbol)
            divs = stock.dividends
            if divs is None or divs.empty:
                return pd.DataFrame()
            return divs.reset_index()
        except Exception as e:
            logger.error("Yahoo dividends fetch failed for %s: %s", symbol, e)
            return pd.DataFrame()

    def fetch_all(self, ticker: str) -> dict[str, Any]:
        cache_key = f"yahoo_{ticker}"
        cached = get_cached(cache_key)
        if cached is not None:
            return cached
        logger.info("Fetching Yahoo data for %s", ticker)
        result = {
            "price_history_2y": self.get_price_history(ticker, "2y"),
            "price_history_5y": self.get_price_history(ticker, "5y"),
            "stock_info": self.get_stock_info(ticker),
            "benchmark_2y": self.get_benchmark("2y"),
            "yahoo_dividends": self.get_dividends(ticker),
        }
        set_cached(cache_key, result)
        return result
