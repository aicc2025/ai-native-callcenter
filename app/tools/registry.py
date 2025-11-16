"""Tool registry with decorator for function calling."""
from typing import Callable, Dict, Any, Optional, List
from dataclasses import dataclass, field
from functools import wraps
import inspect

from app.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class ToolDefinition:
    """Definition of a callable tool."""

    name: str
    description: str
    function: Callable
    parameters: Dict[str, Any]
    cache_ttl: Optional[int] = None  # Cache TTL in seconds (None = no cache)
    timeout: int = 5  # Execution timeout in seconds
    rate_limit: Optional[Dict[str, Any]] = None  # Rate limiting config

    def to_openai_function(self) -> Dict[str, Any]:
        """Convert to OpenAI function calling format."""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
        }


class ToolRegistry:
    """Registry for managing callable tools."""

    def __init__(self):
        self._tools: Dict[str, ToolDefinition] = {}

    def register(
        self,
        name: str,
        description: str,
        parameters: Dict[str, Any],
        cache_ttl: Optional[int] = None,
        timeout: int = 5,
        rate_limit: Optional[Dict[str, Any]] = None,
    ) -> Callable:
        """
        Decorator to register a function as a tool.

        Args:
            name: Tool name
            description: Tool description
            parameters: JSON Schema for parameters
            cache_ttl: Cache TTL in seconds (None = no cache, 1800 = 30min default)
            timeout: Execution timeout in seconds
            rate_limit: Rate limiting config (e.g., {"max_calls": 3, "window": 3600})

        Example:
            @registry.register(
                name="get_claim_status",
                description="Get the current status of a claim",
                parameters={
                    "type": "object",
                    "properties": {
                        "claim_id": {"type": "string", "description": "Claim ID"}
                    },
                    "required": ["claim_id"]
                },
                cache_ttl=1800  # 30 minutes
            )
            async def get_claim_status(claim_id: str) -> dict:
                ...
        """

        def decorator(func: Callable) -> Callable:
            # Validate function is async
            if not inspect.iscoroutinefunction(func):
                raise ValueError(f"Tool function {name} must be async")

            # Register tool
            tool_def = ToolDefinition(
                name=name,
                description=description,
                function=func,
                parameters=parameters,
                cache_ttl=cache_ttl,
                timeout=timeout,
                rate_limit=rate_limit,
            )
            self._tools[name] = tool_def

            logger.info(
                "Tool registered",
                name=name,
                cache_ttl=cache_ttl,
                timeout=timeout,
                has_rate_limit=rate_limit is not None,
            )

            # Return wrapped function
            @wraps(func)
            async def wrapper(*args, **kwargs):
                return await func(*args, **kwargs)

            return wrapper

        return decorator

    def get(self, name: str) -> Optional[ToolDefinition]:
        """Get tool definition by name."""
        return self._tools.get(name)

    def get_all(self) -> Dict[str, ToolDefinition]:
        """Get all registered tools."""
        return self._tools.copy()

    def get_openai_functions(self) -> List[Dict[str, Any]]:
        """Get all tools in OpenAI function calling format."""
        return [tool.to_openai_function() for tool in self._tools.values()]

    def exists(self, name: str) -> bool:
        """Check if tool exists."""
        return name in self._tools

    def unregister(self, name: str) -> bool:
        """Unregister a tool."""
        if name in self._tools:
            del self._tools[name]
            logger.info("Tool unregistered", name=name)
            return True
        return False


# Global registry instance
tool_registry = ToolRegistry()
