#!/usr/bin/env python3
"""Seed customers table with deterministic mock data."""
import asyncio
import os
from uuid7 import uuid7

import asyncpg
from dotenv import load_dotenv

load_dotenv()

CUSTOMERS = [
    ("John Smith", "+1-555-0101", "john.smith@email.com", "POL-001"),
    ("Sarah Johnson", "+1-555-0102", "sarah.j@email.com", "POL-002"),
    ("Michael Chen", "+1-555-0103", "m.chen@email.com", "POL-003"),
    ("Emma Davis", "+1-555-0104", "emma.davis@email.com", "POL-004"),
    ("Robert Williams", "+1-555-0105", "r.williams@email.com", "POL-005"),
    ("Maria Garcia", "+1-555-0106", "maria.g@email.com", "POL-006"),
    ("James Brown", "+1-555-0107", "james.b@email.com", "POL-007"),
    ("Lisa Anderson", "+1-555-0108", "lisa.a@email.com", "POL-008"),
    ("David Martinez", "+1-555-0109", "d.martinez@email.com", "POL-009"),
    ("Jennifer Taylor", "+1-555-0110", "j.taylor@email.com", "POL-010"),
    ("Christopher Lee", "+1-555-0111", "c.lee@email.com", "POL-011"),
    ("Amanda White", "+1-555-0112", "amanda.w@email.com", "POL-012"),
    ("Matthew Harris", "+1-555-0113", "m.harris@email.com", "POL-013"),
    ("Jessica Clark", "+1-555-0114", "jessica.c@email.com", "POL-014"),
    ("Daniel Lewis", "+1-555-0115", "d.lewis@email.com", "POL-015"),
    ("Ashley Robinson", "+1-555-0116", "ashley.r@email.com", "POL-016"),
    ("Joshua Walker", "+1-555-0117", "j.walker@email.com", "POL-017"),
    ("Nicole Hall", "+1-555-0118", "nicole.h@email.com", "POL-018"),
    ("Andrew Young", "+1-555-0119", "a.young@email.com", "POL-019"),
    ("Stephanie King", "+1-555-0120", "stephanie.k@email.com", "POL-020"),
]


async def seed_customers():
    conn = await asyncpg.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        user=os.getenv("POSTGRES_USER", "callcenter"),
        password=os.getenv("POSTGRES_PASSWORD", "callcenter_dev"),
        database=os.getenv("POSTGRES_DB", "callcenter"),
    )

    try:
        for name, phone, email, policy in CUSTOMERS:
            customer_id = uuid7()
            await conn.execute(
                """
                INSERT INTO customers (id, name, phone, email, policy_number, metadata)
                VALUES ($1, $2, $3, $4, $5, '{}'::jsonb)
                ON CONFLICT (policy_number) DO NOTHING
                """,
                customer_id,
                name,
                phone,
                email,
                policy,
            )
            print(f"Seeded customer: {name} ({policy})")

        count = await conn.fetchval("SELECT COUNT(*) FROM customers")
        print(f"\nTotal customers: {count}")

    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(seed_customers())
