#!/usr/bin/env python3
"""Seed knowledge_base table with deterministic mock data."""
import asyncio
import os
from uuid7 import uuid7

import asyncpg
from dotenv import load_dotenv

load_dotenv()

KNOWLEDGE_ARTICLES = [
    # Category: policy_coverage
    ("policy_coverage", ["auto", "coverage", "liability", "comprehensive"],
     "What does auto insurance liability coverage include?",
     "Auto insurance liability coverage includes bodily injury liability (covers medical expenses if you injure someone) and property damage liability (covers damage you cause to another person's property). It does not cover your own vehicle or injuries.",
     100),

    ("policy_coverage", ["health", "coverage", "preventive", "annual"],
     "Does my health insurance cover annual checkups?",
     "Yes, most health insurance policies cover one annual preventive care visit per year at no cost to you. This typically includes physical examination, blood pressure screening, and age-appropriate preventive services.",
     95),

    ("policy_coverage", ["property", "homeowners", "flood", "coverage"],
     "Does homeowners insurance cover flood damage?",
     "Standard homeowners insurance policies do NOT cover flood damage. You need a separate flood insurance policy through the National Flood Insurance Program (NFIP) or a private insurer.",
     90),

    ("policy_coverage", ["deductible", "payment", "copay"],
     "What is the difference between deductible and copay?",
     "A deductible is the amount you pay out-of-pocket before insurance kicks in. A copay is a fixed amount you pay for covered services after meeting your deductible. For example, $30 for a doctor visit.",
     85),

    ("policy_coverage", ["auto", "collision", "comprehensive"],
     "What's the difference between collision and comprehensive coverage?",
     "Collision coverage pays for damage to your car from accidents with other vehicles or objects. Comprehensive coverage pays for damage from non-collision events like theft, vandalism, fire, or natural disasters.",
     90),

    # Category: claims_process
    ("claims_process", ["claim", "submit", "file", "process"],
     "How do I file a claim?",
     "You can file a claim by calling our 24/7 hotline, using our mobile app, or through our website. You'll need your policy number, date of incident, description of what happened, and any supporting documentation like photos or police reports.",
     100),

    ("claims_process", ["claim", "status", "check", "track"],
     "How can I check my claim status?",
     "You can check your claim status by logging into your online account, using our mobile app, or calling our claims department with your claim number. Claims are typically reviewed within 3-5 business days.",
     95),

    ("claims_process", ["claim", "denied", "appeal", "rejection"],
     "What should I do if my claim is denied?",
     "If your claim is denied, you'll receive a letter explaining the reason. You have the right to appeal by submitting additional documentation or requesting a review. Appeals must be filed within 60 days of the denial notice.",
     85),

    ("claims_process", ["claim", "payment", "timeline", "processing"],
     "How long does it take to receive claim payment?",
     "Once your claim is approved, payment is typically processed within 5-10 business days. Direct deposit is faster (3-5 days) compared to check payment (7-10 days). Complex claims may take longer.",
     90),

    ("claims_process", ["documentation", "required", "documents", "proof"],
     "What documentation do I need for a claim?",
     "Required documentation varies by claim type. Generally you need: photos of damage, police report (if applicable), repair estimates, medical bills (for health/injury claims), and any receipts. Our claims adjuster will request specific documents as needed.",
     85),

    # Category: billing_payment
    ("billing_payment", ["premium", "payment", "due", "billing"],
     "When is my premium payment due?",
     "Premium payments are due on the date shown on your billing statement, typically the first of the month. You can set up automatic payments to avoid missing due dates. A 10-day grace period is provided before cancellation.",
     95),

    ("billing_payment", ["payment", "methods", "pay", "options"],
     "What payment methods do you accept?",
     "We accept credit cards (Visa, MasterCard, Amex), debit cards, bank transfers (ACH), checks, and automatic monthly payments. Online and mobile app payments are processed immediately.",
     90),

    ("billing_payment", ["discount", "savings", "reduce", "premium"],
     "How can I reduce my insurance premium?",
     "You can reduce your premium by: increasing your deductible, bundling multiple policies, maintaining good credit, taking defensive driving courses (auto), installing security systems (property), and asking about available discounts.",
     85),

    ("billing_payment", ["late", "payment", "penalty", "fee"],
     "What happens if I miss a payment?",
     "You have a 10-day grace period after the due date. After that, a late fee may be charged and your policy could be cancelled. Contact us immediately if you're having trouble making payments to discuss options.",
     80),

    ("billing_payment", ["autopay", "automatic", "recurring", "payment"],
     "Can I set up automatic payments?",
     "Yes, you can set up automatic monthly payments from your bank account or credit card through your online account or by calling customer service. This ensures you never miss a payment and may qualify for a small discount.",
     90),

    # Category: account_management
    ("account_management", ["policy", "change", "update", "modify"],
     "How do I update my policy information?",
     "You can update your policy information (address, phone, vehicles, etc.) by logging into your online account, calling customer service, or using our mobile app. Some changes may affect your premium.",
     90),

    ("account_management", ["beneficiary", "change", "update"],
     "How do I change my beneficiary?",
     "To change your beneficiary, submit a beneficiary change form available in your online account or by calling customer service. The change takes effect once we process the signed form.",
     85),

    ("account_management", ["cancel", "policy", "termination"],
     "How do I cancel my policy?",
     "To cancel your policy, contact customer service in writing or by phone. Cancellation is effective on the date you specify (must be future-dated). You may receive a refund for unused premium depending on timing.",
     80),

    ("account_management", ["add", "driver", "vehicle", "coverage"],
     "How do I add a driver or vehicle to my auto policy?",
     "You can add a driver or vehicle by logging into your account, calling customer service, or using the mobile app. You'll need the driver's license information or vehicle VIN. Your premium will be adjusted accordingly.",
     90),

    ("account_management", ["id", "card", "proof", "insurance"],
     "How do I get my insurance ID card?",
     "Your insurance ID card is available instantly in our mobile app or online account. You can download and print it, or request a physical card be mailed to you (arrives in 5-7 business days).",
     95),
]


