from typing import Optional
import redis.asyncio as redis
from app.core.config import settings
from fastapi_limiter import FastAPILimiter

redis_client: Optional[redis.Redis] = None


def _build_url() -> str:
    # user = settings.redis_username
    pwd = settings.redis_password
    host = settings.redis_host
    port = settings.redis_port
    db = settings.redis_db

    if pwd:
        return f"redis://:{pwd}@{host}:{port}/{db}"
    return f"redis://{host}:{port}/{db}"


async def init_redis() -> None:
    """Initialize global async Redis client. Call at app startup."""
    global redis_client
    url = _build_url()
    redis_client = redis.from_url(url, decode_responses=True)
    try:
        await redis_client.ping()
        print("✅ Redis connected")
        await FastAPILimiter.init(redis_client)
    except Exception as exc:
        print("⚠️ Redis connection failed:", exc)
        raise


async def close_redis() -> None:
    """Close the global Redis client. Call at app shutdown."""
    global redis_client
    if redis_client:
        try:
            await redis_client.close()
            await redis_client.connection_pool.disconnect()
        except Exception:
            pass
        redis_client = None


def get_redis() -> redis.Redis:
    assert redis_client is not None, "Redis not initialized. Call init_redis first."
    return redis_client
