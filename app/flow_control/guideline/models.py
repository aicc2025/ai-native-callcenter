"""Guideline engine data models."""
from dataclasses import dataclass, field
from typing import Optional, List, Any
from datetime import datetime
from uuid import UUID
from enum import Enum


class GuidelineScope(str, Enum):
    """Guideline scope levels."""

    GLOBAL = "GLOBAL"
    JOURNEY = "JOURNEY"
    STATE = "STATE"


@dataclass
class Guideline:
    """Represents a business rule that constrains AI behavior."""

    id: UUID
    scope: GuidelineScope
    name: str
    description: Optional[str]
    condition: str
    action: str
    keywords: List[str] = field(default_factory=list)
    tools: List[str] = field(default_factory=list)
    priority: int = 0
    enabled: bool = True
    journey_id: Optional[UUID] = None
    state_name: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def __post_init__(self) -> None:
        """Validate guideline configuration."""
        if not self.name:
            raise ValueError("Guideline name cannot be empty")
        if not self.condition:
            raise ValueError("Guideline condition cannot be empty")
        if not self.action:
            raise ValueError("Guideline action cannot be empty")

        # Validate scope-specific requirements
        if self.scope == GuidelineScope.JOURNEY and not self.journey_id:
            raise ValueError("JOURNEY scope requires journey_id")
        if self.scope == GuidelineScope.STATE and (
            not self.journey_id or not self.state_name
        ):
            raise ValueError("STATE scope requires journey_id and state_name")

    def matches_scope(
        self,
        journey_id: Optional[UUID] = None,
        state_name: Optional[str] = None,
    ) -> bool:
        """Check if guideline matches the given scope."""
        if self.scope == GuidelineScope.GLOBAL:
            return True

        if self.scope == GuidelineScope.JOURNEY:
            return self.journey_id == journey_id

        if self.scope == GuidelineScope.STATE:
            return self.journey_id == journey_id and self.state_name == state_name

        return False

    def get_priority_score(
        self,
        journey_id: Optional[UUID] = None,
        state_name: Optional[str] = None,
    ) -> int:
        """
        Calculate priority score for guideline resolution.

        Priority resolution:
        1. Scope type (state > journey > global)
        2. Within same scope, numeric priority DESC
        """
        # Scope type priority (higher is more specific)
        scope_priority = {
            GuidelineScope.STATE: 3000,
            GuidelineScope.JOURNEY: 2000,
            GuidelineScope.GLOBAL: 1000,
        }

        # Check if guideline applies to current scope
        if not self.matches_scope(journey_id, state_name):
            return 0  # Doesn't apply

        return scope_priority[self.scope] + self.priority


@dataclass
class GuidelineMatch:
    """Represents a matched guideline with confidence."""

    guideline: Guideline
    confidence: float
    reasoning: str = ""

    def __post_init__(self) -> None:
        """Validate match."""
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("Confidence must be between 0.0 and 1.0")
