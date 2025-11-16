"""Journey-aware frame processor for Pipecat pipeline."""
from typing import Optional, AsyncGenerator

from pipecat.frames.frames import Frame, LLMMessagesFrame, SystemFrame
from pipecat.processors.frame_processor import FrameProcessor

from app.logging_config import get_logger
from app.flow_control.journey.store import JourneyStore
from app.flow_control.journey.matcher import JourneyMatcher
from app.flow_control.journey.engine import JourneyEngine
from app.flow_control.guideline.store import GuidelineStore
from app.flow_control.guideline.matcher import GuidelineMatcher

logger = get_logger(__name__)


class JourneyProcessor(FrameProcessor):
    """
    Custom processor that intercepts frames to inject journey context.

    This processor:
    1. Detects when user messages arrive (LLMMessagesFrame)
    2. Retrieves active journey context from Redis/database
    3. If no active journey, attempts activation via LLM
    4. Injects current state guidance into system prompt
    5. Matches and includes applicable guidelines
    """

    def __init__(
        self,
        session_id: str,
        db_pool,
        redis_client,
    ):
        super().__init__()
        self.session_id = session_id
        self.db_pool = db_pool
        self.redis_client = redis_client

        # Initialize engines
        journey_store = JourneyStore(db_pool, redis_client)
        journey_matcher = JourneyMatcher(journey_store, redis_client)
        self.journey_engine = JourneyEngine(journey_store, journey_matcher)

        guideline_store = GuidelineStore(db_pool, redis_client)
        self.guideline_matcher = GuidelineMatcher(guideline_store)

        self._initialized = False

        logger.info(
            "JourneyProcessor initialized",
            session_id=session_id,
        )

    async def _ensure_initialized(self) -> None:
        """Lazy initialization of engines on first use."""
        if not self._initialized:
            await self.journey_engine.initialize()
            await self.guideline_matcher.store.load_guideline_definitions()
            self._initialized = True

    async def process_frame(
        self, frame: Frame, direction: str
    ) -> AsyncGenerator[Frame, None]:
        """Process frames and inject journey context."""
        await self._ensure_initialized()

        if isinstance(frame, LLMMessagesFrame):
            # Extract user message from frame
            user_message = self._extract_user_message(frame)

            if user_message:
                # Process message through journey engine
                context, state, metadata = await self.journey_engine.process_message(
                    self.session_id, user_message
                )

                if context and state:
                    # Get journey definition
                    journey = await self.journey_engine.store.get_journey(context.journey_id)

                    if journey:
                        # Build journey guidance
                        journey_guidance = await self.journey_engine.get_journey_guidance(
                            journey, state
                        )

                        # Match applicable guidelines
                        guideline_matches = await self.guideline_matcher.match_guidelines(
                            user_message,
                            journey_id=context.journey_id,
                            state_name=context.current_state,
                            context_variables=context.variables,
                        )

                        # Inject into system prompt
                        frame = await self._inject_context(
                            frame, journey_guidance, guideline_matches
                        )

                        logger.info(
                            "Journey context injected",
                            session_id=self.session_id,
                            journey=journey.name,
                            state=state.name,
                            guidelines_matched=len(guideline_matches),
                            is_new=metadata.get("is_new_journey"),
                        )

        yield frame

    def _extract_user_message(self, frame: LLMMessagesFrame) -> Optional[str]:
        """Extract user message text from frame."""
        # LLMMessagesFrame contains messages list
        # The last user message is what we want
        if hasattr(frame, "messages") and frame.messages:
            for msg in reversed(frame.messages):
                if isinstance(msg, dict) and msg.get("role") == "user":
                    return msg.get("content", "")
        return None

    async def _inject_context(
        self,
        frame: LLMMessagesFrame,
        journey_guidance: str,
        guideline_matches: list,
    ) -> LLMMessagesFrame:
        """Inject journey and guideline context into system prompt."""
        # Build enhanced system prompt
        guideline_text = ""
        if guideline_matches:
            guideline_rules = [
                f"- {match.guideline.name}: {match.guideline.action}"
                for match in guideline_matches
            ]
            guideline_text = "\n\nACTIVE GUIDELINES (MUST FOLLOW):\n" + "\n".join(guideline_rules)

        enhanced_prompt = f"""
{journey_guidance}
{guideline_text}

Follow the journey state guidance and adhere to all active guidelines.
"""

        # Inject into frame's system message
        if hasattr(frame, "messages") and frame.messages:
            # Find or create system message
            system_msg_index = None
            for i, msg in enumerate(frame.messages):
                if isinstance(msg, dict) and msg.get("role") == "system":
                    system_msg_index = i
                    break

            if system_msg_index is not None:
                # Append to existing system message
                frame.messages[system_msg_index]["content"] += "\n" + enhanced_prompt
            else:
                # Insert new system message at beginning
                frame.messages.insert(0, {
                    "role": "system",
                    "content": enhanced_prompt
                })

        return frame
