"""Tool executor with timeout, caching, and rate limiting."""
from typing import Any, Dict, Optional
from dataclasses import dataclass
from datetime import datetime
import asyncio
import json
import hashlib

from prometheus_client import Counter, Histogram

from app.db.redis_client import RedisClient
from app.tools.registry import ToolRegistry, ToolDefinition
from app.logging_config import get_logger

logger = get_logger(__name__)

# Metrics
tool_calls_total = Counter(
    "tool_calls_total",
    "Total tool calls",
    ["tool_name", "status"],
)
tool_latency_seconds = Histogram(
    "tool_latency_seconds",
    "Tool execution latency",
    ["tool_name"],
)


@dataclass
class ToolContext:
    """Context for tool execution."""

    session_id: str
    user_id: Optional[str] = None
    journey_id: Optional[str] = None
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class ToolExecutionError(Exception):
    """Raised when tool execution fails."""

    pass


class RateLimitExceededError(Exception):
    """Raised when rate limit is exceeded."""

    pass


class ToolExecutor:
    """Executes tools with timeout, caching, and rate limiting."""

    def __init__(self, registry: ToolRegistry, redis_client: RedisClient):
        self.registry = registry
        self.redis = redis_client

    def _compute_cache_key(
        self, tool_name: str, arguments: Dict[str, Any]
    ) -> str:
        """Compute cache key for tool call."""
        # Sort arguments for consistent hashing
        args_str = json.dumps(arguments, sort_keys=True)
        args_hash = hashlib.sha256(args_str.encode()).hexdigest()[:16]
        return f"tool:result:{tool_name}:{args_hash}"

    def _compute_rate_limit_key(
        self, tool_name: str, identifier: str
    ) -> str:
        """Compute rate limit key."""
        return f"tool:ratelimit:{tool_name}:{identifier}"

    async def _check_rate_limit(
        self, tool_def: ToolDefinition, arguments: Dict[str, Any]
    ) -> None:
        """Check if rate limit is exceeded."""
        if not tool_def.rate_limit:
            return

        # Extract identifier from arguments (e.g., phone number)
        identifier_field = tool_def.rate_limit.get("identifier_field", "phone")
        identifier = arguments.get(identifier_field)

        if not identifier:
            # No identifier, skip rate limiting
            return

        rate_limit_key = self._compute_rate_limit_key(tool_def.name, identifier)
        max_calls = tool_def.rate_limit.get("max_calls", 3)
        window = tool_def.rate_limit.get("window", 3600)  # seconds

        # Get current call count
        current_count_str = await self.redis.get(rate_limit_key)
        current_count = int(current_count_str) if current_count_str else 0

        if current_count >= max_calls:
            logger.warning(
                "Rate limit exceeded",
                tool_name=tool_def.name,
                identifier=identifier,
                max_calls=max_calls,
                window=window,
            )
            raise RateLimitExceededError(
                f"Rate limit exceeded for {tool_def.name}: "
                f"{max_calls} calls per {window}s"
            )

        # Increment counter
        if current_count == 0:
            # Set with TTL
            await self.redis.set(rate_limit_key, "1", ttl=window)
        else:
            # Increment
            if self.redis.client:
                await self.redis.client.incr(rate_limit_key)

    async def execute(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        context: ToolContext,
    ) -> Any:
        """
        Execute a tool with timeout protection and caching.

        Args:
            tool_name: Name of the tool to execute
            arguments: Tool arguments
            context: Execution context

        Returns:
            Tool result

        Raises:
            ToolExecutionError: If tool execution fails
            RateLimitExceededError: If rate limit is exceeded
        """
        start_time = datetime.utcnow()

        # Get tool definition
        tool_def = self.registry.get(tool_name)
        if not tool_def:
            logger.error("Tool not found", tool_name=tool_name)
            tool_calls_total.labels(tool_name=tool_name, status="not_found").inc()
            raise ToolExecutionError(f"Tool {tool_name} not found")

        # Check rate limit
        try:
            await self._check_rate_limit(tool_def, arguments)
        except RateLimitExceededError:
            tool_calls_total.labels(tool_name=tool_name, status="rate_limited").inc()
            raise

        # Check cache
        if tool_def.cache_ttl:
            cache_key = self._compute_cache_key(tool_name, arguments)
            cached_result = await self.redis.get_l3(cache_key)

            if cached_result is not None:
                elapsed = (datetime.utcnow() - start_time).total_seconds()
                logger.info(
                    "Tool cache hit",
                    tool_name=tool_name,
                    latency_ms=f"{elapsed * 1000:.1f}",
                )
                tool_calls_total.labels(tool_name=tool_name, status="cache_hit").inc()
                tool_latency_seconds.labels(tool_name=tool_name).observe(elapsed)
                return cached_result

        # Execute tool with timeout
        try:
            result = await asyncio.wait_for(
                tool_def.function(**arguments),
                timeout=tool_def.timeout,
            )

            # Cache result if TTL is set
            if tool_def.cache_ttl:
                cache_key = self._compute_cache_key(tool_name, arguments)
                await self.redis.cache_l3(cache_key, result)

            elapsed = (datetime.utcnow() - start_time).total_seconds()

            logger.info(
                "Tool executed successfully",
                tool_name=tool_name,
                latency_ms=f"{elapsed * 1000:.1f}",
                session_id=context.session_id,
            )

            tool_calls_total.labels(tool_name=tool_name, status="success").inc()
            tool_latency_seconds.labels(tool_name=tool_name).observe(elapsed)

            return result

        except asyncio.TimeoutError:
            elapsed = (datetime.utcnow() - start_time).total_seconds()
            logger.error(
                "Tool execution timeout",
                tool_name=tool_name,
                timeout=tool_def.timeout,
                latency_ms=f"{elapsed * 1000:.1f}",
            )
            tool_calls_total.labels(tool_name=tool_name, status="timeout").inc()
            raise ToolExecutionError(
                f"Tool {tool_name} execution timed out after {tool_def.timeout}s"
            )

        except Exception as e:
            elapsed = (datetime.utcnow() - start_time).total_seconds()
            logger.error(
                "Tool execution failed",
                tool_name=tool_name,
                error=str(e),
                latency_ms=f"{elapsed * 1000:.1f}",
            )
            tool_calls_total.labels(tool_name=tool_name, status="error").inc()
            raise ToolExecutionError(f"Tool {tool_name} execution failed: {str(e)}")
