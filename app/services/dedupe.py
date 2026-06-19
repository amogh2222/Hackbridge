"""
app/services/dedupe.py
──────────────────────
Duplicate-User Detection Service for HackBridge.

Uses fuzzy string matching (via RapidFuzz) to detect near-duplicate
participant registrations. This is critical for hackathon integrity — it
catches cases like:
  • Typos in names ("Rahul Sharma" vs "Rahul K Sharma")
  • Slight email variations ("rahul.sharma@gmail.com" vs "rahul.ksharma@gmail.com")
  • Re-registrations under a different name/email combo

Methodology:
  We compare the *new* user against every *existing* user using a weighted
  composite of two fuzzy similarity scores:

    composite = 0.40 × name_similarity + 0.60 × email_similarity

  • **Name similarity** uses `token_sort_ratio`, which tokenises both strings,
    sorts the tokens alphabetically, then computes a ratio. This makes it
    resilient to name-part reordering ("Patel Priya" == "Priya Patel") and
    middle-name insertion ("Rahul Sharma" ≈ "Rahul K Sharma").

  • **Email similarity** also uses `token_sort_ratio` but operates on the
    *local part* (before '@') split by common separators (., _, -). Email is
    weighted higher (60%) because it's a stronger identity signal — names are
    far more likely to collide legitimately.

  A composite score > 85 is classified as a probable duplicate.
"""

import logging
from typing import Any, Dict, List, Optional

from rapidfuzz.fuzz import token_sort_ratio

logger = logging.getLogger(__name__)

# ─── Thresholds & weights ─────────────────────────────────────────────────────
_NAME_WEIGHT: float = 0.40    # Contribution of name similarity to composite
_EMAIL_WEIGHT: float = 0.60   # Contribution of email similarity to composite
_DUPLICATE_THRESHOLD: float = 85.0  # Composite score above this → duplicate


def _full_name(user: Dict[str, Any]) -> str:
    """Build a full-name string from first_name / last_name fields.

    Handles missing fields gracefully — if only one name part exists we
    still produce a usable string for fuzzy comparison.
    """
    first = (user.get("first_name") or "").strip()
    last = (user.get("last_name") or "").strip()
    return f"{first} {last}".strip()


def _email_local(user: Dict[str, Any]) -> str:
    """Extract the local part of an email (before '@') for comparison.

    We compare local parts only because the domain is less discriminating
    (many users share @gmail.com).  Dots, underscores, and hyphens are
    replaced with spaces so token_sort_ratio can treat each segment as a
    separate token.
    """
    email = (user.get("email") or "").strip().lower()
    local = email.split("@")[0] if "@" in email else email
    # Normalise separators → spaces so token_sort_ratio tokenises them
    for sep in (".", "_", "-"):
        local = local.replace(sep, " ")
    return local


def check_duplicate(
    new_user: Dict[str, Any],
    existing_users: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Compare a new user record against all existing users for duplicates.

    Args:
        new_user: Dict with at least 'email', 'first_name', 'last_name'.
        existing_users: List of user dicts from the database, each expected
                        to have 'id', 'email', 'first_name', 'last_name'.

    Returns:
        A dict with:
          - is_duplicate (bool): True if composite score > 85%.
          - match_confidence (float): Highest composite similarity found.
          - matched_user_id (str | None): ID of the best-matching user, or
            None if no duplicate detected.
    """
    # ── Default: no duplicate ─────────────────────────────────────────────
    result: Dict[str, Any] = {
        "is_duplicate": False,
        "match_confidence": 0.0,
        "matched_user_id": None,
    }

    if not existing_users:
        return result

    new_name: str = _full_name(new_user)
    new_email_local: str = _email_local(new_user)

    best_score: float = 0.0
    best_match_id: Optional[str] = None

    for existing in existing_users:
        # ── Name similarity (token-sort ratio, 0–100) ─────────────────────
        # token_sort_ratio("Rahul Sharma", "Rahul K Sharma") ≈ 87
        # token_sort_ratio("Priya Patel", "Priyanka Patel")  ≈ 80
        name_sim: float = token_sort_ratio(new_name, _full_name(existing))

        # ── Email local-part similarity ───────────────────────────────────
        # "rahul sharma" vs "rahul ksharma" → high similarity
        email_sim: float = token_sort_ratio(new_email_local, _email_local(existing))

        # ── Weighted composite score ──────────────────────────────────────
        # composite = 0.40 × name_sim + 0.60 × email_sim
        # Email is weighted more heavily because it's a stronger unique
        # identifier — two people can legitimately share a name, but similar
        # email local-parts strongly suggest the same person.
        composite: float = (_NAME_WEIGHT * name_sim) + (_EMAIL_WEIGHT * email_sim)

        if composite > best_score:
            best_score = composite
            best_match_id = existing.get("id")

    # ── Apply threshold ───────────────────────────────────────────────────
    if best_score > _DUPLICATE_THRESHOLD:
        result["is_duplicate"] = True
        result["match_confidence"] = round(best_score, 2)
        result["matched_user_id"] = best_match_id
        logger.warning(
            "Duplicate detected: new_user=%s matched existing_id=%s "
            "(confidence=%.1f%%)",
            new_user.get("email"),
            best_match_id,
            best_score,
        )
    else:
        # Even when no duplicate, report the highest score for diagnostics
        result["match_confidence"] = round(best_score, 2)
        logger.info(
            "No duplicate for %s (best composite=%.1f%%)",
            new_user.get("email"),
            best_score,
        )

    return result
