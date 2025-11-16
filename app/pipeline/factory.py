"""Pipecat pipeline factory with built-in services."""
from typing import Optional

from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.task import PipelineTask
from pipecat.services.deepgram import DeepgramSTTService
from pipecat.services.openai import OpenAILLMService, OpenAITTSService
from pipecat.processors.aggregators.llm_response import LLMUserResponseAggregator
from pipecat.processors.frame_processor import FrameProcessor

from app.config import config
from app.logging_config import get_logger
from app.pipeline.processors.journey_processor import JourneyProcessor
from app.pipeline.processors.validator_processor import ValidatorProcessor

logger = get_logger(__name__)


class PipecatPipelineFactory:
    """Factory for creating Pipecat pipelines with all services."""

    def __init__(self):
        self.config = config

    def create_stt_service(self) -> DeepgramSTTService:
        """Create Deepgram STT service with Nova-3 model."""
        logger.info("Creating DeepgramSTTService with Nova-3 model")

        return DeepgramSTTService(
            api_key=self.config.api.deepgram_api_key,
            model="nova-3",
            language="en-US",
            interim_results=True,
        )

    def create_llm_service(
        self,
        system_prompt: Optional[str] = None,
        tools: Optional[list] = None,
    ) -> OpenAILLMService:
        """Create OpenAI LLM service with gpt-4o."""
        logger.info("Creating OpenAILLMService with gpt-4o")

        default_prompt = (
            "You are a helpful AI assistant for an insurance call center. "
            "You help customers with claims inquiries, filing claims, and answering policy questions. "
            "Always be professional, empathetic, and accurate."
        )

        return OpenAILLMService(
            api_key=self.config.api.openai_api_key,
            model="gpt-4o",
            system_prompt=system_prompt or default_prompt,
            tools=tools or [],
        )

    def create_tts_service(self) -> OpenAITTSService:
        """Create OpenAI TTS service with tts-1 model."""
        logger.info("Creating OpenAITTSService with tts-1, voice=alloy")

        return OpenAITTSService(
            api_key=self.config.api.openai_api_key,
            model="tts-1",
            voice="alloy",
            speed=1.0,
        )

    def create_journey_processor(
        self,
        session_id: str,
        db_pool,
        redis_client,
    ) -> JourneyProcessor:
        """Create journey-aware processor."""
        logger.info("Creating JourneyProcessor", session_id=session_id)
        return JourneyProcessor(
            session_id=session_id,
            db_pool=db_pool,
            redis_client=redis_client,
        )

    def create_validator_processor(
        self,
        session_id: str,
        db_pool,
        redis_client,
    ) -> ValidatorProcessor:
        """Create response validator processor."""
        logger.info("Creating ValidatorProcessor", session_id=session_id)
        return ValidatorProcessor(
            session_id=session_id,
            db_pool=db_pool,
            redis_client=redis_client,
        )

    async def create_pipeline(
        self,
        session_id: str,
        transport,
        db_pool,
        redis_client,
    ) -> Pipeline:
        """
        Create complete Pipecat pipeline.

        Pipeline flow:
        SIP Transport → Local VAD → DeepgramSTT → Local Turn Detection →
        JourneyProcessor → OpenAI LLM → ValidatorProcessor → OpenAI TTS → SIP Transport
        """
        logger.info("Building Pipecat pipeline", session_id=session_id)

        # Create services
        stt_service = self.create_stt_service()
        llm_service = self.create_llm_service()
        tts_service = self.create_tts_service()

        # Create custom processors
        journey_processor = self.create_journey_processor(
            session_id, db_pool, redis_client
        )
        validator_processor = self.create_validator_processor(
            session_id, db_pool, redis_client
        )

        # Create user response aggregator for LLM
        user_aggregator = LLMUserResponseAggregator()

        # Build pipeline
        # Note: VAD and Turn Detection would be added here once we determine
        # the specific Pipecat processors to use (built-in or custom)
        pipeline = Pipeline(
            [
                transport.input(),
                stt_service,
                user_aggregator,
                journey_processor,
                llm_service,
                validator_processor,
                tts_service,
                transport.output(),
            ]
        )

        logger.info("Pipeline created successfully", session_id=session_id)
        return pipeline

    async def create_task(
        self,
        pipeline: Pipeline,
        session_id: str,
    ) -> PipelineTask:
        """Create pipeline task for execution."""
        logger.info("Creating pipeline task", session_id=session_id)

        task = PipelineTask(pipeline)
        return task


# Global factory instance
pipeline_factory = PipecatPipelineFactory()
