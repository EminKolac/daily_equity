"""Yahoo Finance data fetcher — price data + benchmark."""

import logging
import time
from typing import Any

import pandas as pd
import yfinance as yf

from data.cache_utils import get_cached, set_cached

logger = logging.getLogger(__name__)

# Small delay between consecutive Yahoo API calls to avoid rate limiting.
_API_CALL_DELAY = 0.5


def _get_ticker_info(stock: yf.Ticker) -> dict:
    """Retrieve the .info property from a yfinance Ticker.

    Wrapped as a standalone function so it can be passed directly to
    ``_with_retry`` (the previous ``lambda: stock.info`` form was
    technically callable but obscured the call-site semantics and could
    not accept *args/**kwargs forwarded by ``_with_retry``).
    """
    return stock.info


class YahooFetcher:
    """Fetches OHLCV price data and benchmark from Yahoo Finance."""

    BIST_SUFFIX = ".IS"
    BENCHMARK = "XU100.IS"
    MAX_RETRIES = 2
    RETRY_DELAY = 2

    def _with_retry(self, func, *args, **kwargs):
        """Execute *func* with retry logic."""
        for attempt in range(self.MAX_RETRIES + 1):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                if attempt < self.MAX_RETRIES:
                    logger.warning("Yahoo retry %d/%d: %s", attempt + 1, self.MAX_RETRIES, e)
                    time.sleep(self.RETRY_DELAY * (attempt + 1))
                else:
                    raise

    # ------------------------------------------------------------------
    # Price history
    # ------------------------------------------------------------------

    def get_price_history(self, ticker: str, period: str = "2y") -> pd.DataFrame:
        symbol = f"{ticker}{self.BIST_SUFFIX}"
        try:
            stock = yf.Ticker(symbol)
            df = self._with_retry(stock.history, period=period)

            # yfinance may return None on transient failures instead of
            # raising, which would cause 'NoneType' object is not
            # subscriptable downstream.
            if df is None:
                logger.warning("Yahoo returned None for %s (period=%s)", symbol, period)
                return pd.DataFrame()

            if not isinstance(df, pd.DataFrame):
                logger.warning("Yahoo returned unexpected type %s for %s", type(df).__name__, symbol)
                return pd.DataFrame()

            if df.empty:
                logger.warning("No price data from Yahoo for %s", symbol)
                return pd.DataFrame()

            return df
        except Exception as e:
            logger.error("Yahoo price fetch failed for %s: %s", symbol, e)
            return pd.DataFrame()

    # ------------------------------------------------------------------
    # Stock info
    # ------------------------------------------------------------------

    def get_stock_info(self, ticker: str) -> dict:
        symbol = f"{ticker}{self.BIST_SUFFIX}"
        try:
            stock = yf.Ticker(symbol)
            info = self._with_retry(_get_ticker_info, stock)

            if info is None:
                logger.warning("Yahoo returned None info for %s", symbol)
                return {}

            return dict(info) if info else {}
        except Exception as e:
            logger.error("Yahoo info fetch failed for %s: %s", symbol, e)
            return {}

    # ------------------------------------------------------------------
    # Benchmark
    # ------------------------------------------------------------------

    def get_benchmark(self, period: str = "2y") -> pd.DataFrame:
        try:
            bench = yf.Ticker(self.BENCHMARK)
            df = self._with_retry(bench.history, period=period)

            if df is None:
                logger.warning("Yahoo returned None for benchmark (period=%s)", period)
                return pd.DataFrame()

            if not isinstance(df, pd.DataFrame):
                logger.warning("Yahoo returned unexpected type %s for benchmark", type(df).__name__)
                return pd.DataFrame()

            if df.empty:
                return pd.DataFrame()

            return df
        except Exception as e:
            logger.error("Yahoo benchmark fetch failed: %s", e)
            return pd.DataFrame()

    # ------------------------------------------------------------------
    # Dividends
    # ------------------------------------------------------------------

    def get_dividends(self, ticker: str) -> pd.DataFrame:
        symbol = f"{ticker}{self.BIST_SUFFIX}"
        try:
            stock = yf.Ticker(symbol)
            divs = stock.dividends

            if divs is None:
                logger.warning("Yahoo returned None dividends for %s", symbol)
                return pd.DataFrame()

            if not isinstance(divs, pd.Series) and not isinstance(divs, pd.DataFrame):
                logger.warning("Yahoo returned unexpected dividends type %s for %s", type(divs).__name__, symbol)
                return pd.DataFrame()

            if divs.empty:
                return pd.DataFrame()

            return divs.reset_index()
        except Exception as e:
            logger.error("Yahoo dividends fetch failed for %s: %s", symbol, e)
            return pd.DataFrame()

    # ------------------------------------------------------------------
    # Aggregate fetch
    # ------------------------------------------------------------------

    def fetch_all(self, ticker: str) -> dict[str, Any]:
        cache_key = f"yahoo_{ticker}"
        cached = get_cached(cache_key)
        if cached is not None:
            return cached

        logger.info("Fetching Yahoo data for %s", ticker)

        price_2y = self.get_price_history(ticker, "2y")
        time.sleep(_API_CALL_DELAY)

        price_5y = self.get_price_history(ticker, "5y")
        time.sleep(_API_CALL_DELAY)

        stock_info = self.get_stock_info(ticker)
        time.sleep(_API_CALL_DELAY)

        benchmark_2y = self.get_benchmark("2y")
        time.sleep(_API_CALL_DELAY)

        dividends = self.get_dividends(ticker)

        result = {
            "price_history_2y": price_2y,
            "price_history_5y": price_5y,
            "stock_info": stock_info,
            "benchmark_2y": benchmark_2y,
            "yahoo_dividends": dividends,
        }
        set_cached(cache_key, result)
        return result
