"""create business tables

Revision ID: 001
Revises:
Create Date: 2025-01-16

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Customers table
    op.execute("""
        CREATE TABLE customers (
            id UUID PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            phone VARCHAR(50) NOT NULL,
            email VARCHAR(255),
            policy_number VARCHAR(100) UNIQUE NOT NULL,
            metadata JSONB DEFAULT '{}'::jsonb,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX idx_customers_phone ON customers(phone);
        CREATE INDEX idx_customers_policy_number ON customers(policy_number);

        CREATE TRIGGER update_customers_updated_at
            BEFORE UPDATE ON customers
            FOR EACH ROW
            EXECUTE FUNCTION update_updated_at_column();
    """)

    # Claims table
    op.execute("""
        CREATE TABLE claims (
            id UUID PRIMARY KEY,
            customer_id UUID NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
            type VARCHAR(50) NOT NULL CHECK (type IN ('auto', 'health', 'property')),
            status VARCHAR(50) NOT NULL CHECK (status IN ('submitted', 'reviewing', 'approved', 'denied')),
            amount DECIMAL(12, 2) NOT NULL CHECK (amount > 0),
            description TEXT NOT NULL,
            documents JSONB DEFAULT '[]'::jsonb,
            history JSONB DEFAULT '[]'::jsonb,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX idx_claims_customer_id ON claims(customer_id);
        CREATE INDEX idx_claims_status ON claims(status);
        CREATE INDEX idx_claims_type ON claims(type);
        CREATE INDEX idx_claims_created_at ON claims(created_at DESC);

        CREATE TRIGGER update_claims_updated_at
            BEFORE UPDATE ON claims
            FOR EACH ROW
            EXECUTE FUNCTION update_updated_at_column();
    """)

    # Knowledge base table
    op.execute("""
        CREATE TABLE knowledge_base (
            id UUID PRIMARY KEY,
            category VARCHAR(100) NOT NULL,
            keywords TEXT[] NOT NULL,
            question TEXT NOT NULL,
            answer TEXT NOT NULL,
            priority INTEGER DEFAULT 0,
            search_vector TSVECTOR,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX idx_kb_category ON knowledge_base(category);
        CREATE INDEX idx_kb_priority ON knowledge_base(priority DESC);
        CREATE INDEX idx_kb_search_vector ON knowledge_base USING GIN(search_vector);
        CREATE INDEX idx_kb_keywords ON knowledge_base USING GIN(keywords);

        CREATE TRIGGER update_knowledge_base_updated_at
            BEFORE UPDATE ON knowledge_base
            FOR EACH ROW
            EXECUTE FUNCTION update_updated_at_column();

        CREATE TRIGGER knowledge_base_search_vector_update
            BEFORE INSERT OR UPDATE ON knowledge_base
            FOR EACH ROW
            EXECUTE FUNCTION tsvector_update_trigger(search_vector, 'pg_catalog.english', question, answer);
    """)


def downgrade() -> None:
    op.drop_table('knowledge_base')
    op.drop_table('claims')
    op.drop_table('customers')
