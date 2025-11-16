"""Journey engine for managing conversation state machines."""
from typing import Optional, Dict, Any, Tuple
from datetime import datetime

from app.flow_control.journey.models import Journey, JourneyContext, JourneyState
from app.flow_control.journey.store import JourneyStore
from app.flow_control.journey.matcher import JourneyMatcher
from app.logging_config import get_logger

logger = get_logger(__name__)


class JourneyEngine:
    """
    Manages journey lifecycle: activation, state transitions, completion.

    Latency target: <30ms (P95), cache hit <5ms
    """

    def __init__(self, store: JourneyStore, matcher: JourneyMatcher):
        self.store = store
        self.matcher = matcher

    async def initialize(self) -> None:
        """Load journey definitions into cache."""
        await self.store.load_journey_definitions()
        logger.info("Journey engine initialized")

    async def process_message(
        self,
        session_id: str,
        user_message: str,
        context_hints: Optional[Dict[str, Any]] = None,
    ) -> Tuple[Optional[JourneyContext], Optional[JourneyState], Dict[str, Any]]:
        """
        Process user message and manage journey state.

        Returns:
            (JourneyContext, CurrentState, Metadata) tuple
            - JourneyContext: Active journey context (or None)
            - CurrentState: Current state definition
            - Metadata: Additional info (is_new, transition_occurred, etc.)
        """
        start_time = datetime.utcnow()

        # Check for active journey context
        context = await self.store.get_active_context(session_id)

        metadata: Dict[str, Any] = {
            "is_new_journey": False,
            "transition_occurred": False,
            "journey_activated": False,
        }

        # If no active journey, try to activate one
        if not context:
            journey = await self.matcher.activate_journey(
                session_id, user_message, context_hints
            )

            if journey:
                # Create new journey context
                context = await self.store.create_context(
                    session_id, journey, initial_variables=context_hints or {}
                )
                metadata["is_new_journey"] = True
                metadata["journey_activated"] = True

                logger.info(
                    "Journey activated",
                    session_id=session_id,
                    journey_name=journey.name,
                    initial_state=context.current_state,
                )
            else:
                # No journey matched
                logger.debug("No journey activated", session_id=session_id)
                elapsed = (datetime.utcnow() - start_time).total_seconds() * 1000
                logger.debug(f"process_message completed in {elapsed:.1f}ms")
                return None, None, metadata

        # Get journey definition
        journey = await self.store.get_journey(context.journey_id)

        if not journey:
            logger.error(
                "Journey not found",
                journey_id=str(context.journey_id),
                session_id=session_id,
            )
            return context, None, metadata

        # Get current state
        current_state = journey.get_state(context.current_state)

        if not current_state:
            logger.error(
                "Current state not found in journey",
                journey=journey.name,
                state=context.current_state,
            )
            return context, None, metadata

        # Check for state transition
        target_state = await self.matcher.can_transition(
            journey, context.current_state, user_message, context.variables
        )

        if target_state:
            # Execute transition
            await self.execute_transition(context, journey, target_state, user_message)
            metadata["transition_occurred"] = True
            current_state = journey.get_state(target_state)

        elapsed = (datetime.utcnow() - start_time).total_seconds() * 1000
        logger.debug(
            "process_message completed",
            session_id=session_id,
            journey=journey.name,
            state=context.current_state,
            latency_ms=f"{elapsed:.1f}",
        )

        return context, current_state, metadata

    async def execute_transition(
        self,
        context: JourneyContext,
        journey: Journey,
        target_state: str,
        reason: str = "",
    ) -> None:
        """Execute a state transition and persist context."""
        old_state = context.current_state
        context.transition_to(target_state, reason)

        # Persist updated context
        await self.store.update_context(context)

        logger.info(
            "State transition executed",
            session_id=context.session_id,
            journey=journey.name,
            from_state=old_state,
            to_state=target_state,
            reason=reason,
        )

    async def complete_journey(
        self, context: JourneyContext, reason: str = ""
    ) -> None:
        """Mark journey as completed."""
        if not context.is_active():
            logger.warning(
                "Attempt to complete already completed journey",
                context_id=str(context.id),
            )
            return

        context.complete()
        await self.store.update_context(context)

        logger.info(
            "Journey completed",
            session_id=context.session_id,
            journey_name=context.journey_name,
            final_state=context.current_state,
            reason=reason,
        )

    async def set_context_variable(
        self, context: JourneyContext, key: str, value: Any
    ) -> None:
        """Set a context variable and persist."""
        context.set_variable(key, value)
        await self.store.update_context(context)

        logger.debug(
            "Context variable set",
            session_id=context.session_id,
            key=key,
            value=str(value)[:100],  # Truncate for logging
        )

    async def get_journey_guidance(
        self, journey: Journey, state: JourneyState
    ) -> str:
        """
        Build guidance text for current journey state.

        This is injected into the LLM system prompt.
        """
        guidance_parts = [
            f"Current Journey: {journey.name}",
            f"Journey Description: {journey.description or 'N/A'}",
            f"Current State: {state.name}",
            f"State Action: {state.action}",
        ]

        if state.tools:
            guidance_parts.append(f"Available Tools: {', '.join(state.tools)}")

        # Get available transitions
        transitions = journey.get_transitions_from(state.name)
        if transitions:
            transition_list = [
                f"  - To '{t.to_state}' when: {t.condition}"
                for t in sorted(transitions, key=lambda x: x.priority, reverse=True)
            ]
            guidance_parts.append("Possible Transitions:")
            guidance_parts.extend(transition_list)

        return "\n".join(guidance_parts)
