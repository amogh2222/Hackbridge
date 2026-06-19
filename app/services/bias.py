"""
app/services/bias.py
────────────────────
Bias Detection Service for HackBridge.

Identifies statistically anomalous evaluation scores using Z-score analysis.
When a judge's score for a project deviates by more than 2 standard
deviations from the per-project mean, it is flagged as potential bias and
recorded in the audit log.

═══════════════════════════════════════════════════════════════════════════
STATISTICAL METHODOLOGY
═══════════════════════════════════════════════════════════════════════════

For each project p evaluated by a set of judges:

  1. Collect all total_score values: S_p = {s₁, s₂, …, sₖ}
  2. Compute the **mean**:   μ_p = (1/k) Σ sᵢ
  3. Compute the **population standard deviation**:
       σ_p = √[ (1/k) Σ (sᵢ − μ_p)² ]
  4. For each individual score sᵢ, compute its **Z-score**:
       z = (sᵢ − μ_p) / σ_p
     The Z-score measures how many standard deviations a score lies from
     the mean. Under a normal distribution:
       • |z| ≤ 1  → ~68% of scores (typical)
       • |z| ≤ 2  → ~95% of scores (normal variation)
       • |z| > 2  → ~5%  of scores (potential outlier / bias)

  5. If |z| > 2, we flag the evaluation:
       • Set `bias_flag = True` on the evaluations row.
       • Insert an audit_log entry with action = 'BIAS_DETECTED'.

Why Z > 2?
  Using 2 standard deviations as the threshold balances sensitivity with
  false-positive rate. In a normally distributed scoring population, only
  ~5% of honest scores would be flagged — an acceptable false-positive
  rate for human review. The threshold can be tuned via _Z_THRESHOLD.

Edge cases:
  • If a project has ≤ 1 evaluation, we cannot compute σ (or σ = 0),
    so we skip that project — there's no population to compare against.
  • If all judges give the exact same score (σ = 0), Z is undefined;
    we treat this as "no outlier" and skip.

═══════════════════════════════════════════════════════════════════════════
"""

import logging
import math
from collections import defaultdict
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

# ─── Configuration ────────────────────────────────────────────────────────────
_Z_THRESHOLD: float = 1.5  # Flag evaluations where |z| exceeds this value


def detect_bias(
    hackathon_id: str,
    supabase_client: Any,
) -> List[Dict[str, Any]]:
    """Detect and flag biased evaluations for a given hackathon.

    Args:
        hackathon_id: UUID of the hackathon to analyse.
        supabase_client: An initialised Supabase client instance.

    Returns:
        A list of dicts for every flagged evaluation, each containing:
          - evaluation_id (str)
          - project_id (str)
          - judge_id (str)
          - total_score (float)
          - mean (float)   — per-project mean score
          - std (float)    — per-project standard deviation
          - z_score (float)
    """
    sb = supabase_client

    # ── 1. Fetch all evaluations linked to this hackathon ─────────────────
    #    We join through the projects table to filter by hackathon_id.
    eval_resp = (
        sb.table("evaluations")
        .select("id, project_id, judge_id, total_score, hackathon_id")
        .eq("hackathon_id", hackathon_id)
        .execute()
    )
    evaluations: List[Dict[str, Any]] = eval_resp.data or []

    if not evaluations:
        logger.info("No evaluations found for hackathon %s", hackathon_id)
        return []

    logger.info(
        "Analysing %d evaluations for hackathon %s",
        len(evaluations),
        hackathon_id,
    )

    # ── 2. Group evaluations by project_id ────────────────────────────────
    #    Each project accumulates a list of evaluation dicts.
    by_project: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for ev in evaluations:
        by_project[ev["project_id"]].append(ev)

    # ── 3. Compute per-project statistics and flag outliers ────────────────
    flagged: List[Dict[str, Any]] = []

    for project_id, evals in by_project.items():
        scores = [e["total_score"] for e in evals]
        n = len(scores)

        # Need at least 2 evaluations to compute a meaningful std deviation
        if n < 2:
            logger.debug(
                "Project %s has only %d evaluation(s) — skipping bias check",
                project_id,
                n,
            )
            continue

        # ── Mean ──────────────────────────────────────────────────────────
        # μ = (1/n) Σ sᵢ
        mean: float = sum(scores) / n

        # ── Population standard deviation ─────────────────────────────────
        # σ = √[ (1/n) Σ (sᵢ − μ)² ]
        # We use population std (not sample std) because the set of judges
        # who evaluated this project IS the full population of interest.
        variance: float = sum((s - mean) ** 2 for s in scores) / n
        std: float = math.sqrt(variance)

        # If σ = 0 every judge gave the same score — no outlier possible
        if std == 0:
            logger.debug(
                "Project %s has zero variance (all scores = %.1f) — skipping",
                project_id,
                mean,
            )
            continue

        # ── Z-score for each evaluation ───────────────────────────────────
        for ev in evals:
            z: float = (ev["total_score"] - mean) / std

            if abs(z) > _Z_THRESHOLD:
                logger.warning(
                    "BIAS FLAG: evaluation %s (judge %s, project %s) — "
                    "score=%.1f, mean=%.1f, std=%.1f, z=%.2f",
                    ev["id"],
                    ev["judge_id"],
                    project_id,
                    ev["total_score"],
                    mean,
                    std,
                    z,
                )

                # ── 4a. Update the evaluation row with bias_flag ──────────
                sb.table("evaluations").update(
                    {"bias_flag": True}
                ).eq("id", ev["id"]).execute()

                # ── 4b. Write an audit trail entry ────────────────────────
                sb.table("audit_log").insert(
                    {
                        "action": "BIAS_DETECTED",
                        "reference_id": ev["id"],
                        "details": (
                            f"Z-score={z:.2f} (threshold=±{_Z_THRESHOLD}). "
                            f"Score={ev['total_score']}, "
                            f"project_mean={mean:.1f}, project_std={std:.1f}."
                        ),
                    }
                ).execute()

                flagged.append(
                    {
                        "evaluation_id": ev["id"],
                        "project_id": project_id,
                        "judge_id": ev["judge_id"],
                        "total_score": ev["total_score"],
                        "mean": round(mean, 2),
                        "std": round(std, 2),
                        "z_score": round(z, 2),
                    }
                )

    logger.info(
        "Bias analysis complete: %d / %d evaluations flagged",
        len(flagged),
        len(evaluations),
    )
    return flagged
