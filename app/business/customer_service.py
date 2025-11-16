"""Customer business service."""
from typing import Optional, Dict, Any
from uuid import UUID

from app.db.connection import DatabasePool
from app.logging_config import get_logger

logger = get_logger(__name__)


class CustomerService:
    """Service for managing customer information and verification."""

    def __init__(self, db_pool: DatabasePool):
        self.db = db_pool

    async def get_customer_info(
        self,
        customer_id: Optional[UUID] = None,
        phone: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Get customer information by ID or phone number.

        At least one parameter must be provided.
        Target latency: <30ms (P95)

        Args:
            customer_id: Customer UUID
            phone: Customer phone number

        Returns:
            Customer info dict or None if not found

        Raises:
            ValueError: If neither customer_id nor phone is provided
        """
        if not customer_id and not phone:
            raise ValueError("Either customer_id or phone must be provided")

        if customer_id:
            row = await self.db.fetchrow(
                """
                SELECT id, name, email, phone, address, policy_number,
                       policy_type, policy_status, policy_start_date,
                       policy_end_date, created_at
                FROM customers
                WHERE id = $1
                """,
                customer_id,
            )
        else:
            row = await self.db.fetchrow(
                """
                SELECT id, name, email, phone, address, policy_number,
                       policy_type, policy_status, policy_start_date,
                       policy_end_date, created_at
                FROM customers
                WHERE phone = $1
                """,
                phone,
            )

        if not row:
            return None

        return {
            "customer_id": str(row["id"]),
            "name": row["name"],
            "email": row["email"],
            "phone": row["phone"],
            "address": row["address"],
            "policy_number": row["policy_number"],
            "policy_type": row["policy_type"],
            "policy_status": row["policy_status"],
            "policy_start_date": (
                row["policy_start_date"].isoformat()
                if row["policy_start_date"]
                else None
            ),
            "policy_end_date": (
                row["policy_end_date"].isoformat() if row["policy_end_date"] else None
            ),
            "created_at": row["created_at"].isoformat() if row["created_at"] else None,
        }

    async def get_customer_by_phone(self, phone: str) -> Optional[Dict[str, Any]]:
        """
        Get customer by phone number.

        Helper method for phone-based lookups.
        Target latency: <30ms (P95)

        Args:
            phone: Customer phone number

        Returns:
            Customer info dict or None if not found
        """
        return await self.get_customer_info(phone=phone)

    async def verify_customer_identity(
        self, phone: str, policy_number: str
    ) -> bool:
        """
        Verify customer identity using phone and policy number.

        This method should be rate-limited (max 3 calls/hour per phone)
        when called through the tool executor.

        Target latency: <30ms (P95)

        Args:
            phone: Customer phone number
            policy_number: Customer policy number

        Returns:
            True if phone and policy number match, False otherwise
        """
        row = await self.db.fetchrow(
            """
            SELECT id
            FROM customers
            WHERE phone = $1 AND policy_number = $2
            """,
            phone,
            policy_number,
        )

        verified = row is not None

        logger.info(
            "Customer identity verification",
            phone=phone,
            verified=verified,
        )

        return verified
