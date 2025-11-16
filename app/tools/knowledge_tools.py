"""Knowledge base search tools for function calling."""
from typing import Optional, List, Dict, Any

from app.tools.registry import tool_registry
from app.business.knowledge_service import KnowledgeService
from app.db.connection import DatabasePool
from app.logging_config import get_logger

logger = get_logger(__name__)

# Global service instance (will be initialized on first use)
_knowledge_service: Optional[KnowledgeService] = None


def _get_knowledge_service() -> KnowledgeService:
    """Get or create knowledge service instance."""
    global _knowledge_service
    if _knowledge_service is None:
        # Import here to avoid circular dependency
        from app.main import get_db_pool

        _knowledge_service = KnowledgeService(get_db_pool())
    return _knowledge_service


@tool_registry.register(
    name="search_knowledge_base",
    description="Search the insurance knowledge base for policy information, coverage details, FAQs, and procedures. Uses full-text search with relevance ranking.",
    parameters={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query (e.g., 'dental coverage', 'claim submission process', 'what is covered for auto accidents')",
                "minLength": 3,
            },
            "category": {
                "type": "string",
                "description": "Optional category filter to narrow results",
                "enum": ["auto", "health", "property", "general"],
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of results to return (default 5, max 20)",
                "default": 5,
                "minimum": 1,
                "maximum": 20,
            },
        },
        "required": ["query"],
    },
    cache_ttl=1800,  # 30 minutes - KB content changes infrequently
    timeout=10,  # Full-text search may take longer
)
async def search_knowledge_base(
    query: str, category: Optional[str] = None, limit: int = 5
) -> List[Dict[str, Any]]:
    """
    Search the knowledge base using PostgreSQL full-text search.

    Uses plainto_tsquery for query parsing and ts_rank for relevance scoring.
    Results are ordered by relevance (highest rank first).

    Args:
        query: Search query string (minimum 3 characters)
        category: Optional category filter ('auto', 'health', 'property', 'general')
        limit: Maximum number of results (default 5, max 20)

    Returns:
        List of knowledge base articles with relevance scores.
        Each article includes: id, title, content, category, tags, relevance

    Example:
        results = await search_knowledge_base("dental coverage", category="health", limit=3)
        # Returns top 3 health-related articles about dental coverage
    """
    if len(query) < 3:
        raise ValueError("Query must be at least 3 characters long")

    service = _get_knowledge_service()
    return await service.search_knowledge_base(query, category, limit)
