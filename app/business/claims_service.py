"""Claims business service."""
from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime
from decimal import Decimal
import json

from app.db.connection import DatabasePool
from app.logging_config import get_logger
from uuid7 import uuid7

logger = get_logger(__name__)


class ClaimsService:
    """Service for managing insurance claims."""

    def __init__(self, db_pool: DatabasePool):
        self.db = db_pool

    async def get_claim_status(self, claim_id: UUID) -> Optional[Dict[str, Any]]:
        """
        Get claim status and details.

        Target latency: <30ms (simple query)
        """
        row = await self.db.fetchrow(
            """
            SELECT id, customer_id, type, status, amount, description,
                   documents, history, created_at, updated_at
            FROM claims
            WHERE id = $1
            """,
            claim_id,
        )

        if not row:
            return None

        return {
            "claim_id": str(row["id"]),
            "customer_id": str(row["customer_id"]),
            "type": row["type"],
            "status": row["status"],
            "amount": float(row["amount"]),
            "description": row["description"],
            "documents": row["documents"],
            "history": row["history"],
            "created_at": row["created_at"].isoformat() if row["created_at"] else None,
            "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None,
        }

    async def list_customer_claims(
        self,
        customer_id: UUID,
        limit: int = 10,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        List claims for a customer.

        Target latency: <30ms (simple query)
        """
        if limit > 50:
            limit = 50  # Max limit

        rows = await self.db.fetch(
            """
            SELECT id, type, status, amount, description, created_at, updated_at
            FROM claims
            WHERE customer_id = $1
            ORDER BY created_at DESC
            LIMIT $2 OFFSET $3
            """,
            customer_id,
            limit,
            offset,
        )

        return [
            {
                "claim_id": str(row["id"]),
                "type": row["type"],
                "status": row["status"],
                "amount": float(row["amount"]),
                "description": row["description"],
                "created_at": row["created_at"].isoformat() if row["created_at"] else None,
                "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None,
            }
            for row in rows
        ]

    async def submit_claim(
        self,
        customer_id: UUID,
        claim_type: str,
        amount: float,
        description: str,
        documents: Optional[List[Dict[str, str]]] = None,
    ) -> Dict[str, Any]:
        """
        Submit a new claim.

        Target latency: <100ms (write operation)
        """
        # Validate claim type
        valid_types = ["auto", "health", "property"]
        if claim_type not in valid_types:
            raise ValueError(f"Invalid claim type. Must be one of: {valid_types}")

        # Validate amount
        if amount <= 0:
            raise ValueError("Claim amount must be positive")

        claim_id = uuid7()
        now = datetime.utcnow()

        # Create history entry
        history = [
            {
                "status": "submitted",
                "timestamp": now.isoformat(),
                "note": "Claim submitted via AI call center",
                "by": "ai_agent",
            }
        ]

        await self.db.execute(
            """
            INSERT INTO claims
            (id, customer_id, type, status, amount, description, documents, history, created_at, updated_at)
            VALUES ($1, $2, $3, 'submitted', $4, $5, $6, $7, $8, $9)
            """,
            claim_id,
            customer_id,
            claim_type,
            Decimal(str(amount)),
            description,
            json.dumps(documents or []),
            json.dumps(history),
            now,
            now,
        )

        logger.info(
            "Claim submitted",
            claim_id=str(claim_id),
            customer_id=str(customer_id),
            type=claim_type,
            amount=amount,
        )

        return {
            "claim_id": str(claim_id),
            "customer_id": str(customer_id),
            "type": claim_type,
            "status": "submitted",
            "amount": amount,
            "description": description,
            "created_at": now.isoformat(),
        }

    async def update_claim_status(
        self,
        claim_id: UUID,
        new_status: str,
        note: Optional[str] = None,
    ) -> bool:
        """Update claim status and add history entry."""
        valid_statuses = ["submitted", "reviewing", "approved", "denied"]
        if new_status not in valid_statuses:
            raise ValueError(f"Invalid status. Must be one of: {valid_statuses}")

        # Get current claim
        row = await self.db.fetchrow(
            "SELECT history FROM claims WHERE id = $1",
            claim_id,
        )

        if not row:
            return False

        # Add history entry
        history = row["history"]
        history.append({
            "status": new_status,
            "timestamp": datetime.utcnow().isoformat(),
            "note": note or f"Status updated to {new_status}",
            "by": "system",
        })

        # Update claim
        await self.db.execute(
            """
            UPDATE claims
            SET status = $1, history = $2, updated_at = CURRENT_TIMESTAMP
            WHERE id = $3
            """,
            new_status,
            json.dumps(history),
            claim_id,
        )

        logger.info(
            "Claim status updated",
            claim_id=str(claim_id),
            new_status=new_status,
        )

        return True
