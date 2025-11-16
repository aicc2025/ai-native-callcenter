"""Claims management tools for function calling."""
from typing import Optional, List, Dict, Any
from uuid import UUID

from app.tools.registry import tool_registry
from app.business.claims_service import ClaimsService
from app.db.connection import DatabasePool
from app.logging_config import get_logger

logger = get_logger(__name__)

# Global service instance (will be initialized on first use)
_claims_service: Optional[ClaimsService] = None


def _get_claims_service() -> ClaimsService:
    """Get or create claims service instance."""
    global _claims_service
    if _claims_service is None:
        # Import here to avoid circular dependency
        from app.main import get_db_pool

        _claims_service = ClaimsService(get_db_pool())
    return _claims_service


@tool_registry.register(
    name="get_claim_status",
    description="Get the current status and details of an insurance claim",
    parameters={
        "type": "object",
        "properties": {
            "claim_id": {
                "type": "string",
                "description": "The unique identifier of the claim (UUID format)",
            }
        },
        "required": ["claim_id"],
    },
    cache_ttl=1800,  # 30 minutes
    timeout=5,
)
async def get_claim_status(claim_id: str) -> Dict[str, Any]:
    """
    Get claim status and details.

    Args:
        claim_id: Claim UUID as string

    Returns:
        Claim details including status, amount, history, etc.

    Raises:
        ValueError: If claim_id is invalid UUID format
        ToolExecutionError: If claim not found
    """
    try:
        claim_uuid = UUID(claim_id)
    except ValueError as e:
        raise ValueError(f"Invalid claim_id format: {claim_id}") from e

    service = _get_claims_service()
    result = await service.get_claim_status(claim_uuid)

    if result is None:
        raise ValueError(f"Claim not found: {claim_id}")

    return result


@tool_registry.register(
    name="list_customer_claims",
    description="List all claims for a specific customer, ordered by creation date (newest first)",
    parameters={
        "type": "object",
        "properties": {
            "customer_id": {
                "type": "string",
                "description": "The unique identifier of the customer (UUID format)",
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of claims to return (default 10, max 50)",
                "default": 10,
                "minimum": 1,
                "maximum": 50,
            },
            "offset": {
                "type": "integer",
                "description": "Number of claims to skip for pagination (default 0)",
                "default": 0,
                "minimum": 0,
            },
        },
        "required": ["customer_id"],
    },
    cache_ttl=1800,  # 30 minutes
    timeout=5,
)
async def list_customer_claims(
    customer_id: str, limit: int = 10, offset: int = 0
) -> List[Dict[str, Any]]:
    """
    List claims for a customer.

    Args:
        customer_id: Customer UUID as string
        limit: Maximum number of results (default 10, max 50)
        offset: Pagination offset (default 0)

    Returns:
        List of claim summaries

    Raises:
        ValueError: If customer_id is invalid UUID format
    """
    try:
        customer_uuid = UUID(customer_id)
    except ValueError as e:
        raise ValueError(f"Invalid customer_id format: {customer_id}") from e

    service = _get_claims_service()
    return await service.list_customer_claims(customer_uuid, limit, offset)


@tool_registry.register(
    name="submit_claim",
    description="Submit a new insurance claim for a customer",
    parameters={
        "type": "object",
        "properties": {
            "customer_id": {
                "type": "string",
                "description": "The unique identifier of the customer (UUID format)",
            },
            "claim_type": {
                "type": "string",
                "description": "Type of claim",
                "enum": ["auto", "health", "property"],
            },
            "amount": {
                "type": "number",
                "description": "Claim amount in dollars (must be positive)",
                "minimum": 0.01,
            },
            "description": {
                "type": "string",
                "description": "Detailed description of the claim",
                "minLength": 10,
            },
            "documents": {
                "type": "array",
                "description": "Optional list of document references",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "url": {"type": "string"},
                        "type": {"type": "string"},
                    },
                },
                "default": [],
            },
        },
        "required": ["customer_id", "claim_type", "amount", "description"],
    },
    cache_ttl=None,  # Don't cache write operations
    timeout=10,  # Longer timeout for write operation
)
async def submit_claim(
    customer_id: str,
    claim_type: str,
    amount: float,
    description: str,
    documents: Optional[List[Dict[str, str]]] = None,
) -> Dict[str, Any]:
    """
    Submit a new claim.

    Args:
        customer_id: Customer UUID as string
        claim_type: One of 'auto', 'health', 'property'
        amount: Claim amount (must be positive)
        description: Claim description (min 10 characters)
        documents: Optional list of document references

    Returns:
        Created claim details with new claim_id

    Raises:
        ValueError: If parameters are invalid
    """
    try:
        customer_uuid = UUID(customer_id)
    except ValueError as e:
        raise ValueError(f"Invalid customer_id format: {customer_id}") from e

    service = _get_claims_service()
    return await service.submit_claim(
        customer_uuid, claim_type, amount, description, documents
    )
