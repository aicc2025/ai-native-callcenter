"""seed guidelines

Revision ID: 005
Revises: 004
Create Date: 2025-01-16

"""
from typing import Sequence, Union
from pathlib import Path
import asyncio

from alembic import op
import sqlalchemy as sa


revision: str = '005'
down_revision: Union[str, None] = '004'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Load guideline definitions from YAML files into database."""
    # Run async loading in sync context
    asyncio.run(async_upgrade())


async def async_upgrade() -> None:
    """Async implementation of upgrade."""
    import sys
    from uuid import UUID

    # Add app to path
    project_root = Path(__file__).parent.parent.parent
    sys.path.insert(0, str(project_root))

    from app.flow_control.guideline.loader import GuidelineLoader

    # Get database connection
    connection = op.get_bind()

    # First, build journey_id_map by querying existing journeys
    journey_rows = connection.execute(
        sa.text("SELECT id, name FROM journeys WHERE enabled = true")
    ).fetchall()

    journey_id_map = {row.name: UUID(str(row.id)) for row in journey_rows}

    print(f"Found {len(journey_id_map)} journeys in database")

    # Load all guidelines from YAML files
    guidelines_dir = project_root / "data" / "guidelines"

    if not guidelines_dir.exists():
        print(f"Warning: Guidelines directory not found at {guidelines_dir}")
        return

    guidelines = await GuidelineLoader.load_guidelines_from_directory(
        guidelines_dir,
        journey_id_map,
    )

    # Insert into database
    for guideline in guidelines:
        db_data = GuidelineLoader.to_db_format(guideline)

        # Convert lists to PostgreSQL arrays
        connection.execute(
            sa.text("""
                INSERT INTO guidelines (
                    id, scope, journey_id, state_name, name, description,
                    condition, action, tools, keywords, priority, enabled,
                    created_at, updated_at
                )
                VALUES (
                    :id, :scope, :journey_id, :state_name, :name, :description,
                    :condition, :action, :tools, :keywords, :priority, :enabled,
                    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                )
                ON CONFLICT (id) DO UPDATE SET
                    scope = EXCLUDED.scope,
                    journey_id = EXCLUDED.journey_id,
                    state_name = EXCLUDED.state_name,
                    name = EXCLUDED.name,
                    description = EXCLUDED.description,
                    condition = EXCLUDED.condition,
                    action = EXCLUDED.action,
                    tools = EXCLUDED.tools,
                    keywords = EXCLUDED.keywords,
                    priority = EXCLUDED.priority,
                    enabled = EXCLUDED.enabled,
                    updated_at = CURRENT_TIMESTAMP
            """),
            {
                'id': str(db_data['id']),
                'scope': db_data['scope'],
                'journey_id': str(db_data['journey_id']) if db_data['journey_id'] else None,
                'state_name': db_data['state_name'],
                'name': db_data['name'],
                'description': db_data['description'],
                'condition': db_data['condition'],
                'action': db_data['action'],
                'tools': db_data['tools'],
                'keywords': db_data['keywords'],
                'priority': db_data['priority'],
                'enabled': db_data['enabled'],
            }
        )

        scope_info = db_data['scope']
        if db_data['journey_id']:
            journey_name = next(
                (name for name, jid in journey_id_map.items() if jid == db_data['journey_id']),
                "unknown"
            )
            scope_info += f" ({journey_name}"
            if db_data['state_name']:
                scope_info += f".{db_data['state_name']}"
            scope_info += ")"

        print(f"Loaded guideline: {guideline.name} [{scope_info}]")

    print(f"Successfully loaded {len(guidelines)} guidelines")


def downgrade() -> None:
    """Remove seeded guidelines."""
    connection = op.get_bind()

    # Delete all guidelines (or you could be more selective)
    result = connection.execute(
        sa.text("DELETE FROM guidelines WHERE created_at >= CURRENT_DATE")
    )

    print(f"Removed guidelines")
