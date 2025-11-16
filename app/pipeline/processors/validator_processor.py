"""Response validator frame processor for Pipecat pipeline."""
from typing import Optional, AsyncGenerator

from pipecat.frames.frames import Frame, TextFrame
from pipecat.processors.frame_processor import FrameProcessor

from app.logging_config import get_logger
from app.flow_control.validator.post_validator import ResponseValidator
from app.flow_control.journey.store import JourneyStore
from app.flow_control.guideline.store import GuidelineStore

logger = get_logger(__name__)


class ValidatorProcessor(FrameProcessor):
    """
    Custom processor that validates LLM responses against guidelines.

    This processor:
    1. Intercepts LLM-generated responses
    2. Validates against active guidelines using LLM structured output
    3. Detects violations (ARQ-inspired validation)
    4. Attempts auto-fix if violations found
    5. Logs validation results to audit table
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

        # Initialize validator
        self.validator = ResponseValidator(db_pool)

        # Initialize stores for fetching context
        self.journey_store = JourneyStore(db_pool, redis_client)
        self.guideline_store = GuidelineStore(db_pool, redis_client)

        logger.info(
            "ValidatorProcessor initialized",
            session_id=session_id,
        )

    async def process_frame(
        self, frame: Frame, direction: str
    ) -> AsyncGenerator[Frame, None]:
        """Process frames and validate responses."""
        if isinstance(frame, TextFrame):
            response_text = frame.text if hasattr(frame, "text") else ""

            if response_text:
                # Get active journey context
                context = await self.journey_store.get_active_context(self.session_id)

                if context:
                    # Get applicable guidelines
                    guidelines = await self.guideline_store.get_guidelines_by_scope(
                        journey_id=context.journey_id,
                        state_name=context.current_state,
                    )

                    if guidelines:
                        # Validate response
                        result = await self.validator.validate_response(
                            response_text,
                            guidelines,
                            self.session_id,
                            journey_id=context.journey_id,
                            context=context.variables,
                        )

                        # If invalid and auto-fixed, replace frame text
                        if not result.is_valid and result.fixed_response:
                            logger.warning(
                                "Response violated guidelines, using auto-fixed version",
                                session_id=self.session_id,
                                violations=len(result.violations),
                            )
                            frame.text = result.fixed_response
                        elif not result.is_valid:
                            logger.error(
                                "Response violated guidelines, no auto-fix available",
                                session_id=self.session_id,
                                violations=result.violations,
                            )

        yield frame
