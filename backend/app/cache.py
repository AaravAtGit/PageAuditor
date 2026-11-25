"""Redis: per-IP rate limiting and the 24h URL -> audit cache.

Design choice: if Redis is down, we log and carry on (fail open) rather than take
the whole app down. Audits still work; they just aren't limited or cached.
"""

import hashlib
import logging
import time
import uuid
from urllib.parse import urlsplit, urlunsplit

import redis.asyncio as redis

from app.config import get_settings

log = logging.getLogger(__name__)
_redis = redis.from_url(get_settings().redis_url, decode_responses=True)


def normalize_url(url: str) -> str:
    """Canonical form for cache keys: lowercase scheme/host, no default port, no fragment."""
    parts = urlsplit(url.strip())
    scheme = parts.scheme.lower()
    host = (parts.hostname or "").lower()
    port = parts.port
    if port and not ((scheme == "http" and port == 80) or (scheme == "https" and port == 443)):
        host = f"{host}:{port}"
    return urlunsplit((scheme, host, parts.path or "/", parts.query, ""))


def _url_key(normalized_url: str) -> str:
    return "audit:url:" + hashlib.sha256(normalized_url.encode()).hexdigest()


async def get_cached_audit_id(normalized_url: str) -> uuid.UUID | None:
    try:
        value = await _redis.get(_url_key(normalized_url))
    except redis.RedisError:
        log.warning("Redis unavailable; skipping cache lookup", exc_info=True)
        return None
    return uuid.UUID(value) if value else None


async def cache_audit_id(normalized_url: str, audit_id: uuid.UUID) -> None:
    try:
        await _redis.set(_url_key(normalized_url), str(audit_id), ex=get_settings().cache_ttl_seconds)
    except redis.RedisError:
        log.warning("Redis unavailable; audit not cached", exc_info=True)


class RateLimitExceeded(Exception):
    def __init__(self, retry_after: int):
        self.retry_after = retry_after


async def check_rate_limit(client_ip: str) -> None:
    """Fixed one-hour window: INCR a counter keyed by IP + hour, expire it after the hour.

    INCR and EXPIRE run in one MULTI/EXEC transaction, so a crash between them
    can't leave a counter that never expires.
    """
    limit = get_settings().rate_limit_per_hour
    window = int(time.time() // 3600)
    key = f"ratelimit:{client_ip}:{window}"
    try:
        async with _redis.pipeline(transaction=True) as pipe:
            count, _ = await pipe.incr(key).expire(key, 3600).execute()
    except redis.RedisError:
        log.warning("Redis unavailable; rate limit not enforced", exc_info=True)
        return
    if count > limit:
        raise RateLimitExceeded(retry_after=(window + 1) * 3600 - int(time.time()))


async def ping() -> bool:
    try:
        return await _redis.ping()
    except redis.RedisError:
        return False
