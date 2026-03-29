"""Twitter/X sentiment fetcher via Apify Tweet Scraper."""

import logging
from datetime import datetime, timedelta
from typing import Any

from config.settings import APIFY_API_TOKEN

logger = logging.getLogger(__name__)

FINTWIT_ACCOUNTS = ["BorsaGundem", "yaborsa", "baborsa", "ParaAnaliz"]


class TwitterFetcher:
    """Fetches Twitter/X data via Apify's Tweet Scraper V2."""

    def __init__(self):
        self.api_token = APIFY_API_TOKEN
        self._client = None

    @property
    def client(self):
        if self._client is None and self.api_token:
            try:
                from apify_client import ApifyClient
                self._client = ApifyClient(self.api_token)
            except ImportError:
                logger.warning("apify-client not installed")
        return self._client

    def search_tweets(self, ticker: str, max_tweets: int = 200, days: int = 30) -> list[dict]:
        if not self.client:
            logger.warning("No Apify client available — skipping Twitter fetch")
            return []

        start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

        run_input = {
            "searchTerms": [f"${ticker}", f"#{ticker}", ticker],
            "searchMode": "live",
            "maxTweets": max_tweets,
            "language": "tr",
            "addUserInfo": True,
            "startDate": start_date,
            "sort": "Latest",
        }

        try:
            run = self.client.actor("apidojo/tweet-scraper").call(run_input=run_input)
            tweets = []
            for item in self.client.dataset(run["defaultDatasetId"]).iterate_items():
                author = item.get("author", {})
                tweets.append({
                    "date": item.get("createdAt"),
                    "text": item.get("text", ""),
                    "likes": item.get("likeCount", 0),
                    "retweets": item.get("retweetCount", 0),
                    "replies": item.get("replyCount", 0),
                    "user": author.get("userName", ""),
                    "user_followers": author.get("followers", 0),
                    "is_verified": author.get("isVerified", False),
                    "is_blue": author.get("isBlueVerified", False),
                })
            return tweets
        except Exception as e:
            logger.error("Apify tweet search failed for %s: %s", ticker, e)
            return []

    def scrape_fintwit_accounts(self, ticker: str) -> list[dict]:
        if not self.client:
            return []

        tweets = []
        for account in FINTWIT_ACCOUNTS:
            try:
                run_input = {
                    "twitterHandles": [account],
                    "maxTweets": 20,
                }
                run = self.client.actor("apidojo/tweet-scraper").call(run_input=run_input)
                for item in self.client.dataset(run["defaultDatasetId"]).iterate_items():
                    text = item.get("text", "")
                    if ticker.lower() in text.lower():
                        author = item.get("author", {})
                        tweets.append({
                            "date": item.get("createdAt"),
                            "text": text,
                            "likes": item.get("likeCount", 0),
                            "retweets": item.get("retweetCount", 0),
                            "replies": item.get("replyCount", 0),
                            "user": author.get("userName", account),
                            "user_followers": author.get("followers", 0),
                            "is_verified": True,
                            "is_blue": author.get("isBlueVerified", False),
                            "source": "fintwit",
                        })
            except Exception as e:
                logger.error("Fintwit scrape failed for @%s: %s", account, e)
        return tweets

    def fetch_all(self, ticker: str) -> dict[str, Any]:
        logger.info("Fetching Twitter data for %s via Apify", ticker)
        search_tweets = self.search_tweets(ticker)
        fintwit_tweets = self.scrape_fintwit_accounts(ticker)
        all_tweets = search_tweets + fintwit_tweets
        return {
            "twitter_tweets": all_tweets,
            "twitter_count": len(all_tweets),
        }
