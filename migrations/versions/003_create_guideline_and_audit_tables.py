"""create guideline and audit tables

Revision ID: 003
Revises: 002
Create Date: 2025-01-16

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '003'
down_revision: Union[str, None] = '002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Guidelines table
    op.execute("""
        CREATE TABLE guidelines (
            id UUID PRIMARY KEY,
            scope VARCHAR(50) NOT NULL CHECK (scope IN ('GLOBAL', 'JOURNEY', 'STATE')),
            journey_id UUID REFERENCES journeys(id) ON DELETE CASCADE,
            state_name VARCHAR(100),
            name VARCHAR(255) NOT NULL,
            description TEXT,
            condition TEXT NOT NULL,
            action TEXT NOT NULL,
            tools TEXT[],
            keywords TEXT[],
            priority INTEGER DEFAULT 0,
            enabled BOOLEAN DEFAULT true,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX idx_guidelines_scope ON guidelines(scope);
        CREATE INDEX idx_guidelines_journey_id ON guidelines(journey_id);
        CREATE INDEX idx_guidelines_enabled ON guidelines(enabled);
        CREATE INDEX idx_guidelines_priority ON guidelines(priority DESC);
        CREATE INDEX idx_guidelines_keywords ON guidelines USING GIN(keywords);

        CREATE TRIGGER update_guidelines_updated_at
            BEFORE UPDATE ON guidelines
            FOR EACH ROW
            EXECUTE FUNCTION update_updated_at_column();
    """)

    # Validation audit table
    op.execute("""
        CREATE TABLE validation_audit (
            id UUID PRIMARY KEY,
            session_id VARCHAR(255) NOT NULL,
            journey_id UUID REFERENCES journeys(id),
            guideline_ids UUID[],
            is_valid BOOLEAN NOT NULL,
            violations JSONB DEFAULT '[]'::jsonb,
            suggested_fixes JSONB DEFAULT '[]'::jsonb,
            confidence DECIMAL(3, 2),
            latency_ms INTEGER,
            original_response TEXT,
            fixed_response TEXT,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX idx_validation_audit_session_id ON validation_audit(session_id);
        CREATE INDEX idx_validation_audit_journey_id ON validation_audit(journey_id);
        CREATE INDEX idx_validation_audit_is_valid ON validation_audit(is_valid);
        CREATE INDEX idx_validation_audit_created_at ON validation_audit(created_at DESC);
    """)

    # Call sessions table (for audit trail)
    op.execute("""
        CREATE TABLE call_sessions (
            id VARCHAR(255) PRIMARY KEY,
            call_id VARCHAR(255),
            customer_id UUID REFERENCES customers(id),
            started_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
            ended_at TIMESTAMP WITH TIME ZONE,
            duration_seconds INTEGER,
            transcript JSONB DEFAULT '[]'::jsonb,
            metadata JSONB DEFAULT '{}'::jsonb,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX idx_call_sessions_customer_id ON call_sessions(customer_id);
        CREATE INDEX idx_call_sessions_started_at ON call_sessions(started_at DESC);

        CREATE TRIGGER update_call_sessions_updated_at
            BEFORE UPDATE ON call_sessions
            FOR EACH ROW
            EXECUTE FUNCTION update_updated_at_column();
    """)


def downgrade() -> None:
    op.drop_table('call_sessions')
    op.drop_table('validation_audit')
    op.drop_table('guidelines')
