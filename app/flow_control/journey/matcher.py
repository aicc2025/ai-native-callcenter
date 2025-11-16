"""Journey activation matcher using LLM structured output."""
from typing import Optional, List, Dict, Any
import json

from openai import AsyncOpenAI

from app.config import config
from app.flow_control.journey.models import Journey
from app.flow_control.journey.store import JourneyStore
from app.db.redis_client import RedisClient
from app.logging_config import get_logger

logger = get_logger(__name__)


class JourneyMatcher:
    """Matches user messages to journeys using LLM structured output."""

    def __init__(self, store: JourneyStore, redis_client: RedisClient):
        self.store = store
        self.redis = redis_client
        self.openai = AsyncOpenAI(api_key=config.api.openai_api_key)

    async def activate_journey(
        self,
        session_id: str,
        user_message: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Optional[Journey]:
        """
        Attempt to activate a journey based on user message.

        Uses LLM structured output to match against activation conditions.
        Results cached in L2 (5min TTL) for repeated activations.

        Returns:
            Matched Journey or None if no match
        """
        # Check L2 cache for recent activation
        cache_key = f"activation:{session_id}:{hash(user_message)}"
        cached_result = await self.redis.get_l2(cache_key)

        if cached_result:
            logger.debug("Journey activation cache hit", session_id=session_id)
            if cached_result.get("journey_id"):
                return await self.store.get_journey(cached_result["journey_id"])
            return None

        # Get all available journeys
        journeys = await self.store.get_all_journeys()

        if not journeys:
            logger.warning("No journeys available for activation")
            return None

        # Build activation prompt for LLM
        activation_candidates = [
            {
                "journey_id": str(j.id),
                "journey_name": j.name,
                "description": j.description or "",
                "activation_conditions": j.activation_conditions,
            }
            for j in journeys
        ]

        system_prompt = """You are a journey activation classifier for an insurance call center.
Your task is to determine which conversation journey (if any) matches the user's message.

Analyze the user's message and compare it against the activation conditions of each journey.
Return the journey that best matches, or null if no journey matches.

Consider:
- User intent (what they want to do)
- Keywords and phrases
- Context if provided
"""

        user_prompt = f"""User message: "{user_message}"

Context: {json.dumps(context or {}, indent=2)}

Available journeys:
{json.dumps(activation_candidates, indent=2)}

Which journey should be activated? Return your answer in this exact JSON format:
{{
  "matched": true/false,
  "journey_id": "uuid-of-matched-journey" or null,
  "journey_name": "name-of-journey" or null,
  "confidence": 0.0-1.0,
  "reasoning": "brief explanation"
}}
"""

        try:
            # Call LLM with structured output
            response = await self.openai.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.0,
            )

            result = json.loads(response.choices[0].message.content)

            logger.info(
                "Journey activation result",
                session_id=session_id,
                matched=result.get("matched"),
                journey_name=result.get("journey_name"),
                confidence=result.get("confidence"),
                reasoning=result.get("reasoning"),
            )

            # Cache result to L2 (5min)
            await self.redis.cache_l2(cache_key, result)

            # Return matched journey
            if result.get("matched") and result.get("journey_id"):
                from uuid import UUID

                journey_id = UUID(result["journey_id"])
                return await self.store.get_journey(journey_id)

            return None

        except Exception as e:
            logger.error(
                "Error during journey activation",
                session_id=session_id,
                error=str(e),
            )
            return None

    async def can_transition(
        self,
        journey: Journey,
        current_state: str,
        user_message: str,
        context_variables: Dict[str, Any],
    ) -> Optional[str]:
        """
        Check if a state transition is possible based on user message.

        Returns:
            Target state name if transition allowed, None otherwise
        """
        transitions = journey.get_transitions_from(current_state)

        if not transitions:
            logger.debug(
                "No transitions available",
                journey=journey.name,
                current_state=current_state,
            )
            return None

        # Build transition evaluation prompt
        transition_candidates = [
            {
                "to_state": t.to_state,
                "condition": t.condition,
                "priority": t.priority,
            }
            for t in sorted(transitions, key=lambda x: x.priority, reverse=True)
        ]

        system_prompt = """You are a state transition evaluator for conversation flows.
Determine if any transition condition is met based on the user's message and context variables.

If multiple transitions match, choose the one with highest priority.
Return null if no transition condition is met.
"""

        user_prompt = f"""Current state: {current_state}
User message: "{user_message}"
Context variables: {json.dumps(context_variables, indent=2)}

Available transitions:
{json.dumps(transition_candidates, indent=2)}

Which transition (if any) should be taken? Return in this JSON format:
{{
  "should_transition": true/false,
  "to_state": "target-state-name" or null,
  "reasoning": "brief explanation"
}}
"""

        try:
            response = await self.openai.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.0,
            )

            result = json.loads(response.choices[0].message.content)

            logger.debug(
                "Transition evaluation result",
                journey=journey.name,
                current_state=current_state,
                should_transition=result.get("should_transition"),
                to_state=result.get("to_state"),
                reasoning=result.get("reasoning"),
            )

            if result.get("should_transition") and result.get("to_state"):
                return result["to_state"]

            return None

        except Exception as e:
            logger.error(
                "Error evaluating transition",
                journey=journey.name,
                current_state=current_state,
                error=str(e),
            )
            return None
