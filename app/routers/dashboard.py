"""
HackBridge — Dashboard Router
Aggregated metrics for the organizer dashboard.
All queries hit Supabase's PostgREST API with server-side counting.
"""

from fastapi import APIRouter, HTTPException
from app.database import get_supabase

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])


@router.get("/organizer")
async def organizer_dashboard():
    """
    Returns a single JSON payload with all key platform metrics.
    The frontend renders these as stat cards on the organizer dashboard.

    Metrics:
      - total_active_events:   hackathons with status = 'active'
      - total_participants:    users with role = 'participant'
      - total_judges:          users with role = 'judge'
      - total_projects:        all submitted projects
      - completion_rate:       % of projects that have at least 1 evaluation
      - evaluations_completed: total evaluation records
      - bias_flags_detected:   evaluations flagged by the bias detector
    """
    sb = get_supabase()

    try:
        # Active hackathons
        active_events = (
            sb.table("hackathons")
            .select("id", count="exact")
            .eq("status", "active")
            .execute()
        )

        # Participant count
        participants = (
            sb.table("users")
            .select("id", count="exact")
            .eq("role", "participant")
            .execute()
        )

        # Judge count
        judges = (
            sb.table("users")
            .select("id", count="exact")
            .eq("role", "judge")
            .execute()
        )

        # Total projects
        projects = (
            sb.table("projects")
            .select("id", count="exact")
            .execute()
        )

        # All evaluations
        evaluations = (
            sb.table("evaluations")
            .select("id, project_id", count="exact")
            .execute()
        )

        # Bias-flagged evaluations
        bias_flags = (
            sb.table("evaluations")
            .select("id", count="exact")
            .eq("bias_flag", True)
            .execute()
        )

        # Completion rate: projects with ≥1 evaluation / total projects
        total_projects = projects.count or 0
        if total_projects > 0 and evaluations.data:
            evaluated_project_ids = set(e["project_id"] for e in evaluations.data)
            completion_rate = round(len(evaluated_project_ids) / total_projects * 100, 1)
        else:
            completion_rate = 0.0

        return {
            "total_active_events": active_events.count or 0,
            "total_participants": participants.count or 0,
            "total_judges": judges.count or 0,
            "total_projects": total_projects,
            "completion_rate": completion_rate,
            "evaluations_completed": evaluations.count or 0,
            "bias_flags_detected": bias_flags.count or 0,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Dashboard query failed: {str(e)}")


@router.get("/audit-log")
async def get_audit_log():
    """
    Returns the full audit log for transparency review.
    Ordered by most recent first. Essential for the 'transparency' judging criterion.
    """
    sb = get_supabase()

    try:
        result = (
            sb.table("audit_log")
            .select("*")
            .order("created_at", desc=True)
            .limit(200)
            .execute()
        )
        return {"audit_log": result.data, "count": len(result.data)}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Audit log query failed: {str(e)}")


@router.get("/leaderboard/{hackathon_id}")
async def get_leaderboard(hackathon_id: str):
    """
    Returns project rankings by average total_score for a given hackathon.
    Excludes bias-flagged evaluations from the average calculation.
    """
    sb = get_supabase()

    try:
        # Fetch all non-flagged evaluations for this hackathon
        evals = (
            sb.table("evaluations")
            .select("project_id, total_score")
            .eq("hackathon_id", hackathon_id)
            .eq("bias_flag", False)
            .execute()
        )

        # Fetch project metadata
        projects = (
            sb.table("projects")
            .select("id, title, team_name")
            .eq("hackathon_id", hackathon_id)
            .execute()
        )

        # Build project lookup
        project_map = {p["id"]: p for p in projects.data}

        # Aggregate scores per project
        scores: dict[str, list[float]] = {}
        for ev in evals.data:
            pid = ev["project_id"]
            scores.setdefault(pid, []).append(ev["total_score"])

        # Compute averages and rank
        leaderboard = []
        for pid, score_list in scores.items():
            avg = sum(score_list) / len(score_list)
            project = project_map.get(pid, {})
            leaderboard.append({
                "project_id": pid,
                "title": project.get("title", "Unknown"),
                "team_name": project.get("team_name", "Unknown"),
                "average_score": round(avg, 2),
                "num_evaluations": len(score_list),
            })

        # Sort descending by average score
        leaderboard.sort(key=lambda x: x["average_score"], reverse=True)

        # Add rank
        for i, entry in enumerate(leaderboard):
            entry["rank"] = i + 1

        return {"leaderboard": leaderboard, "hackathon_id": hackathon_id}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Leaderboard query failed: {str(e)}")
