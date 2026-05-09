"""Natural-language Q&A on the dashboard.

Sends a slimmed-down dashboard JSON (the heavy long-arrays-of-numbers
trajectories trimmed for clarity) to Claude with the user's question.
Verifies numeric grounding against the slim JSON.
"""

from __future__ import annotations

import json

from . import client, prompts, verify


def _slim_dashboard(dashboard: dict) -> dict:
    """Trim the dashboard JSON for Q&A use: keep all the structured
    summary fields, drop the very long arrays where summaries already
    exist (e.g., feature_panel for axes — judges won't ask about every
    analyte by name)."""
    out = {
        "metadata":   dashboard.get("metadata", {}),
        "astronauts": dashboard.get("astronauts", []),
        "axes":       [],
        "multi_system_deviation":
            dashboard.get("multi_system_deviation"),
        "flow_diagram":
            (dashboard.get("flow_diagram") or {}).get("cohort_level_facts"),
    }
    for ax in dashboard.get("axes", []):
        out["axes"].append({
            "id":                ax.get("id"),
            "label":             ax.get("label"),
            "description":       ax.get("description"),
            "is_mock":           ax.get("is_mock", False),
            "is_cohort_level":   ax.get("is_cohort_level", False),
            "datasets_used":     ax.get("datasets_used"),
            "in_flight_observable": ax.get("in_flight_observable"),
            "trajectories":      ax.get("trajectories"),
            "within_cohort_comparison":
                ax.get("within_cohort_comparison"),
            "prior_cohort_overlay": ax.get("prior_cohort_overlay"),
            "actionable_line": ax.get("actionable_line"),
            # feature_panel and scoring_method dropped — too long
        })
    return out


def answer(question: str, dashboard: dict) -> dict:
    """Return:
        {"text": "...", "unverified": [...], "model": str}
    or
        {"error": "..."}
    """
    if not question.strip():
        return {"error": "empty_question"}
    slim = _slim_dashboard(dashboard)
    user = prompts.QA_USER_TEMPLATE.format(
        question=question.strip(),
        json_blob=json.dumps(slim, indent=2)[:35000],
    )
    resp = client.generate(prompts.QA_SYSTEM, user,
                           max_tokens=400, temperature=0.0)
    if "error" in resp:
        return {"error": resp["error"]}

    text = (resp.get("text") or "").strip()
    unverified = verify.find_unverified_numbers(text, slim)
    return {"text": text, "unverified": unverified,
            "model": resp.get("model", "?")}
