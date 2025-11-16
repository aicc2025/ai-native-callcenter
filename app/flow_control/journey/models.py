"""Journey engine data models."""
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Any
from datetime import datetime
from uuid import UUID


@dataclass
class JourneyState:
    """Represents a state in a journey state machine."""

    name: str
    action: str
    tools: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate state configuration."""
        if not self.name:
            raise ValueError("State name cannot be empty")
        if not self.action:
            raise ValueError("State action cannot be empty")


@dataclass
class JourneyTransition:
    """Represents a transition between states."""

    from_state: str
    to_state: str
    condition: str
    priority: int = 0

    def __post_init__(self) -> None:
        """Validate transition configuration."""
        if not self.from_state:
            raise ValueError("from_state cannot be empty")
        if not self.to_state:
            raise ValueError("to_state cannot be empty")
        if not self.condition:
            raise ValueError("Transition condition cannot be empty")


@dataclass
class Journey:
    """Represents a complete journey definition."""

    id: UUID
    name: str
    description: Optional[str]
    activation_conditions: str
    initial_state: str
    states: Dict[str, JourneyState]
    transitions: List[JourneyTransition]
    enabled: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def __post_init__(self) -> None:
        """Validate journey configuration."""
        if not self.name:
            raise ValueError("Journey name cannot be empty")
        if not self.activation_conditions:
            raise ValueError("Activation conditions cannot be empty")
        if not self.initial_state:
            raise ValueError("Initial state must be specified")
        if self.initial_state not in self.states:
            raise ValueError(f"Initial state '{self.initial_state}' not found in states")
        if not self.states:
            raise ValueError("Journey must have at least one state")

    def get_state(self, state_name: str) -> Optional[JourneyState]:
        """Get a state by name."""
        return self.states.get(state_name)

    def get_transitions_from(self, state_name: str) -> List[JourneyTransition]:
        """Get all transitions from a given state."""
        return [t for t in self.transitions if t.from_state == state_name]


@dataclass
class JourneyContext:
    """Represents runtime state of an active journey instance."""

    id: UUID
    session_id: str
    journey_id: UUID
    journey_name: str
    current_state: str
    variables: Dict[str, Any] = field(default_factory=dict)
    state_history: List[Dict[str, Any]] = field(default_factory=list)
    activated_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def __post_init__(self) -> None:
        """Validate context."""
        if not self.session_id:
            raise ValueError("session_id cannot be empty")
        if not self.current_state:
            raise ValueError("current_state cannot be empty")

    def is_active(self) -> bool:
        """Check if journey is still active."""
        return self.completed_at is None

    def set_variable(self, key: str, value: Any) -> None:
        """Set a context variable."""
        self.variables[key] = value

    def get_variable(self, key: str, default: Any = None) -> Any:
        """Get a context variable."""
        return self.variables.get(key, default)

    def add_to_history(self, event: Dict[str, Any]) -> None:
        """Add an event to state history."""
        self.state_history.append({
            **event,
            "timestamp": datetime.utcnow().isoformat(),
        })

    def transition_to(self, new_state: str, reason: str = "") -> None:
        """Transition to a new state."""
        self.add_to_history({
            "event": "state_transition",
            "from_state": self.current_state,
            "to_state": new_state,
            "reason": reason,
        })
        self.current_state = new_state

    def complete(self) -> None:
        """Mark journey as completed."""
        self.completed_at = datetime.utcnow()
        self.add_to_history({
            "event": "journey_completed",
            "final_state": self.current_state,
        })
