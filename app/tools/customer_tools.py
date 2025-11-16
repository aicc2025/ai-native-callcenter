"""Customer information and verification tools for function calling."""
from typing import Optional, Dict, Any
from uuid import UUID

from app.tools.registry import tool_registry
from app.business.customer_service import CustomerService
from app.db.connection import DatabasePool
from app.logging_config import get_logger

logger = get_logger(__name__)

# Global service instance (will be initialized on first use)
_customer_service: Optional[CustomerService] = None


def _get_customer_service() -> CustomerService:
    """Get or create customer service instance."""
    global _customer_service
    if _customer_service is None:
        # Import here to avoid circular dependency
        from app.main import get_db_pool

        _customer_service = CustomerService(get_db_pool())
    return _customer_service


@tool_registry.register(
    name="get_customer_info",
    description="Get customer information and policy details by customer ID or phone number",
    parameters={
        "type": "object",
        "properties": {
            "customer_id": {
                "type": "string",
                "description": "The unique identifier of the customer (UUID format)",
            },
            "phone": {
                "type": "string",
                "description": "Customer phone number (E.164 format preferred)",
            },
        },
        "oneOf": [{"required": ["customer_id"]}, {"required": ["phone"]}],
    },
    cache_ttl=1800,  # 30 minutes
    timeout=5,
)
async def get_customer_info(
    customer_id: Optional[str] = None, phone: Optional[str] = None
) -> Dict[str, Any]:
    """
    Get customer information.

    Args:
        customer_id: Customer UUID as string (optional)
        phone: Customer phone number (optional)

    At least one parameter must be provided.

    Returns:
        Customer details including name, email, phone, policy info

    Raises:
        ValueError: If neither parameter provided or customer not found
    """
    if customer_id:
        try:
            customer_uuid = UUID(customer_id)
        except ValueError as e:
            raise ValueError(f"Invalid customer_id format: {customer_id}") from e
    else:
        customer_uuid = None

    service = _get_customer_service()
    result = await service.get_customer_info(customer_id=customer_uuid, phone=phone)

    if result is None:
        identifier = customer_id or phone
        raise ValueError(f"Customer not found: {identifier}")

    return result


@tool_registry.register(
    name="verify_customer_identity",
    description="Verify customer identity using phone number and policy number. IMPORTANT: Rate limited to 3 attempts per hour per phone number.",
    parameters={
        "type": "object",
        "properties": {
            "phone": {
                "type": "string",
                "description": "Customer phone number (E.164 format preferred)",
            },
            "policy_number": {
                "type": "string",
                "description": "Customer policy number (alphanumeric)",
            },
        },
        "required": ["phone", "policy_number"],
    },
    cache_ttl=None,  # Don't cache verification results for security
    timeout=5,
    rate_limit={
        "max_calls": 3,  # Maximum 3 verification attempts
        "window": 3600,  # Per hour (3600 seconds)
        "identifier_field": "phone",  # Rate limit per phone number
    },
)
async def verify_customer_identity(phone: str, policy_number: str) -> bool:
    """
    Verify customer identity.

    IMPORTANT: This function is rate-limited to 3 calls per hour per phone number
    to prevent brute-force attacks. The rate limit is enforced by the ToolExecutor.

    Args:
        phone: Customer phone number
        policy_number: Customer policy number

    Returns:
        True if phone and policy number match, False otherwise

    Raises:
        RateLimitExceededError: If too many verification attempts for this phone
    """
    service = _get_customer_service()
    return await service.verify_customer_identity(phone, policy_number)
