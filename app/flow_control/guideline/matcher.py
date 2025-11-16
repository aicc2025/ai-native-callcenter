"""Two-stage guideline matcher: keyword pre-filter + LLM batch matching."""
from typing import List, Optional, Set
from uuid import UUID
import json
import re
from datetime import datetime

from openai import AsyncOpenAI

from app.config import config
from app.flow_control.guideline.models import Guideline, GuidelineMatch
from app.flow_control.guideline.store import GuidelineStore
from app.logging_config import get_logger

logger = get_logger(__name__)


class GuidelineMatcher:
    """
    Two-stage guideline matching engine.

    Stage 1: Keyword pre-filter (<5ms) - narrows from 100+ to 10-20 candidates
    Stage 2: LLM batch matching (<60ms P95) - evaluates conditions with structured output

    Total latency target: <60ms (P95)
    """

    def __init__(self, store: GuidelineStore):
        self.store = store
        self.openai = AsyncOpenAI(api_key=config.api.openai_api_key)

    def extract_keywords(self, message: str, min_length: int = 3) -> List[str]:
        """
        Extract keywords from message.

        Simple implementation: split on whitespace, filter short words,
        convert to lowercase.
        """
        # Remove punctuation and split
        words = re.findall(r'\b\w+\b', message.lower())

        # Filter out short words and common stopwords
        stopwords = {
            "the", "a", "an", "and", "or", "but", "is", "are", "was", "were",
            "be", "been", "being", "have", "has", "had", "do", "does", "did",
            "will", "would", "should", "could", "may", "might", "can", "i",
            "you", "he", "she", "it", "we", "they", "my", "your", "his", "her",
            "its", "our", "their", "this", "that", "these", "those",
        }

        keywords = [w for w in words if len(w) >= min_length and w not in stopwords]

        return keywords

    async def match_guidelines(
        self,
        user_message: str,
        journey_id: Optional[UUID] = None,
        state_name: Optional[str] = None,
        context_variables: Optional[dict] = None,
    ) -> List[GuidelineMatch]:
        """
        Match guidelines against user message using two-stage approach.

        Returns:
            List of GuidelineMatch objects sorted by priority (highest first)
        """
        start_time = datetime.utcnow()

        # Stage 1: Keyword pre-filter (<5ms)
        stage1_start = datetime.utcnow()
        message_keywords = self.extract_keywords(user_message)

        candidate_ids = self.store.get_candidates_by_keywords(message_keywords)

        # Get scope-appropriate guidelines
        scope_guidelines = await self.store.get_guidelines_by_scope(journey_id, state_name)
        scope_guideline_ids = {g.id for g in scope_guidelines}

        # Combine: candidates that match keywords AND are in scope
        relevant_ids = candidate_ids & scope_guideline_ids

        # If no keyword matches, use all scope guidelines (max 20)
        if not relevant_ids and scope_guidelines:
            relevant_ids = {g.id for g in scope_guidelines[:20]}

        candidates = await self.store.get_guidelines_by_ids(relevant_ids)

        stage1_elapsed = (datetime.utcnow() - stage1_start).total_seconds() * 1000

        if not candidates:
            logger.debug(
                "No guideline candidates found",
                keywords=message_keywords,
                journey_id=str(journey_id) if journey_id else None,
                state_name=state_name,
                stage1_ms=f"{stage1_elapsed:.1f}",
            )
            return []

        logger.debug(
            "Stage 1: Keyword pre-filter complete",
            candidates=len(candidates),
            latency_ms=f"{stage1_elapsed:.1f}",
        )

        # Stage 2: LLM batch matching (<60ms P95)
        stage2_start = datetime.utcnow()
        matches = await self._batch_evaluate_guidelines(
            user_message,
            candidates,
            journey_id,
            state_name,
            context_variables or {},
        )
        stage2_elapsed = (datetime.utcnow() - stage2_start).total_seconds() * 1000

        total_elapsed = (datetime.utcnow() - start_time).total_seconds() * 1000

        logger.info(
            "Guideline matching complete",
            total_matches=len(matches),
            candidates_evaluated=len(candidates),
            stage1_ms=f"{stage1_elapsed:.1f}",
            stage2_ms=f"{stage2_elapsed:.1f}",
            total_ms=f"{total_elapsed:.1f}",
        )

        # Sort by priority (considering scope hierarchy + numeric priority)
        matches.sort(
            key=lambda m: m.guideline.get_priority_score(journey_id, state_name),
            reverse=True,
        )

        return matches

    async def _batch_evaluate_guidelines(
        self,
        user_message: str,
        candidates: List[Guideline],
        journey_id: Optional[UUID],
        state_name: Optional[str],
        context_variables: dict,
    ) -> List[GuidelineMatch]:
        """
        Evaluate multiple guidelines in a single LLM call using structured output.

        Target: <60ms (P95)
        """
        # Build evaluation prompt
        guideline_descriptions = [
            {
                "id": str(g.id),
                "name": g.name,
                "description": g.description or "",
                "condition": g.condition,
                "action": g.action,
                "scope": g.scope.value,
            }
            for g in candidates
        ]

        system_prompt = """You are a guideline evaluation system for an AI call center.

Your task is to determine which guidelines (if any) apply to the user's message.
For each guideline, evaluate if its condition is met and assign a confidence score.

Return ONLY guidelines that clearly apply (confidence >= 0.6).
"""

        user_prompt = f"""User message: "{user_message}"

Context variables: {json.dumps(context_variables, indent=2)}

Journey: {journey_id or 'None'}
State: {state_name or 'None'}

Evaluate these guidelines:
{json.dumps(guideline_descriptions, indent=2)}

Return your evaluation in this JSON format:
{{
  "matches": [
    {{
      "guideline_id": "uuid",
      "applies": true/false,
      "confidence": 0.0-1.0,
      "reasoning": "brief explanation"
    }},
    ...
  ]
}}

Only include guidelines with confidence >= 0.6.
"""

        try:
            response = await self.openai.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.0,
            )

            result = json.loads(response.choices[0].message.content)

            # Build matches list
            matches = []
            for match_data in result.get("matches", []):
                if not match_data.get("applies", False):
                    continue

                guideline_id = UUID(match_data["guideline_id"])
                guideline = next((g for g in candidates if g.id == guideline_id), None)

                if guideline and match_data.get("confidence", 0) >= 0.6:
                    matches.append(
                        GuidelineMatch(
                            guideline=guideline,
                            confidence=match_data["confidence"],
                            reasoning=match_data.get("reasoning", ""),
                        )
                    )

            return matches

        except Exception as e:
            logger.error(
                "Error during LLM guideline evaluation",
                candidates=len(candidates),
                error=str(e),
            )
            return []
