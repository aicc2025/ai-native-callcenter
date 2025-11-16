"""SIP server using sip-to-ai library to handle incoming calls."""
import asyncio
from typing import Optional
import uuid

from app.config import config
from app.logging_config import get_logger
from app.telephony.rtp_session import RTPSession
from app.telephony.sip_transport import SIPTransport
from app.pipeline.factory import pipeline_factory

logger = get_logger(__name__)


class SIPServer:
    """
    SIP server that accepts incoming calls and routes to Pipecat pipelines.

    This server:
    - Listens on configured SIP port (default 5060)
    - Accepts INVITE from any IP (no auth for MVP)
    - Negotiates G.711 μ-law codec
    - Creates RTP session and Pipecat pipeline for each call
    - Handles call termination and cleanup

    Week 2 TODO: Integrate with actual sip-to-ai library
    This is currently a placeholder implementation showing the architecture.
    """

    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 5060,
        db_pool=None,
        redis_client=None,
    ):
        """
        Initialize SIP server.

        Args:
            host: Bind address (default 0.0.0.0 for all interfaces)
            port: SIP port (default 5060)
            db_pool: Database connection pool
            redis_client: Redis client for caching
        """
        self.host = host
        self.port = port
        self.db_pool = db_pool
        self.redis_client = redis_client
        self._running = False
        self._active_calls: dict[str, dict] = {}

        logger.info(
            "SIPServer initialized",
            host=host,
            port=port,
        )

    async def start(self) -> None:
        """Start the SIP server and begin accepting calls."""
        if self._running:
            logger.warning("SIP server already running")
            return

        self._running = True
        logger.info("Starting SIP server", host=self.host, port=self.port)

        # TODO Week 2: Initialize sip-to-ai server
        # TODO Week 2: Bind to port and start listening
        # TODO Week 2: Register INVITE handler

        # Placeholder: Just log that we're "running"
        logger.info("SIP server started (placeholder)", active_calls=0)

        # In real implementation, this would run the sip-to-ai event loop
        # For now, just keep running
        try:
            while self._running:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            logger.info("SIP server task cancelled")

    async def stop(self) -> None:
        """Stop the SIP server and cleanup."""
        if not self._running:
            return

        logger.info("Stopping SIP server")
        self._running = False

        # Terminate all active calls
        for call_id in list(self._active_calls.keys()):
            await self._end_call(call_id)

        # TODO Week 2: Shutdown sip-to-ai server

        logger.info("SIP server stopped")

    async def handle_invite(
        self,
        call_id: str,
        from_uri: str,
        to_uri: str,
        remote_addr: tuple[str, int],
    ) -> None:
        """
        Handle incoming SIP INVITE.

        Args:
            call_id: Unique call identifier
            from_uri: Caller SIP URI
            to_uri: Called SIP URI
            remote_addr: Remote RTP endpoint (host, port)
        """
        logger.info(
            "Received INVITE",
            call_id=call_id,
            from_uri=from_uri,
            to_uri=to_uri,
            remote_addr=remote_addr,
        )

        try:
            # Generate session ID
            session_id = str(uuid.uuid4())

            # TODO Week 2: Accept call with SDP (G.711 μ-law)
            # TODO Week 2: Get local RTP port

            # Create RTP session
            rtp_session = RTPSession(
                call_id=call_id,
                remote_addr=remote_addr,
                codec="PCMU",
            )

            # Create SIP transport
            sip_transport = SIPTransport(
                rtp_session=rtp_session,
                session_id=session_id,
            )

            # Create Pipecat pipeline
            pipeline = await pipeline_factory.create_pipeline(
                session_id=session_id,
                transport=sip_transport,
                db_pool=self.db_pool,
                redis_client=self.redis_client,
            )

            # Create pipeline task
            task = await pipeline_factory.create_task(
                pipeline=pipeline,
                session_id=session_id,
            )

            # Store call info
            self._active_calls[call_id] = {
                "session_id": session_id,
                "from_uri": from_uri,
                "to_uri": to_uri,
                "transport": sip_transport,
                "pipeline": pipeline,
                "task": task,
                "rtp_session": rtp_session,
            }

            # Start transport and pipeline
            await sip_transport.start()
            asyncio.create_task(task.run())

            logger.info(
                "Call established",
                call_id=call_id,
                session_id=session_id,
                active_calls=len(self._active_calls),
            )

        except Exception as e:
            logger.error(
                "Error handling INVITE",
                call_id=call_id,
                error=str(e),
            )
            # TODO Week 2: Send SIP error response

    async def handle_bye(self, call_id: str) -> None:
        """
        Handle SIP BYE (call termination).

        Args:
            call_id: Call identifier
        """
        logger.info("Received BYE", call_id=call_id)
        await self._end_call(call_id)

    async def _end_call(self, call_id: str) -> None:
        """End a call and cleanup resources."""
        if call_id not in self._active_calls:
            logger.warning("Call not found", call_id=call_id)
            return

        call_info = self._active_calls[call_id]
        logger.info("Ending call", call_id=call_id, session_id=call_info["session_id"])

        try:
            # Stop transport (this will stop pipeline too)
            await call_info["transport"].stop()

            # TODO Week 2: Persist call metadata to database
            # - Duration
            # - Journeys activated
            # - Tools called
            # - Transcript

            logger.info(
                "Call ended and metadata persisted (placeholder)",
                call_id=call_id,
                session_id=call_info["session_id"],
            )

        except Exception as e:
            logger.error(
                "Error ending call",
                call_id=call_id,
                error=str(e),
            )
        finally:
            # Remove from active calls
            del self._active_calls[call_id]
            logger.info("Call cleaned up", call_id=call_id, active_calls=len(self._active_calls))


# Global server instance (initialized in main.py)
sip_server: Optional[SIPServer] = None


async def init_sip_server(db_pool, redis_client) -> SIPServer:
    """Initialize and return SIP server instance."""
    global sip_server

    sip_server = SIPServer(
        host=config.sip.host,
        port=config.sip.port,
        db_pool=db_pool,
        redis_client=redis_client,
    )

    return sip_server
