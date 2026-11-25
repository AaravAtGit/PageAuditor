"""Redis: rate limiting per IP, and a 24h cache of URL -> audit id."""

import redis.asyncio as redis

from app.config import settings

r = redis.from_url(settings.redis_url, decode_responses=True)


async def is_rate_limited(ip: str) -> bool:
    """Allow `rate_limit_per_hour` audits per IP; the counter resets an hour after the first one."""
    key = f"rate:{ip}"
    count = await r.incr(key)
    if count == 1:
        await r.expire(key, 3600)
    return count > settings.rate_limit_per_hour


async def get_cached_audit_id(url: str) -> str | None:
    return await r.get(f"audit:{url}")


async def cache_audit_id(url: str, audit_id: str) -> None:
    await r.set(f"audit:{url}", audit_id, ex=settings.cache_ttl_seconds)
