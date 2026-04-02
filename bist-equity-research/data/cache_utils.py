import os
import json
import hashlib
import pickle
import logging
from datetime import datetime, timedelta
from config.settings import CACHE_DIR, CACHE_TTL_HOURS

logger = logging.getLogger(__name__)

def _cache_path(key: str) -> str:
    """Get cache file path for a given key."""
    os.makedirs(CACHE_DIR, exist_ok=True)
    safe_key = hashlib.md5(key.encode()).hexdigest()
    return os.path.join(CACHE_DIR, f"{safe_key}.pkl")

def get_cached(key: str):
    """Get cached value if it exists and hasn't expired."""
    path = _cache_path(key)
    if not os.path.exists(path):
        return None
    try:
        with open(path, "rb") as f:
            data = pickle.load(f)
        if datetime.now() - data["timestamp"] > timedelta(hours=CACHE_TTL_HOURS):
            os.remove(path)
            return None
        logger.debug("Cache hit: %s", key)
        return data["value"]
    except Exception:
        return None

def set_cached(key: str, value):
    """Store value in cache."""
    path = _cache_path(key)
    os.makedirs(CACHE_DIR, exist_ok=True)
    try:
        with open(path, "wb") as f:
            pickle.dump({"timestamp": datetime.now(), "value": value}, f)
    except Exception as e:
        logger.warning("Cache write failed: %s", e)
