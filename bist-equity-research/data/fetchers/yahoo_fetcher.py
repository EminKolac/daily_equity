"""Yahoo Finance data fetcher — price data + benchmark."""

import logging
from typing import Any

import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)


class YahooFetcher:
    """Fetches OHLCV price data and benchmark from Yahoo Finance."""

    BIST_SUFFIX = ".IS"
    BENCHMARK = "XU100.IS"

    def get_price_history(self, ticker: str, period: str = "2y") -> pd.DataFrame:
        symbol = f"{ticker}{self.BIST_SUFFIX}"
        try:
            stock = yf.Ticker(symbol)
            df = stock.history(period=period)
            if df.empty:
                logger.warning("No price data from Yahoo for %s", symbol)
            return df
        except Exception as e:
            logger.error("Yahoo price fetch failed for %s: %s", symbol, e)
            return pd.DataFrame()

    def get_stock_info(self, ticker: str) -> dict:
        symbol = f"{ticker}{self.BIST_SUFFIX}"
        try:
            stock = yf.Ticker(symbol)
            return dict(stock.info)
        except Exception as e:
            logger.error("Yahoo info fetch failed for %s: %s", symbol, e)
            return {}

    def get_benchmark(self, period: str = "2y") -> pd.DataFrame:
        try:
            bench = yf.Ticker(self.BENCHMARK)
            return bench.history(period=period)
        except Exception as e:
            logger.error("Yahoo benchmark fetch failed: %s", e)
            return pd.DataFrame()

    def get_dividends(self, ticker: str) -> pd.DataFrame:
        symbol = f"{ticker}{self.BIST_SUFFIX}"
        try:
            stock = yf.Ticker(symbol)
            return stock.dividends.reset_index()
        except Exception as e:
            logger.error("Yahoo dividends fetch failed for %s: %s", symbol, e)
            return pd.DataFrame()

    def fetch_all(self, ticker: str) -> dict[str, Any]:
        logger.info("Fetching Yahoo data for %s", ticker)
        return {
            "price_history_2y": self.get_price_history(ticker, "2y"),
            "price_history_5y": self.get_price_history(ticker, "5y"),
            "stock_info": self.get_stock_info(ticker),
            "benchmark_2y": self.get_benchmark("2y"),
            "yahoo_dividends": self.get_dividends(ticker),
        }
