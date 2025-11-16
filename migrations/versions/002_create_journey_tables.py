"""create journey tables

Revision ID: 002
Revises: 001
Create Date: 2025-01-16

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '002'
down_revision: Union[str, None] = '001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Journeys table
    op.execute("""
        CREATE TABLE journeys (
            id UUID PRIMARY KEY,
            name VARCHAR(255) UNIQUE NOT NULL,
            description TEXT,
            activation_conditions TEXT NOT NULL,
            initial_state VARCHAR(100) NOT NULL,
            states JSONB NOT NULL,
            transitions JSONB NOT NULL,
            enabled BOOLEAN DEFAULT true,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX idx_journeys_name ON journeys(name);
        CREATE INDEX idx_journeys_enabled ON journeys(enabled);

        CREATE TRIGGER update_journeys_updated_at
            BEFORE UPDATE ON journeys
            FOR EACH ROW
            EXECUTE FUNCTION update_updated_at_column();
    """)

    # Journey states (for definitions)
    op.execute("""
        CREATE TABLE journey_states (
            id UUID PRIMARY KEY,
            journey_id UUID NOT NULL REFERENCES journeys(id) ON DELETE CASCADE,
            name VARCHAR(100) NOT NULL,
            action TEXT NOT NULL,
            tools TEXT[],
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(journey_id, name)
        );

        CREATE INDEX idx_journey_states_journey_id ON journey_states(journey_id);

        CREATE TRIGGER update_journey_states_updated_at
            BEFORE UPDATE ON journey_states
            FOR EACH ROW
            EXECUTE FUNCTION update_updated_at_column();
    """)

    # Journey transitions (for definitions)
    op.execute("""
        CREATE TABLE journey_transitions (
            id UUID PRIMARY KEY,
            journey_id UUID NOT NULL REFERENCES journeys(id) ON DELETE CASCADE,
            from_state VARCHAR(100) NOT NULL,
            to_state VARCHAR(100) NOT NULL,
            condition TEXT NOT NULL,
            priority INTEGER DEFAULT 0,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX idx_journey_transitions_journey_id ON journey_transitions(journey_id);
        CREATE INDEX idx_journey_transitions_from_state ON journey_transitions(from_state);

        CREATE TRIGGER update_journey_transitions_updated_at
            BEFORE UPDATE ON journey_transitions
            FOR EACH ROW
            EXECUTE FUNCTION update_updated_at_column();
    """)

    # Journey contexts (runtime state)
    op.execute("""
        CREATE TABLE journey_contexts (
            id UUID PRIMARY KEY,
            session_id VARCHAR(255) NOT NULL,
            journey_id UUID NOT NULL REFERENCES journeys(id),
            current_state VARCHAR(100) NOT NULL,
            variables JSONB DEFAULT '{}'::jsonb,
            state_history JSONB DEFAULT '[]'::jsonb,
            activated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP WITH TIME ZONE,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX idx_journey_contexts_session_id ON journey_contexts(session_id);
        CREATE INDEX idx_journey_contexts_journey_id ON journey_contexts(journey_id);
        CREATE INDEX idx_journey_contexts_activated_at ON journey_contexts(activated_at DESC);

        CREATE TRIGGER update_journey_contexts_updated_at
            BEFORE UPDATE ON journey_contexts
            FOR EACH ROW
            EXECUTE FUNCTION update_updated_at_column();
    """)


def downgrade() -> None:
    op.drop_table('journey_contexts')
    op.drop_table('journey_transitions')
    op.drop_table('journey_states')
    op.drop_table('journeys')
