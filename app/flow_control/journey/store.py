"""Journey storage with PostgreSQL and Redis caching."""
from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime
import json

from app.db.connection import DatabasePool
from app.db.redis_client import RedisClient
from app.flow_control.journey.models import Journey, JourneyState, JourneyTransition, JourneyContext
from app.logging_config import get_logger
from uuid7 import uuid7

logger = get_logger(__name__)


class JourneyStore:
    """Manages journey definitions and contexts with PostgreSQL + Redis."""

    def __init__(self, db_pool: DatabasePool, redis_client: RedisClient):
        self.db = db_pool
        self.redis = redis_client

    async def load_journey_definitions(self) -> None:
        """Load all journey definitions from PostgreSQL into Redis L1 cache."""
        logger.info("Loading journey definitions into cache")

        try:
            # Fetch all enabled journeys
            rows = await self.db.fetch(
                """
                SELECT id, name, description, activation_conditions,
                       initial_state, states, transitions, enabled,
                       created_at, updated_at
                FROM journeys
                WHERE enabled = true
                ORDER BY name
                """
            )

            for row in rows:
                journey = Journey(
                    id=row["id"],
                    name=row["name"],
                    description=row["description"],
                    activation_conditions=row["activation_conditions"],
                    initial_state=row["initial_state"],
                    states={
                        name: JourneyState(**state_data)
                        for name, state_data in row["states"].items()
                    },
                    transitions=[
                        JourneyTransition(**t) for t in row["transitions"]
                    ],
                    enabled=row["enabled"],
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                )

                # Cache to L1 (indefinite)
                await self.redis.cache_l1(
                    f"journey:def:{journey.id}",
                    {
                        "id": str(journey.id),
                        "name": journey.name,
                        "description": journey.description,
                        "activation_conditions": journey.activation_conditions,
                        "initial_state": journey.initial_state,
                        "states": {
                            name: {
                                "name": state.name,
                                "action": state.action,
                                "tools": state.tools,
                                "metadata": state.metadata,
                            }
                            for name, state in journey.states.items()
                        },
                        "transitions": [
                            {
                                "from_state": t.from_state,
                                "to_state": t.to_state,
                                "condition": t.condition,
                                "priority": t.priority,
                            }
                            for t in journey.transitions
                        ],
                        "enabled": journey.enabled,
                    },
                )

                # Also cache by name
                await self.redis.cache_l1(f"journey:name:{journey.name}", str(journey.id))

            logger.info("Journey definitions loaded", count=len(rows))

        except Exception as e:
            logger.error("Failed to load journey definitions", error=str(e))
            raise

    async def get_journey(self, journey_id: UUID) -> Optional[Journey]:
        """
        Get journey definition by ID (cache-first).

        Cache hit: <5ms
        Cache miss: <30ms (P95)
        """
        try:
            # Try L1 cache first
            cached = await self.redis.get_l1(f"journey:def:{journey_id}")
            if cached:
                logger.debug("Journey cache hit", journey_id=str(journey_id))
                return Journey(
                    id=UUID(cached["id"]),
                    name=cached["name"],
                    description=cached["description"],
                    activation_conditions=cached["activation_conditions"],
                    initial_state=cached["initial_state"],
                    states={
                        name: JourneyState(**state_data)
                        for name, state_data in cached["states"].items()
                    },
                    transitions=[JourneyTransition(**t) for t in cached["transitions"]],
                    enabled=cached["enabled"],
                )

            # Cache miss - fetch from database
            logger.debug("Journey cache miss, fetching from DB", journey_id=str(journey_id))
            row = await self.db.fetchrow(
                """
                SELECT id, name, description, activation_conditions,
                       initial_state, states, transitions, enabled,
                       created_at, updated_at
                FROM journeys
                WHERE id = $1 AND enabled = true
                """,
                journey_id,
            )

            if not row:
                return None

            journey = Journey(
                id=row["id"],
                name=row["name"],
                description=row["description"],
                activation_conditions=row["activation_conditions"],
                initial_state=row["initial_state"],
                states={
                    name: JourneyState(**state_data)
                    for name, state_data in row["states"].items()
                },
                transitions=[JourneyTransition(**t) for t in row["transitions"]],
                enabled=row["enabled"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )

            # Cache for next time
            await self.redis.cache_l1(
                f"journey:def:{journey_id}",
                {
                    "id": str(journey.id),
                    "name": journey.name,
                    "description": journey.description,
                    "activation_conditions": journey.activation_conditions,
                    "initial_state": journey.initial_state,
                    "states": {
                        name: {
                            "name": state.name,
                            "action": state.action,
                            "tools": state.tools,
                            "metadata": state.metadata,
                        }
                        for name, state in journey.states.items()
                    },
                    "transitions": [
                        {
                            "from_state": t.from_state,
                            "to_state": t.to_state,
                            "condition": t.condition,
                            "priority": t.priority,
                        }
                        for t in journey.transitions
                    ],
                    "enabled": journey.enabled,
                },
            )

            return journey

        except Exception as e:
            logger.error("Error fetching journey", journey_id=str(journey_id), error=str(e))
            raise

    async def get_journey_by_name(self, name: str) -> Optional[Journey]:
        """Get journey definition by name."""
        # Try to get ID from cache
        cached_id = await self.redis.get_l1(f"journey:name:{name}")
        if cached_id:
            return await self.get_journey(UUID(cached_id))

        # Fallback to database query
        row = await self.db.fetchrow(
            "SELECT id FROM journeys WHERE name = $1 AND enabled = true",
            name,
        )
        if row:
            return await self.get_journey(row["id"])

        return None

    async def get_all_journeys(self) -> List[Journey]:
        """Get all enabled journey definitions."""
        rows = await self.db.fetch(
            """
            SELECT id, name, description, activation_conditions,
                   initial_state, states, transitions, enabled,
                   created_at, updated_at
            FROM journeys
            WHERE enabled = true
            ORDER BY name
            """
        )

        return [
            Journey(
                id=row["id"],
                name=row["name"],
                description=row["description"],
                activation_conditions=row["activation_conditions"],
                initial_state=row["initial_state"],
                states={
                    name: JourneyState(**state_data)
                    for name, state_data in row["states"].items()
                },
                transitions=[JourneyTransition(**t) for t in row["transitions"]],
                enabled=row["enabled"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
            for row in rows
        ]

    async def create_context(
        self,
        session_id: str,
        journey: Journey,
        initial_variables: Optional[Dict[str, Any]] = None,
    ) -> JourneyContext:
        """Create a new journey context instance."""
        context_id = uuid7()
        now = datetime.utcnow()

        context = JourneyContext(
            id=context_id,
            session_id=session_id,
            journey_id=journey.id,
            journey_name=journey.name,
            current_state=journey.initial_state,
            variables=initial_variables or {},
            state_history=[],
            activated_at=now,
            created_at=now,
            updated_at=now,
        )

        # Add activation event to history
        context.add_to_history({
            "event": "journey_activated",
            "journey_name": journey.name,
            "initial_state": journey.initial_state,
        })

        # Persist to database
        await self.db.execute(
            """
            INSERT INTO journey_contexts
            (id, session_id, journey_id, current_state, variables,
             state_history, activated_at, created_at, updated_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            """,
            context.id,
            context.session_id,
            context.journey_id,
            context.current_state,
            json.dumps(context.variables),
            json.dumps(context.state_history),
            context.activated_at,
            context.created_at,
            context.updated_at,
        )

        logger.info(
            "Journey context created",
            context_id=str(context.id),
            session_id=session_id,
            journey_name=journey.name,
        )

        return context

    async def update_context(self, context: JourneyContext) -> None:
        """Update journey context in database."""
        context.updated_at = datetime.utcnow()

        await self.db.execute(
            """
            UPDATE journey_contexts
            SET current_state = $1,
                variables = $2,
                state_history = $3,
                completed_at = $4,
                updated_at = $5
            WHERE id = $6
            """,
            context.current_state,
            json.dumps(context.variables),
            json.dumps(context.state_history),
            context.completed_at,
            context.updated_at,
            context.id,
        )

        logger.debug(
            "Journey context updated",
            context_id=str(context.id),
            current_state=context.current_state,
        )

    async def get_active_context(self, session_id: str) -> Optional[JourneyContext]:
        """Get active journey context for a session."""
        row = await self.db.fetchrow(
            """
            SELECT id, session_id, journey_id, current_state, variables,
                   state_history, activated_at, completed_at, created_at, updated_at
            FROM journey_contexts
            WHERE session_id = $1 AND completed_at IS NULL
            ORDER BY activated_at DESC
            LIMIT 1
            """,
            session_id,
        )

        if not row:
            return None

        # Get journey name
        journey_row = await self.db.fetchrow(
            "SELECT name FROM journeys WHERE id = $1",
            row["journey_id"],
        )

        return JourneyContext(
            id=row["id"],
            session_id=row["session_id"],
            journey_id=row["journey_id"],
            journey_name=journey_row["name"] if journey_row else "unknown",
            current_state=row["current_state"],
            variables=row["variables"],
            state_history=row["state_history"],
            activated_at=row["activated_at"],
            completed_at=row["completed_at"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
