"""
app/services/reviewer.py
─────────────────────────
Optimal Reviewer (Judge) Assignment Engine for HackBridge.

Assigns judges to hackathon projects using semantic similarity and the
Hungarian algorithm to maximise overall expertise-match while enforcing
a hard cap of 5 projects per judge.

═══════════════════════════════════════════════════════════════════════════
ALGORITHM OVERVIEW
═══════════════════════════════════════════════════════════════════════════

1. **Embedding**
   We use `sentence-transformers/all-MiniLM-L6-v2` to embed both project
   descriptions and judge skill-set strings into a shared 384-dimensional
   vector space. Cosine similarity in this space measures how well a
   judge's expertise aligns with a project's domain.

2. **Cost matrix construction**
   For each (project, judge) pair, the cost is  `1 − cosine_similarity`.
   Lower cost ⇒ better match.

3. **Hard constraint: max 5 projects per judge**
   The Hungarian algorithm operates on a *square* cost matrix and assumes
   one-to-one assignment. To allow a single judge to be assigned to up to
   5 projects we *replicate* each judge's row up to 5 times, creating
   "virtual judge slots". After solving, all slots that map to the same
   real judge are merged.

   Example with 15 projects and 4 judges:
     • 4 judges × 5 slots = 20 virtual rows (≥ 15 projects ✓)
     • The cost matrix is (20 × 15); padding with high cost if needed.
     • linear_sum_assignment picks the cheapest 15 assignments, spreading
       load across judges while respecting the cap.

4. **Write-back**
   Assignments are upserted into the `project_assignments` table so the
   endpoint is idempotent — calling it twice for the same hackathon
   overwrites rather than duplicates.

═══════════════════════════════════════════════════════════════════════════
"""

import logging
from typing import Any, Dict, List

import numpy as np
from scipy.optimize import linear_sum_assignment
from scipy.spatial.distance import cosine as cosine_distance
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

# ─── Constants ────────────────────────────────────────────────────────────────
_MAX_PROJECTS_PER_JUDGE: int = 5
_MODEL_NAME: str = "all-MiniLM-L6-v2"

# Lazy-loaded model singleton — avoids reloading the ~80 MB model on every call.
_model: SentenceTransformer | None = None


def _get_model() -> SentenceTransformer:
    """Return (and cache) the sentence-transformer model."""
    global _model  # noqa: PLW0603
    if _model is None:
        logger.info("Loading SentenceTransformer model '%s' …", _MODEL_NAME)
        _model = SentenceTransformer(_MODEL_NAME)
    return _model


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────


