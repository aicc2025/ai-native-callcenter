"""seed journey definitions

Revision ID: 004
Revises: 003
Create Date: 2025-01-16

"""
from typing import Sequence, Union
from pathlib import Path
import json

from alembic import op
import sqlalchemy as sa


revision: str = '004'
down_revision: Union[str, None] = '003'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Load journey definitions from YAML files into database."""
    # Import here to avoid issues during migration
    import sys
    from uuid7 import uuid7

    # Add app to path
    project_root = Path(__file__).parent.parent.parent
    sys.path.insert(0, str(project_root))

    from app.flow_control.journey.loader import JourneyLoader

    # Load all journeys from YAML files
    journeys_dir = project_root / "data" / "journeys"

    if not journeys_dir.exists():
        print(f"Warning: Journeys directory not found at {journeys_dir}")
        return

    journeys = JourneyLoader.load_journeys_from_directory(journeys_dir)

    # Insert into database
    connection = op.get_bind()

    for journey in journeys:
        db_data = JourneyLoader.to_db_format(journey)

        # Convert states and transitions to JSON strings
        states_json = json.dumps(db_data['states'])
        transitions_json = json.dumps(db_data['transitions'])

        # Insert journey
        connection.execute(
            sa.text("""
                INSERT INTO journeys (
                    id, name, description, activation_conditions,
                    initial_state, states, transitions, enabled,
                    created_at, updated_at
                )
                VALUES (
                    :id, :name, :description, :activation_conditions,
                    :initial_state, :states::jsonb, :transitions::jsonb, :enabled,
                    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                )
                ON CONFLICT (name) DO UPDATE SET
                    description = EXCLUDED.description,
                    activation_conditions = EXCLUDED.activation_conditions,
                    initial_state = EXCLUDED.initial_state,
                    states = EXCLUDED.states,
                    transitions = EXCLUDED.transitions,
                    enabled = EXCLUDED.enabled,
                    updated_at = CURRENT_TIMESTAMP
            """),
            {
                'id': str(db_data['id']),
                'name': db_data['name'],
                'description': db_data['description'],
                'activation_conditions': db_data['activation_conditions'],
                'initial_state': db_data['initial_state'],
                'states': states_json,
                'transitions': transitions_json,
                'enabled': db_data['enabled'],
            }
        )

        print(f"Loaded journey: {journey.name} ({len(journey.states)} states, {len(journey.transitions)} transitions)")

    print(f"Successfully loaded {len(journeys)} journey definitions")


def downgrade() -> None:
    """Remove seeded journey definitions."""
    connection = op.get_bind()

    # Delete the specific journeys we added
    journey_names = ['claim_inquiry', 'claim_submission', 'knowledge_query']

    for name in journey_names:
        connection.execute(
            sa.text("DELETE FROM journeys WHERE name = :name"),
            {'name': name}
        )

    print(f"Removed {len(journey_names)} journey definitions")
