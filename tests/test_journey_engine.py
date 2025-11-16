"""Unit tests for Journey Engine."""
import pytest
from uuid import UUID
from datetime import datetime

from app.flow_control.journey.models import Journey, JourneyState, JourneyTransition, JourneyContext


class TestJourneyModels:
    """Test journey data models."""

    def test_journey_state_creation(self):
        """Test JourneyState creation and validation."""
        state = JourneyState(
            name="verify_identity",
            action="Ask customer for policy number and date of birth",
            tools=["verify_customer_identity"],
        )

        assert state.name == "verify_identity"
        assert state.action == "Ask customer for policy number and date of birth"
        assert "verify_customer_identity" in state.tools

    def test_journey_state_validation(self):
        """Test JourneyState validation."""
        with pytest.raises(ValueError, match="State name cannot be empty"):
            JourneyState(name="", action="test action")

        with pytest.raises(ValueError, match="State action cannot be empty"):
            JourneyState(name="test", action="")

    def test_journey_transition(self):
        """Test JourneyTransition creation."""
        transition = JourneyTransition(
            from_state="verify_identity",
            to_state="provide_status",
            condition="Identity verified successfully",
            priority=10,
        )

        assert transition.from_state == "verify_identity"
        assert transition.to_state == "provide_status"
        assert transition.priority == 10

    def test_journey_context_variables(self):
        """Test JourneyContext variable management."""
        context = JourneyContext(
            id=UUID("550e8400-e29b-41d4-a716-446655440000"),
            session_id="test-session",
            journey_id=UUID("550e8400-e29b-41d4-a716-446655440001"),
            journey_name="claim_inquiry",
            current_state="verify_identity",
        )

        # Set and get variables
        context.set_variable("customer_id", "12345")
        context.set_variable("policy_number", "POL-001")

        assert context.get_variable("customer_id") == "12345"
        assert context.get_variable("policy_number") == "POL-001"
        assert context.get_variable("missing_key") is None
        assert context.get_variable("missing_key", "default") == "default"

    def test_journey_context_state_transition(self):
        """Test JourneyContext state transitions."""
        context = JourneyContext(
            id=UUID("550e8400-e29b-41d4-a716-446655440000"),
            session_id="test-session",
            journey_id=UUID("550e8400-e29b-41d4-a716-446655440001"),
            journey_name="claim_inquiry",
            current_state="verify_identity",
        )

        # Transition to new state
        context.transition_to("provide_status", "Identity verified")

        assert context.current_state == "provide_status"
        assert len(context.state_history) == 2  # Initial + transition
        assert context.state_history[-1]["event"] == "state_transition"
        assert context.state_history[-1]["from_state"] == "verify_identity"
        assert context.state_history[-1]["to_state"] == "provide_status"

    def test_journey_context_completion(self):
        """Test JourneyContext completion."""
        context = JourneyContext(
            id=UUID("550e8400-e29b-41d4-a716-446655440000"),
            session_id="test-session",
            journey_id=UUID("550e8400-e29b-41d4-a716-446655440001"),
            journey_name="claim_inquiry",
            current_state="completed",
        )

        assert context.is_active()

        context.complete()

        assert not context.is_active()
        assert context.completed_at is not None
        assert context.state_history[-1]["event"] == "journey_completed"


class TestGuidelineModels:
    """Test guideline data models."""

    def test_guideline_priority_score(self):
        """Test guideline priority score calculation."""
        from app.flow_control.guideline.models import Guideline, GuidelineScope
        from uuid import uuid4

        journey_id = uuid4()
        state_name = "verify_identity"

        # STATE scope guideline
        state_guideline = Guideline(
            id=uuid4(),
            scope=GuidelineScope.STATE,
            name="State-specific rule",
            condition="test",
            action="test",
            priority=50,
            journey_id=journey_id,
            state_name=state_name,
        )

        # JOURNEY scope guideline
        journey_guideline = Guideline(
            id=uuid4(),
            scope=GuidelineScope.JOURNEY,
            name="Journey-specific rule",
            condition="test",
            action="test",
            priority=50,
            journey_id=journey_id,
        )

        # GLOBAL scope guideline
        global_guideline = Guideline(
            id=uuid4(),
            scope=GuidelineScope.GLOBAL,
            name="Global rule",
            condition="test",
            action="test",
            priority=50,
        )

        # STATE scope should have highest priority
        assert state_guideline.get_priority_score(journey_id, state_name) > \
               journey_guideline.get_priority_score(journey_id, state_name)

        # JOURNEY scope should be higher than GLOBAL
        assert journey_guideline.get_priority_score(journey_id, state_name) > \
               global_guideline.get_priority_score(journey_id, state_name)

        # Different journeys/states shouldn't match
        other_journey = uuid4()
        assert state_guideline.get_priority_score(other_journey, state_name) == 0


# Note: Full integration tests would require database/Redis setup
# These are unit tests for the models only