def assign_reviewers(
    hackathon_id: str,
    supabase_client: Any,
) -> List[Dict[str, Any]]:
    """Compute and persist optimal judge → project assignments.

    Args:
        hackathon_id: UUID of the target hackathon.
        supabase_client: An initialised Supabase client instance.

    Returns:
        A list of assignment dicts, each containing:
          - project_id (str)
          - judge_id (str)
          - similarity_score (float) — cosine similarity (0–1)
    """
    sb = supabase_client

    # ── 1. Fetch projects for this hackathon ──────────────────────────────
    projects_resp = (
        sb.table("projects")
        .select("id, title, description")
        .eq("hackathon_id", hackathon_id)
        .execute()
    )
    projects: List[Dict[str, Any]] = projects_resp.data or []

    if not projects:
        logger.warning("No projects found for hackathon %s", hackathon_id)
        return []

    # ── 2. Fetch judges for this hackathon ────────────────────────────────
    # Judges are users with role='judge' linked to this hackathon.
    judges_resp = (
        sb.table("users")
        .select("id, first_name, last_name, skills")
        .eq("role", "judge")
        .execute()
    )
    judges: List[Dict[str, Any]] = judges_resp.data or []

    if not judges:
        logger.warning("No judges found for hackathon %s", hackathon_id)
        return []

    n_projects = len(projects)
    n_judges = len(judges)
    logger.info(
        "Building assignment matrix: %d projects × %d judges (max %d each)",
        n_projects,
        n_judges,
        _MAX_PROJECTS_PER_JUDGE,
    )

    # ── 3. Embed project descriptions and judge skill strings ─────────────
    model = _get_model()

    project_texts: List[str] = [
        f"{p.get('title', '')}. {p.get('description', '')}" for p in projects
    ]
    # Join skills list into a single string for embedding.
    # If skills is already a string, use it directly.
    judge_texts: List[str] = []
    for j in judges:
        raw_skills = j.get("skills", [])
        if isinstance(raw_skills, list):
            judge_texts.append(", ".join(raw_skills))
        else:
            judge_texts.append(str(raw_skills or ""))

    # Encode returns numpy arrays of shape (n, 384)
    project_embeddings: np.ndarray = model.encode(project_texts, show_progress_bar=False)
    judge_embeddings: np.ndarray = model.encode(judge_texts, show_progress_bar=False)

    # ── 4. Build the cost matrix with judge replication ────────────────────
    #
    # We create `_MAX_PROJECTS_PER_JUDGE` copies of each judge's embedding
    # row to form a "virtual judge" matrix of shape:
    #   (n_judges × MAX_SLOTS, n_projects)
    #
    # This lets the Hungarian solver assign up to MAX_SLOTS projects to a
    # single judge (via different virtual slots), while still solving a
    # standard one-to-one assignment problem.

    n_virtual = n_judges * _MAX_PROJECTS_PER_JUDGE

    # Repeat each judge embedding MAX times → (n_virtual, 384)
    virtual_judge_embeddings = np.repeat(
        judge_embeddings, _MAX_PROJECTS_PER_JUDGE, axis=0
    )

    # Cosine distance cost matrix: shape (n_virtual, n_projects)
    # cost[i][j] = 1 − cosine_similarity(virtual_judge_i, project_j)
    cost_matrix = np.zeros((n_virtual, n_projects), dtype=np.float64)
    for vi in range(n_virtual):
        for pj in range(n_projects):
            cost_matrix[vi, pj] = cosine_distance(
                virtual_judge_embeddings[vi],
                project_embeddings[pj],
            )

    # If there are more virtual judge slots than projects, pad columns with
    # high cost so the matrix is square (required by linear_sum_assignment
    # only when rows > cols). scipy handles rectangular matrices, but
    # padding ensures every virtual slot *can* be assigned (dummy projects).
    if n_virtual > n_projects:
        padding = np.full(
            (n_virtual, n_virtual - n_projects),
            fill_value=1e6,  # Prohibitively high cost for dummy assignments
            dtype=np.float64,
        )
        cost_matrix = np.hstack([cost_matrix, padding])

    # ── 5. Solve with the Hungarian algorithm ─────────────────────────────
    #
    # `linear_sum_assignment` finds the permutation that minimises total
    # cost in O(n³). It returns matched (row_indices, col_indices).
    row_indices, col_indices = linear_sum_assignment(cost_matrix)

    # ── 6. Map virtual slots back to real judges & filter dummies ─────────
    assignments: List[Dict[str, Any]] = []
    for vi, pj in zip(row_indices, col_indices):
        # Skip dummy project columns (padding)
        if pj >= n_projects:
            continue

        real_judge_idx = vi // _MAX_PROJECTS_PER_JUDGE
        similarity = 1.0 - cost_matrix[vi, pj]  # Convert cost → similarity

        assignments.append(
            {
                "project_id": projects[pj]["id"],
                "judge_id": judges[real_judge_idx]["id"],
                "similarity_score": round(float(similarity), 4),
            }
        )

    logger.info("Computed %d assignments for hackathon %s", len(assignments), hackathon_id)

    # ── 7. Write assignments to Supabase ──────────────────────────────────
    # Delete previous assignments for idempotency, then bulk-insert new ones.
    project_ids = [p["id"] for p in projects]
    sb.table("project_assignments").delete().in_("project_id", project_ids).execute()

    if assignments:
        # Prepare rows for insertion (drop similarity_score — it's not a DB column)
        db_rows = [
            {"project_id": a["project_id"], "judge_id": a["judge_id"], "hackathon_id": hackathon_id}
            for a in assignments
        ]
        sb.table("project_assignments").insert(db_rows).execute()
        logger.info("Persisted %d assignments to project_assignments table", len(db_rows))

    return assignments
