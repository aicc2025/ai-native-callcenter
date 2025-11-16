"""Response validator with auto-fix and audit logging."""
from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime
import json

from openai import AsyncOpenAI

from app.config import config
from app.db.connection import DatabasePool
from app.flow_control.guideline.models import Guideline
from app.logging_config import get_logger
from uuid7 import uuid7

logger = get_logger(__name__)


class ValidationResult:
    """Result of response validation."""

    def __init__(
        self,
        is_valid: bool,
        violations: List[Dict[str, Any]],
        confidence: float,
        suggested_fixes: Optional[List[str]] = None,
        fixed_response: Optional[str] = None,
    ):
        self.is_valid = is_valid
        self.violations = violations
        self.confidence = confidence
        self.suggested_fixes = suggested_fixes or []
        self.fixed_response = fixed_response


class ResponseValidator:
    """
    Validates AI responses against active guidelines.

    Uses LLM structured output for ARQ-inspired validation.
    Target latency: <30ms
    """

    def __init__(self, db_pool: DatabasePool):
        self.db = db_pool
        self.openai = AsyncOpenAI(api_key=config.api.openai_api_key)

    async def validate_response(
        self,
        response: str,
        guidelines: List[Guideline],
        session_id: str,
        journey_id: Optional[UUID] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> ValidationResult:
        """
        Validate response against active guidelines.

        Returns:
            ValidationResult with violations and auto-fix suggestions
        """
        start_time = datetime.utcnow()

        if not guidelines:
            logger.debug("No guidelines to validate against", session_id=session_id)
            return ValidationResult(
                is_valid=True, violations=[], confidence=1.0
            )

        # Build validation prompt
        guideline_rules = [
            {
                "id": str(g.id),
                "name": g.name,
                "condition": g.condition,
                "action": g.action,
                "priority": g.priority,
            }
            for g in guidelines
        ]

        system_prompt = """You are a response validation system for an AI call center.

Your task is to check if the AI's response violates any active guidelines.

Guidelines represent business rules that MUST be followed.
Evaluate each guideline carefully and identify any violations.
"""

        user_prompt = f"""AI Response to validate:
"{response}"

Context: {json.dumps(context or {}, indent=2)}

Active guidelines:
{json.dumps(guideline_rules, indent=2)}

Validate the response and return in this JSON format:
{{
  "is_valid": true/false,
  "violations": [
    {{
      "guideline_id": "uuid",
      "guideline_name": "name",
      "violation_description": "what rule was broken",
      "severity": "critical|high|medium|low"
    }},
    ...
  ],
  "confidence": 0.0-1.0,
  "suggested_fixes": ["fix suggestion 1", "fix suggestion 2", ...]
}}
"""

        try:
            response_obj = await self.openai.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.0,
            )

            result = json.loads(response_obj.choices[0].message.content)

            validation_result = ValidationResult(
                is_valid=result.get("is_valid", True),
                violations=result.get("violations", []),
                confidence=result.get("confidence", 1.0),
                suggested_fixes=result.get("suggested_fixes", []),
            )

            # If invalid and auto-fix is possible, attempt it
            if not validation_result.is_valid and validation_result.suggested_fixes:
                fixed_response = await self._attempt_auto_fix(
                    response, validation_result.violations, validation_result.suggested_fixes
                )
                validation_result.fixed_response = fixed_response

            elapsed = (datetime.utcnow() - start_time).total_seconds() * 1000

            logger.info(
                "Response validation complete",
                session_id=session_id,
                is_valid=validation_result.is_valid,
                violations_count=len(validation_result.violations),
                confidence=validation_result.confidence,
                auto_fixed=validation_result.fixed_response is not None,
                latency_ms=f"{elapsed:.1f}",
            )

            # Persist validation result to audit table
            await self._log_validation(
                session_id,
                journey_id,
                [g.id for g in guidelines],
                response,
                validation_result,
                int(elapsed),
            )

            return validation_result

        except Exception as e:
            logger.error(
                "Error during response validation",
                session_id=session_id,
                error=str(e),
            )
            # On error, assume valid to not block response
            return ValidationResult(is_valid=True, violations=[], confidence=0.0)

    async def _attempt_auto_fix(
        self,
        original_response: str,
        violations: List[Dict[str, Any]],
        suggested_fixes: List[str],
    ) -> Optional[str]:
        """
        Attempt to auto-fix response based on violations.

        Returns:
            Fixed response or None if auto-fix failed
        """
        try:
            fix_prompt = f"""Original AI response:
"{original_response}"

Violations detected:
{json.dumps(violations, indent=2)}

Suggested fixes:
{json.dumps(suggested_fixes, indent=2)}

Please provide a corrected version of the response that addresses all violations while maintaining the original intent and tone.

Return ONLY the fixed response text, no explanations or meta-commentary.
"""

            response = await self.openai.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "system",
                        "content": "You are a response correction system. Fix the given response to comply with business rules.",
                    },
                    {"role": "user", "content": fix_prompt},
                ],
                temperature=0.3,
            )

            fixed = response.choices[0].message.content.strip()

            logger.info(
                "Auto-fix attempted",
                original_length=len(original_response),
                fixed_length=len(fixed),
            )

            return fixed

        except Exception as e:
            logger.error("Error during auto-fix", error=str(e))
            return None

    async def _log_validation(
        self,
        session_id: str,
        journey_id: Optional[UUID],
        guideline_ids: List[UUID],
        original_response: str,
        result: ValidationResult,
        latency_ms: int,
    ) -> None:
        """Persist validation result to validation_audit table."""
        try:
            audit_id = uuid7()

            await self.db.execute(
                """
                INSERT INTO validation_audit
                (id, session_id, journey_id, guideline_ids, is_valid,
                 violations, suggested_fixes, confidence, latency_ms,
                 original_response, fixed_response, created_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, CURRENT_TIMESTAMP)
                """,
                audit_id,
                session_id,
                journey_id,
                guideline_ids,
                result.is_valid,
                json.dumps(result.violations),
                json.dumps(result.suggested_fixes),
                result.confidence,
                latency_ms,
                original_response,
                result.fixed_response,
            )

            logger.debug("Validation result logged to audit", audit_id=str(audit_id))

        except Exception as e:
            logger.error("Failed to log validation to audit table", error=str(e))
            # Don't raise - logging failure shouldn't block validation
