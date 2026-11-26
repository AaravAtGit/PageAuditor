import redis.asyncio as redis

from app.config import settings

r = redis.from_url(settings.redis_url, decode_responses=True)


async def is_rate_limited(ip: str) -> bool:
    key = f"rate:{ip}"
    count = await r.incr(key)
    if count == 1:
        await r.expire(key, 3600)
    return count > 10


async def get_cached_audit_id(url: str) -> str | None:
    return await r.get(f"audit:{url}")


async def cache_audit_id(url: str, audit_id: str) -> None:
    await r.set(f"audit:{url}", audit_id, ex=24 * 60 * 60)
