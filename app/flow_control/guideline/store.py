"""Guideline storage with PostgreSQL and Redis caching."""
from typing import List, Optional, Dict, Set
from uuid import UUID

from app.db.connection import DatabasePool
from app.db.redis_client import RedisClient
from app.flow_control.guideline.models import Guideline, GuidelineScope
from app.logging_config import get_logger

logger = get_logger(__name__)


class GuidelineStore:
    """Manages guideline storage with keyword indexing."""

    def __init__(self, db_pool: DatabasePool, redis_client: RedisClient):
        self.db = db_pool
        self.redis = redis_client
        self._keyword_index: Dict[str, Set[UUID]] = {}  # keyword -> guideline_ids

    async def load_guideline_definitions(self) -> None:
        """Load all guidelines from PostgreSQL into Redis L1 cache and build keyword index."""
        logger.info("Loading guideline definitions into cache")

        try:
            # Fetch all enabled guidelines
            rows = await self.db.fetch(
                """
                SELECT id, scope, journey_id, state_name, name, description,
                       condition, action, tools, keywords, priority, enabled,
                       created_at, updated_at
                FROM guidelines
                WHERE enabled = true
                ORDER BY priority DESC, name
                """
            )

            # Clear keyword index
            self._keyword_index.clear()

            for row in rows:
                guideline = Guideline(
                    id=row["id"],
                    scope=GuidelineScope(row["scope"]),
                    journey_id=row["journey_id"],
                    state_name=row["state_name"],
                    name=row["name"],
                    description=row["description"],
                    condition=row["condition"],
                    action=row["action"],
                    tools=row["tools"] or [],
                    keywords=row["keywords"] or [],
                    priority=row["priority"],
                    enabled=row["enabled"],
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                )

                # Cache to L1 (indefinite)
                await self.redis.cache_l1(
                    f"guideline:def:{guideline.id}",
                    {
                        "id": str(guideline.id),
                        "scope": guideline.scope.value,
                        "journey_id": str(guideline.journey_id) if guideline.journey_id else None,
                        "state_name": guideline.state_name,
                        "name": guideline.name,
                        "description": guideline.description,
                        "condition": guideline.condition,
                        "action": guideline.action,
                        "tools": guideline.tools,
                        "keywords": guideline.keywords,
                        "priority": guideline.priority,
                        "enabled": guideline.enabled,
                    },
                )

                # Build keyword index
                for keyword in guideline.keywords:
                    keyword_lower = keyword.lower()
                    if keyword_lower not in self._keyword_index:
                        self._keyword_index[keyword_lower] = set()
                    self._keyword_index[keyword_lower].add(guideline.id)

            logger.info(
                "Guideline definitions loaded",
                count=len(rows),
                keywords_indexed=len(self._keyword_index),
            )

        except Exception as e:
            logger.error("Failed to load guideline definitions", error=str(e))
            raise

    async def get_guideline(self, guideline_id: UUID) -> Optional[Guideline]:
        """Get guideline by ID (cache-first)."""
        try:
            # Try L1 cache first
            cached = await self.redis.get_l1(f"guideline:def:{guideline_id}")
            if cached:
                return Guideline(
                    id=UUID(cached["id"]),
                    scope=GuidelineScope(cached["scope"]),
                    journey_id=UUID(cached["journey_id"]) if cached.get("journey_id") else None,
                    state_name=cached.get("state_name"),
                    name=cached["name"],
                    description=cached.get("description"),
                    condition=cached["condition"],
                    action=cached["action"],
                    tools=cached.get("tools", []),
                    keywords=cached.get("keywords", []),
                    priority=cached.get("priority", 0),
                    enabled=cached.get("enabled", True),
                )

            # Cache miss - fetch from database
            row = await self.db.fetchrow(
                """
                SELECT id, scope, journey_id, state_name, name, description,
                       condition, action, tools, keywords, priority, enabled,
                       created_at, updated_at
                FROM guidelines
                WHERE id = $1 AND enabled = true
                """,
                guideline_id,
            )

            if not row:
                return None

            return Guideline(
                id=row["id"],
                scope=GuidelineScope(row["scope"]),
                journey_id=row["journey_id"],
                state_name=row["state_name"],
                name=row["name"],
                description=row["description"],
                condition=row["condition"],
                action=row["action"],
                tools=row["tools"] or [],
                keywords=row["keywords"] or [],
                priority=row["priority"],
                enabled=row["enabled"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )

        except Exception as e:
            logger.error("Error fetching guideline", guideline_id=str(guideline_id), error=str(e))
            raise

    async def get_guidelines_by_scope(
        self,
        journey_id: Optional[UUID] = None,
        state_name: Optional[str] = None,
    ) -> List[Guideline]:
        """Get all guidelines matching the given scope."""
        rows = await self.db.fetch(
            """
            SELECT id, scope, journey_id, state_name, name, description,
                   condition, action, tools, keywords, priority, enabled,
                   created_at, updated_at
            FROM guidelines
            WHERE enabled = true
              AND (
                scope = 'GLOBAL'
                OR (scope = 'JOURNEY' AND journey_id = $1)
                OR (scope = 'STATE' AND journey_id = $1 AND state_name = $2)
              )
            ORDER BY priority DESC, name
            """,
            journey_id,
            state_name,
        )

        return [
            Guideline(
                id=row["id"],
                scope=GuidelineScope(row["scope"]),
                journey_id=row["journey_id"],
                state_name=row["state_name"],
                name=row["name"],
                description=row["description"],
                condition=row["condition"],
                action=row["action"],
                tools=row["tools"] or [],
                keywords=row["keywords"] or [],
                priority=row["priority"],
                enabled=row["enabled"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
            for row in rows
        ]

    def get_candidates_by_keywords(
        self, message_keywords: List[str]
    ) -> Set[UUID]:
        """
        Get guideline candidates matching any of the message keywords.

        This is the Stage 1 pre-filter: <5ms target.
        """
        candidate_ids: Set[UUID] = set()

        for keyword in message_keywords:
            keyword_lower = keyword.lower()
            if keyword_lower in self._keyword_index:
                candidate_ids.update(self._keyword_index[keyword_lower])

        logger.debug(
            "Keyword pre-filter completed",
            message_keywords=message_keywords,
            candidates_found=len(candidate_ids),
        )

        return candidate_ids

    async def get_guidelines_by_ids(self, guideline_ids: Set[UUID]) -> List[Guideline]:
        """Get multiple guidelines by IDs."""
        guidelines = []

        for guideline_id in guideline_ids:
            guideline = await self.get_guideline(guideline_id)
            if guideline:
                guidelines.append(guideline)

        return guidelines
