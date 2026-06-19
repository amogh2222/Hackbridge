"""
app/routers/ai.py
─────────────────
AI-powered API endpoints for HackBridge.

This router exposes four capabilities:
  POST /api/ai/extract-skills   — Extract technical skills from a bio
  POST /api/ai/dedupe           — Check a new user for duplicates
  POST /api/ai/assign-reviewers — Optimally assign judges to projects
  POST /api/ai/detect-bias      — Flag statistically biased evaluations
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.database import get_supabase
from app.services.skills import extract_skills
from app.services.dedupe import check_duplicate
from app.services.reviewer import assign_reviewers
from app.services.bias import detect_bias

router = APIRouter(prefix="/api/ai", tags=["AI"])


# ─── Request schemas ──────────────────────────────────────────────────────────

class SkillsRequest(BaseModel):
    """Payload for the skill-extraction endpoint."""
    bio: str


class DedupeRequest(BaseModel):
    """Payload for the duplicate-detection endpoint."""
    email: str
    first_name: str
    last_name: str


class AssignRequest(BaseModel):
    """Payload for the reviewer-assignment endpoint."""
    hackathon_id: str


class BiasRequest(BaseModel):
    """Payload for the bias-detection endpoint."""
    hackathon_id: str


# ─── Endpoints ────────────────────────────────────────────────────────────────

@router.post("/extract-skills")
async def extract_skills_endpoint(req: SkillsRequest):
    """Extract technical skills from a free-text participant bio.

    Returns a JSON object with a `skills` list, e.g.:
        {"skills": ["Python", "React", "TensorFlow"]}
    """
    skills = await extract_skills(req.bio)
    return {"skills": skills}


@router.post("/dedupe")
async def dedupe_endpoint(req: DedupeRequest):
    """Check whether a new user is a probable duplicate of an existing one.

    If a duplicate is detected (composite similarity > 85%), an audit-log
    entry is written automatically for compliance tracking.

    Returns:
        {"is_duplicate": bool, "match_confidence": float, "matched_user_id": str|null}
    """
    sb = get_supabase()

    # Fetch all existing users for comparison
    existing = sb.table("users").select("*").execute()

    result = check_duplicate(
        {"email": req.email, "first_name": req.first_name, "last_name": req.last_name},
        existing.data,
    )

    # If a duplicate was found, log it for audit / compliance
    if result["is_duplicate"]:
        sb.table("audit_log").insert(
            {
                "action": "DUPLICATE_DETECTED",
                "reference_id": result.get("matched_user_id"),
                "details": f"Confidence: {result['match_confidence']:.1f}%",
            }
        ).execute()

    return result


@router.post("/assign-reviewers")
async def assign_reviewers_endpoint(req: AssignRequest):
    """Run the optimal reviewer-assignment algorithm for a hackathon.

    Uses sentence-transformer embeddings + the Hungarian algorithm to
    maximise expertise-match between judges and projects, subject to a
    hard cap of 5 projects per judge.

    Returns:
        {"assignments": [...], "count": int}
    """
    sb = get_supabase()
    assignments = assign_reviewers(req.hackathon_id, sb)
    return {"assignments": assignments, "count": len(assignments)}


@router.post("/detect-bias")
async def detect_bias_endpoint(req: BiasRequest):
    """Detect and flag statistically biased evaluation scores.

    Computes per-project Z-scores and flags evaluations where |z| > 2.
    Flagged evaluations are updated in-place and audit-log entries are
    created.

    Returns:
        {"flagged_evaluations": [...], "count": int}
    """
    sb = get_supabase()
    flagged = detect_bias(req.hackathon_id, sb)
    return {"flagged_evaluations": flagged, "count": len(flagged)}
