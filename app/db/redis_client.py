"""Redis client for caching."""
import json
from typing import Optional, Any
import redis.asyncio as redis

from app.config import config
from app.logging_config import get_logger

logger = get_logger(__name__)


class RedisClient:
    """
    Async Redis client for multi-level caching.

    Cache levels:
    - L1 (hot): Journey/guideline definitions (indefinite)
    - L2 (warm): Activation results (5 minutes)
    - L3 (cold): Tool results (30 minutes)
    """

    def __init__(self):
        self.client: Optional[redis.Redis] = None

    async def connect(self) -> None:
        """Initialize Redis connection."""
        if self.client:
            logger.warning("Redis client already initialized")
            return

        logger.info(
            "Initializing Redis connection",
            host=config.redis.host,
            port=config.redis.port,
        )

        try:
            self.client = await redis.Redis(
                host=config.redis.host,
                port=config.redis.port,
                password=config.redis.password if config.redis.password else None,
                decode_responses=True,
                socket_timeout=5,
                socket_connect_timeout=5,
            )

            # Test connection
            await self.client.ping()

            logger.info("Redis connection initialized successfully")

        except Exception as e:
            logger.error("Failed to initialize Redis connection", error=str(e))
            raise

    async def close(self) -> None:
        """Close Redis connection."""
        if not self.client:
            return

        logger.info("Closing Redis connection")
        await self.client.close()
        self.client = None
        logger.info("Redis connection closed")

    async def get(self, key: str) -> Optional[str]:
        """Get value by key."""
        if not self.client:
            raise RuntimeError("Redis client not initialized")

        try:
            value = await self.client.get(key)
            logger.debug("Cache GET", key=key, hit=value is not None)
            return value
        except Exception as e:
            logger.error("Redis GET error", key=key, error=str(e))
            return None

    async def set(
        self,
        key: str,
        value: str,
        ttl: Optional[int] = None,
    ) -> bool:
        """
        Set value with optional TTL.

        Args:
            key: Cache key
            value: Value to cache
            ttl: Time-to-live in seconds (None = no expiration)
        """
        if not self.client:
            raise RuntimeError("Redis client not initialized")

        try:
            if ttl:
                await self.client.setex(key, ttl, value)
            else:
                await self.client.set(key, value)

            logger.debug("Cache SET", key=key, ttl=ttl)
            return True
        except Exception as e:
            logger.error("Redis SET error", key=key, error=str(e))
            return False

    async def get_json(self, key: str) -> Optional[Any]:
        """Get JSON value and deserialize."""
        value = await self.get(key)
        if value:
            try:
                return json.loads(value)
            except json.JSONDecodeError as e:
                logger.error("JSON decode error", key=key, error=str(e))
                return None
        return None

    async def set_json(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
    ) -> bool:
        """Serialize and set JSON value."""
        try:
            json_value = json.dumps(value)
            return await self.set(key, json_value, ttl)
        except (TypeError, ValueError) as e:
            logger.error("JSON encode error", key=key, error=str(e))
            return False

    async def delete(self, key: str) -> bool:
        """Delete key."""
        if not self.client:
            raise RuntimeError("Redis client not initialized")

        try:
            await self.client.delete(key)
            logger.debug("Cache DELETE", key=key)
            return True
        except Exception as e:
            logger.error("Redis DELETE error", key=key, error=str(e))
            return False

    async def exists(self, key: str) -> bool:
        """Check if key exists."""
        if not self.client:
            raise RuntimeError("Redis client not initialized")

        try:
            result = await self.client.exists(key)
            return result > 0
        except Exception as e:
            logger.error("Redis EXISTS error", key=key, error=str(e))
            return False

    # Cache level helpers

    async def cache_l1(self, key: str, value: Any) -> bool:
        """Cache at L1 (hot) - indefinite TTL for definitions."""
        return await self.set_json(f"l1:{key}", value, ttl=None)

    async def cache_l2(self, key: str, value: Any) -> bool:
        """Cache at L2 (warm) - 5 minute TTL for activations."""
        return await self.set_json(f"l2:{key}", value, ttl=300)

    async def cache_l3(self, key: str, value: Any) -> bool:
        """Cache at L3 (cold) - 30 minute TTL for tool results."""
        return await self.set_json(f"l3:{key}", value, ttl=1800)

    async def get_l1(self, key: str) -> Optional[Any]:
        """Get from L1 cache."""
        return await self.get_json(f"l1:{key}")

    async def get_l2(self, key: str) -> Optional[Any]:
        """Get from L2 cache."""
        return await self.get_json(f"l2:{key}")

    async def get_l3(self, key: str) -> Optional[Any]:
        """Get from L3 cache."""
        return await self.get_json(f"l3:{key}")


# Global Redis client instance
redis_client = RedisClient()
