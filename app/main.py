"""Main application entry point."""
import asyncio
from typing import Optional
from fastapi import FastAPI
from prometheus_client import Counter, Histogram, Gauge, generate_latest
from fastapi.responses import Response
import uvicorn

from app.config import config
from app.logging_config import setup_logging, get_logger
from app.db.connection import db_pool
from app.db.redis_client import redis_client
from app.telephony.sip_server import init_sip_server

setup_logging()
logger = get_logger(__name__)

# Global SIP server task
sip_server_task: Optional[asyncio.Task] = None

app = FastAPI(title="AI-Native Call Center", version="0.1.0")

journey_activations_total = Counter(
    "journey_activations_total", "Total journey activations", ["journey_name"]
)
guideline_matches_total = Counter(
    "guideline_matches_total", "Total guideline matches", ["guideline_id"]
)
tool_latency_seconds = Histogram(
    "tool_latency_seconds", "Tool execution latency", ["tool_name"]
)
response_latency_e2e_seconds = Histogram(
    "response_latency_e2e_seconds", "End-to-end response latency"
)
active_calls = Gauge("active_calls", "Number of active calls")


@app.get("/")
async def root():
    """Health check endpoint."""
    return {"status": "ok", "service": "ai-native-callcenter"}


@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint."""
    return Response(content=generate_latest(), media_type="text/plain")


@app.on_event("startup")
async def startup():
    """Initialize services on startup."""
    global sip_server_task

    logger.info("Starting AI-Native Call Center")

    try:
        # Initialize database pool
        logger.info("Connecting to PostgreSQL...")
        await db_pool.connect()

        # Initialize Redis client
        logger.info("Connecting to Redis...")
        await redis_client.connect()

        # Initialize and start SIP server
        logger.info("Initializing SIP server...")
        sip_server = await init_sip_server(db_pool, redis_client)
        sip_server_task = asyncio.create_task(sip_server.start())

        logger.info(
            "All services started successfully",
            postgres=f"{config.database.host}:{config.database.port}",
            redis=f"{config.redis.host}:{config.redis.port}",
            sip=f"{config.sip.host}:{config.sip.port}",
        )

    except Exception as e:
        logger.error("Failed to start services", error=str(e))
        raise


@app.on_event("shutdown")
async def shutdown():
    """Cleanup on shutdown."""
    global sip_server_task

    logger.info("Shutting down AI-Native Call Center")

    try:
        # Stop SIP server
        if sip_server_task:
            logger.info("Stopping SIP server...")
            sip_server_task.cancel()
            try:
                await sip_server_task
            except asyncio.CancelledError:
                pass

        # Close Redis connection
        logger.info("Closing Redis connection...")
        await redis_client.close()

        # Close database pool
        logger.info("Closing database pool...")
        await db_pool.close()

        logger.info("Shutdown complete")

    except Exception as e:
        logger.error("Error during shutdown", error=str(e))


def main():
    """Run the application."""
    logger.info("Starting FastAPI server")
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        log_config=None,
    )


if __name__ == "__main__":
    main()
