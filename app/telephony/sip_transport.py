"""Custom Pipecat transport layer wrapping sip-to-ai RTP streams."""
from typing import Optional
import asyncio

from pipecat.transports.base_transport import BaseTransport
from pipecat.frames.frames import Frame, AudioRawFrame, StartFrame, EndFrame

from app.logging_config import get_logger
from app.telephony.rtp_session import RTPSession

logger = get_logger(__name__)


class SIPTransport(BaseTransport):
    """
    Custom Pipecat transport that wraps sip-to-ai RTP streams.

    This transport:
    - Receives RTP audio from sip-to-ai and converts to Pipecat AudioRawFrames
    - Sends Pipecat audio output back to sip-to-ai RTP
    - Handles call lifecycle (start, end)
    """

    def __init__(
        self,
        rtp_session: RTPSession,
        session_id: str,
        sample_rate: int = 16000,
        num_channels: int = 1,
    ):
        """
        Initialize SIP transport.

        Args:
            rtp_session: RTP session handling audio I/O
            session_id: Unique session identifier
            sample_rate: Audio sample rate (default 16kHz for Deepgram)
            num_channels: Number of audio channels (default 1 for mono)
        """
        super().__init__()
        self.rtp_session = rtp_session
        self.session_id = session_id
        self.sample_rate = sample_rate
        self.num_channels = num_channels
        self._running = False
        self._input_task: Optional[asyncio.Task] = None

        logger.info(
            "SIPTransport initialized",
            session_id=session_id,
            sample_rate=sample_rate,
            num_channels=num_channels,
        )

    async def start(self) -> None:
        """Start the transport and begin processing audio."""
        if self._running:
            logger.warning("Transport already running", session_id=self.session_id)
            return

        self._running = True
        logger.info("Starting SIP transport", session_id=self.session_id)

        # Send start frame to pipeline
        await self.push_frame(StartFrame())

        # Start input audio processing task
        self._input_task = asyncio.create_task(self._process_input_audio())

    async def stop(self) -> None:
        """Stop the transport and cleanup."""
        if not self._running:
            return

        logger.info("Stopping SIP transport", session_id=self.session_id)
        self._running = False

        # Cancel input task
        if self._input_task:
            self._input_task.cancel()
            try:
                await self._input_task
            except asyncio.CancelledError:
                pass

        # Send end frame to pipeline
        await self.push_frame(EndFrame())

        # Close RTP session
        await self.rtp_session.close()

        logger.info("SIP transport stopped", session_id=self.session_id)

    async def _process_input_audio(self) -> None:
        """Process incoming RTP audio and push to pipeline."""
        logger.info("Started input audio processing", session_id=self.session_id)

        try:
            while self._running:
                # Read PCM audio from RTP session (20ms chunks)
                pcm_data = await self.rtp_session.read_audio()

                if not pcm_data:
                    # No more audio, call ended
                    logger.info("No more audio data", session_id=self.session_id)
                    break

                # Convert to Pipecat AudioRawFrame
                frame = AudioRawFrame(
                    audio=pcm_data,
                    sample_rate=self.sample_rate,
                    num_channels=self.num_channels,
                )

                # Push to pipeline
                await self.push_frame(frame)

        except asyncio.CancelledError:
            logger.info("Input audio processing cancelled", session_id=self.session_id)
        except Exception as e:
            logger.error(
                "Error processing input audio",
                session_id=self.session_id,
                error=str(e),
            )
        finally:
            # Signal end of call
            await self.stop()

    async def write_frame(self, frame: Frame) -> None:
        """
        Write frame to output (RTP).

        Called by pipeline to send audio back to caller.
        """
        if isinstance(frame, AudioRawFrame):
            # Send PCM audio to RTP session
            await self.rtp_session.write_audio(frame.audio)

            logger.debug(
                "Sent audio frame to RTP",
                session_id=self.session_id,
                audio_length=len(frame.audio),
            )

    def input(self):
        """Return input interface for pipeline."""
        return self

    def output(self):
        """Return output interface for pipeline."""
        return self
