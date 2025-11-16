"""Knowledge base business service."""
from typing import Optional, List, Dict, Any

from app.db.connection import DatabasePool
from app.logging_config import get_logger

logger = get_logger(__name__)


class KnowledgeService:
    """Service for searching the knowledge base."""

    def __init__(self, db_pool: DatabasePool):
        self.db = db_pool

    async def search_knowledge_base(
        self,
        query: str,
        category: Optional[str] = None,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Search knowledge base using PostgreSQL full-text search.

        Uses plainto_tsquery for query parsing and ts_rank for relevance scoring.
        Results are ordered by relevance (highest rank first).

        Target latency: <50ms (P95)

        Args:
            query: Search query string
            category: Optional category filter (auto, health, property, general)
            limit: Maximum number of results (default 5, max 20)

        Returns:
            List of matching knowledge base articles with relevance scores
        """
        if limit > 20:
            limit = 20  # Max limit

        # Build query with optional category filter
        if category:
            rows = await self.db.fetch(
                """
                SELECT id, title, content, category, tags,
                       ts_rank(search_vector, plainto_tsquery('english', $1)) as relevance
                FROM knowledge_base
                WHERE search_vector @@ plainto_tsquery('english', $1)
                  AND category = $2
                ORDER BY relevance DESC
                LIMIT $3
                """,
                query,
                category,
                limit,
            )
        else:
            rows = await self.db.fetch(
                """
                SELECT id, title, content, category, tags,
                       ts_rank(search_vector, plainto_tsquery('english', $1)) as relevance
                FROM knowledge_base
                WHERE search_vector @@ plainto_tsquery('english', $1)
                ORDER BY relevance DESC
                LIMIT $2
                """,
                query,
                limit,
            )

        results = [
            {
                "id": str(row["id"]),
                "title": row["title"],
                "content": row["content"],
                "category": row["category"],
                "tags": row["tags"],
                "relevance": float(row["relevance"]),
            }
            for row in rows
        ]

        logger.info(
            "Knowledge base search",
            query=query,
            category=category,
            results_count=len(results),
        )

        return results