async def seed_knowledge():
    conn = await asyncpg.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        user=os.getenv("POSTGRES_USER", "callcenter"),
        password=os.getenv("POSTGRES_PASSWORD", "callcenter_dev"),
        database=os.getenv("POSTGRES_DB", "callcenter"),
    )

    try:
        for category, keywords, question, answer, priority in KNOWLEDGE_ARTICLES:
            article_id = uuid7()

            await conn.execute(
                """
                INSERT INTO knowledge_base (id, category, keywords, question, answer, priority)
                VALUES ($1, $2, $3, $4, $5, $6)
                """,
                article_id,
                category,
                keywords,
                question,
                answer,
                priority,
            )
            print(f"Seeded: [{category}] {question[:60]}...")

        # Add more variations to reach 50-100 articles
        additional_articles = [
            ("policy_coverage", ["dental", "coverage", "teeth", "orthodontics"],
             "Does health insurance cover dental work?",
             "Basic health insurance typically does NOT cover dental work. You need a separate dental insurance policy. However, some health plans cover emergency dental care for injuries.",
             75),

            ("policy_coverage", ["vision", "glasses", "eye", "exam"],
             "Is vision coverage included in health insurance?",
             "Vision coverage is usually separate from health insurance. You may need a vision plan for eye exams, glasses, and contacts. Some health plans include one basic eye exam per year.",
             75),

            ("claims_process", ["emergency", "claim", "urgent", "immediate"],
             "How do I file an emergency claim?",
             "For emergencies, call our 24/7 emergency hotline immediately. For auto accidents, ensure everyone is safe and call police. For property emergencies like fire or flood, secure the property and document damage with photos.",
             100),

            ("billing_payment", ["refund", "overpayment", "credit"],
             "How do I request a refund?",
             "Refunds for overpayments or policy cancellations are automatically processed within 15 business days. You can request expedited processing by calling customer service.",
             70),

            ("account_management", ["password", "login", "reset", "account"],
             "I forgot my password, how do I reset it?",
             "Click 'Forgot Password' on the login page. Enter your email address and we'll send a reset link. For security, the link expires in 24 hours. Contact support if you don't receive the email.",
             85),
        ]

        for category, keywords, question, answer, priority in additional_articles:
            article_id = uuid7()
            await conn.execute(
                """
                INSERT INTO knowledge_base (id, category, keywords, question, answer, priority)
                VALUES ($1, $2, $3, $4, $5, $6)
                """,
                article_id,
                category,
                keywords,
                question,
                answer,
                priority,
            )
            print(f"Seeded: [{category}] {question[:60]}...")

        total = await conn.fetchval("SELECT COUNT(*) FROM knowledge_base")
        by_category = await conn.fetch(
            "SELECT category, COUNT(*) as count FROM knowledge_base GROUP BY category ORDER BY count DESC"
        )

        print(f"\n=== Knowledge Base Summary ===")
        print(f"Total articles: {total}")
        print(f"\nBy category:")
        for row in by_category:
            print(f"  {row['category']}: {row['count']}")

    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(seed_knowledge())
