"""Database connection management."""
import asyncpg
from typing import Optional

from app.config import config
from app.logging_config import get_logger

logger = get_logger(__name__)


class DatabasePool:
    """Async PostgreSQL connection pool manager."""

    def __init__(self):
        self.pool: Optional[asyncpg.Pool] = None

    async def connect(self) -> None:
        """Initialize the connection pool."""
        if self.pool:
            logger.warning("Database pool already initialized")
            return

        logger.info(
            "Initializing database connection pool",
            host=config.database.host,
            port=config.database.port,
            database=config.database.database,
        )

        try:
            self.pool = await asyncpg.create_pool(
                host=config.database.host,
                port=config.database.port,
                user=config.database.user,
                password=config.database.password,
                database=config.database.database,
                min_size=5,
                max_size=20,
                command_timeout=30,
            )

            logger.info("Database connection pool initialized successfully")

        except Exception as e:
            logger.error("Failed to initialize database pool", error=str(e))
            raise

    async def close(self) -> None:
        """Close the connection pool."""
        if not self.pool:
            return

        logger.info("Closing database connection pool")
        await self.pool.close()
        self.pool = None
        logger.info("Database connection pool closed")

    async def acquire(self):
        """Acquire a connection from the pool."""
        if not self.pool:
            raise RuntimeError("Database pool not initialized")
        return self.pool.acquire()

    async def execute(self, query: str, *args):
        """Execute a query."""
        if not self.pool:
            raise RuntimeError("Database pool not initialized")
        async with self.pool.acquire() as conn:
            return await conn.execute(query, *args)

    async def fetch(self, query: str, *args):
        """Fetch multiple rows."""
        if not self.pool:
            raise RuntimeError("Database pool not initialized")
        async with self.pool.acquire() as conn:
            return await conn.fetch(query, *args)

    async def fetchrow(self, query: str, *args):
        """Fetch a single row."""
        if not self.pool:
            raise RuntimeError("Database pool not initialized")
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(query, *args)

    async def fetchval(self, query: str, *args):
        """Fetch a single value."""
        if not self.pool:
            raise RuntimeError("Database pool not initialized")
        async with self.pool.acquire() as conn:
            return await conn.fetchval(query, *args)


# Global database pool instance
db_pool = DatabasePool()
