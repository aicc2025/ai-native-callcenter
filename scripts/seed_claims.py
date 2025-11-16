#!/usr/bin/env python3
"""Seed claims table with deterministic mock data."""
import asyncio
import os
from uuid7 import uuid7
from decimal import Decimal
import json

import asyncpg
from dotenv import load_dotenv

load_dotenv()

CLAIM_TEMPLATES = [
    # Auto claims
    ("auto", "submitted", 2500.00, "Rear-end collision at intersection, minor damage to bumper"),
    ("auto", "reviewing", 8500.00, "Side impact collision, door and panel damage, airbag deployed"),
    ("auto", "approved", 1200.00, "Windshield crack from road debris"),
    ("auto", "submitted", 15000.00, "Total loss - vehicle rolled over in highway accident"),
    ("auto", "approved", 3200.00, "Parking lot fender bender, front bumper replacement needed"),
    ("auto", "denied", 500.00, "Pre-existing damage claim denied after inspection"),
    ("auto", "reviewing", 6800.00, "Hit and run damage to driver side, police report filed"),

    # Health claims
    ("health", "submitted", 450.00, "Annual physical examination and blood work"),
    ("health", "approved", 12500.00, "Emergency room visit for broken arm, X-ray and casting"),
    ("health", "reviewing", 3200.00, "MRI scan for back pain diagnosis"),
    ("health", "approved", 850.00, "Dental crown replacement procedure"),
    ("health", "submitted", 25000.00, "Outpatient surgery for knee arthroscopy"),
    ("health", "denied", 180.00, "Cosmetic procedure not covered by policy"),
    ("health", "approved", 2100.00, "Physical therapy sessions - 12 visits"),

    # Property claims
    ("property", "submitted", 8500.00, "Water damage from burst pipe in kitchen"),
    ("property", "reviewing", 45000.00, "Roof damage from severe storm and hail"),
    ("property", "approved", 3200.00, "Broken window from fallen tree branch"),
    ("property", "submitted", 15000.00, "Fire damage to garage, electrical fire origin"),
    ("property", "approved", 1800.00, "Stolen laptop and electronics from home burglary"),
    ("property", "denied", 25000.00, "Flood damage - not covered under standard policy"),
    ("property", "reviewing", 5500.00, "HVAC system failure, replacement needed"),
]


async def seed_claims():
    conn = await asyncpg.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        user=os.getenv("POSTGRES_USER", "callcenter"),
        password=os.getenv("POSTGRES_PASSWORD", "callcenter_dev"),
        database=os.getenv("POSTGRES_DB", "callcenter"),
    )

    try:
        # Get all customer IDs
        customer_ids = await conn.fetch("SELECT id FROM customers ORDER BY created_at")

        if not customer_ids:
            print("No customers found. Please run seed_customers.py first.")
            return

        claim_count = 0
        for idx, (claim_type, status, amount, description) in enumerate(CLAIM_TEMPLATES):
            # Distribute claims across customers
            customer_id = customer_ids[idx % len(customer_ids)]['id']
            claim_id = uuid7()

            # Create history entry
            history = [
                {
                    "status": status,
                    "timestamp": "2025-01-10T10:00:00Z",
                    "note": "Claim submitted via AI call center",
                    "by": "ai_agent"
                }
            ]

            if status in ("reviewing", "approved", "denied"):
                history.append({
                    "status": "reviewing",
                    "timestamp": "2025-01-11T14:30:00Z",
                    "note": "Claim under review by adjuster",
                    "by": "adjuster_001"
                })

            if status in ("approved", "denied"):
                history.append({
                    "status": status,
                    "timestamp": "2025-01-13T09:15:00Z",
                    "note": f"Claim {status}" + (" - payment processed" if status == "approved" else " - see denial reason"),
                    "by": "adjuster_001"
                })

            # Documents
            documents = []
            if claim_type == "auto":
                documents = [
                    {"type": "photo", "url": f"/claims/{claim_id}/damage_photo_1.jpg"},
                    {"type": "police_report", "url": f"/claims/{claim_id}/police_report.pdf"}
                ]
            elif claim_type == "health":
                documents = [
                    {"type": "medical_bill", "url": f"/claims/{claim_id}/bill.pdf"},
                    {"type": "doctor_note", "url": f"/claims/{claim_id}/diagnosis.pdf"}
                ]
            elif claim_type == "property":
                documents = [
                    {"type": "photo", "url": f"/claims/{claim_id}/damage_photo.jpg"},
                    {"type": "repair_estimate", "url": f"/claims/{claim_id}/estimate.pdf"}
                ]

            await conn.execute(
                """
                INSERT INTO claims (id, customer_id, type, status, amount, description, documents, history)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                """,
                claim_id,
                customer_id,
                claim_type,
                status,
                Decimal(str(amount)),
                description,
                json.dumps(documents),
                json.dumps(history),
            )
            claim_count += 1
            print(f"Seeded claim {claim_count}: {claim_type} - {status} - ${amount}")

        # Create some additional claims for distribution
        additional_claims = min(50 - claim_count, 30)
        for i in range(additional_claims):
            customer_id = customer_ids[i % len(customer_ids)]['id']
            template_idx = i % len(CLAIM_TEMPLATES)
            claim_type, status, base_amount, description = CLAIM_TEMPLATES[template_idx]

            claim_id = uuid7()
            amount = Decimal(str(base_amount * (0.8 + i * 0.1)))  # Vary amounts

            history = [{
                "status": status,
                "timestamp": f"2025-01-{10 + (i % 20):02d}T10:00:00Z",
                "note": "Claim submitted",
                "by": "ai_agent"
            }]

            await conn.execute(
                """
                INSERT INTO claims (id, customer_id, type, status, amount, description, documents, history)
                VALUES ($1, $2, $3, $4, $5, $6, '[]'::jsonb, $7)
                """,
                claim_id,
                customer_id,
                claim_type,
                status,
                amount,
                description,
                json.dumps(history),
            )
            claim_count += 1

        total = await conn.fetchval("SELECT COUNT(*) FROM claims")
        by_status = await conn.fetch("SELECT status, COUNT(*) as count FROM claims GROUP BY status")
        by_type = await conn.fetch("SELECT type, COUNT(*) as count FROM claims GROUP BY type")

        print(f"\n=== Claims Summary ===")
        print(f"Total claims: {total}")
        print(f"\nBy status:")
        for row in by_status:
            print(f"  {row['status']}: {row['count']}")
        print(f"\nBy type:")
        for row in by_type:
            print(f"  {row['type']}: {row['count']}")

    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(seed_claims())
