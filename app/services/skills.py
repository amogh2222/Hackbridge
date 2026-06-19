"""
app/services/skills.py
──────────────────────
Skill Extraction Service for HackBridge.

Uses an LLM (via LiteLLM) to parse free-text participant bios and extract
a structured list of technical skills. This powers the participant profile
enrichment pipeline and feeds into the reviewer-assignment similarity engine.

Design decisions:
  • LiteLLM abstracts the model provider, so we can swap between OpenAI,
    Anthropic, Gemini, etc. via env vars without code changes.
  • The system prompt is intentionally restrictive ("return ONLY a JSON
    array") to minimise post-processing and reduce hallucination surface.
  • We parse with json.loads rather than eval() for safety.
  • Temperature is set to 0 for deterministic, repeatable extractions.
"""

import json
import logging
from typing import List

import litellm

logger = logging.getLogger(__name__)

# ─── System prompt ────────────────────────────────────────────────────────────
# Instructs the model to behave as a skill-extraction engine and return
# nothing but a JSON array of short skill strings.
_SYSTEM_PROMPT = (
    "You are a technical-skill extraction engine. "
    "Given a free-text bio of a hackathon participant, extract every "
    "distinct technical skill mentioned (programming languages, frameworks, "
    "cloud platforms, tools, databases, ML/AI techniques, etc.).\n\n"
    "Rules:\n"
    "1. Return ONLY a JSON array of strings — no markdown, no explanation.\n"
    '2. Each skill should be a concise canonical name (e.g. "Python", '
    '"React", "TensorFlow", "AWS Lambda").\n'
    "3. De-duplicate — do not repeat the same skill.\n"
    "4. If no skills are found, return an empty array: []\n"
)


async def extract_skills(bio: str) -> List[str]:
    """Extract technical skills from a free-text bio using an LLM.

    Args:
        bio: Free-text biography or self-description from a participant.

    Returns:
        A list of canonical skill strings, e.g. ["Python", "React", "AWS"].
        Returns an empty list on any failure so callers always get a usable
        value.
    """
    if not bio or not bio.strip():
        logger.warning("extract_skills called with empty bio — returning []")
        return []

    try:
        # ── Call the LLM via LiteLLM ──────────────────────────────────────
        # model is resolved from LITELLM_MODEL or defaults to gpt-4o-mini.
        # Temperature 0 ensures deterministic extraction.
        import os
        response = await litellm.acompletion(
            model=os.getenv("LITELLM_MODEL", "gpt-4o-mini"),
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": bio},
            ],
            temperature=0,
            max_tokens=512,
        )

        raw_content: str = response.choices[0].message.content.strip()

        # ── Parse the JSON array ──────────────────────────────────────────
        # The model should return pure JSON, but occasionally wraps it in
        # ```json ... ``` fences. Strip those defensively.
        if raw_content.startswith("```"):
            # Remove opening fence (with optional language tag) and closing fence
            raw_content = raw_content.split("\n", 1)[-1]  # drop first line
            raw_content = raw_content.rsplit("```", 1)[0]  # drop closing fence
            raw_content = raw_content.strip()

        skills: List[str] = json.loads(raw_content)

        # Validate that every element is a string
        if not isinstance(skills, list):
            logger.error("LLM returned non-list JSON: %s", type(skills))
            return []

        # Normalise: strip whitespace and drop empty strings
        skills = [s.strip() for s in skills if isinstance(s, str) and s.strip()]

        logger.info("Extracted %d skills from bio (%d chars)", len(skills), len(bio))
        return skills

    except json.JSONDecodeError as exc:
        logger.error("Failed to parse LLM response as JSON: %s", exc)
        return []
    except litellm.exceptions.APIError as exc:
        logger.error("LiteLLM API error during skill extraction: %s", exc)
        return []
    except Exception as exc:  # noqa: BLE001 — catch-all for resilience
        logger.exception("Unexpected error in extract_skills: %s", exc)
        return []
