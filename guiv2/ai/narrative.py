"""Per-astronaut narrative generator.

Builds a small JSON slice for one astronaut, asks Claude to write a
2-paragraph factual summary using prompts.NARRATIVE_*, and verifies
that every numeric claim in the response appears in the source JSON.

Caches the generated narrative to disk keyed by (crew_id, json_hash)
so judges can reload the page without burning tokens.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from . import client, prompts, verify


CACHE_DIR = Path(__file__).resolve().parent / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)


def _slice_for(crew_id: str, dashboard: dict) -> dict:
    """Pull just the data the LLM needs to talk about one astronaut."""
    out = {
        "crew_id":           crew_id,
        "metadata":          dashboard.get("metadata", {}),
        "axes":              [],
        "multi_system_deviation": None,
        "honesty_notes":     None,   # filled by the caller from manifest
    }
    for ax in dashboard.get("axes", []):
        traj = ax.get("trajectories", {}).get(crew_id)
        if traj is None:
            continue
        out["axes"].append({
            "id":                ax.get("id"),
            "label":             ax.get("label"),
            "is_mock":           ax.get("is_mock", False),
            "is_cohort_level":   ax.get("is_cohort_level", False),
            "datasets_used":     ax.get("datasets_used", []),
            "in_flight_observable": ax.get("in_flight_observable"),
            "trajectory":        traj,
            "within_cohort_comparison": ax.get("within_cohort_comparison"),
            "prior_cohort_overlay":     ax.get("prior_cohort_overlay"),
            "actionable_line":          ax.get("actionable_line"),
        })
    msd = dashboard.get("multi_system_deviation")
    if msd and msd.get("per_astronaut", {}).get(crew_id):
        out["multi_system_deviation"] = {
            "axis_order": msd.get("axis_order"),
            "per_astronaut_this_crew":
                msd["per_astronaut"][crew_id],
            "method": msd.get("method"),
        }
    return out


def _hash(d: dict) -> str:
    return hashlib.sha256(
        json.dumps(d, sort_keys=True).encode("utf-8")
    ).hexdigest()[:16]


def _cache_path(crew_id: str, h: str) -> Path:
    return CACHE_DIR / f"{crew_id}_{h}.md"


def generate_narrative(crew_id: str, dashboard: dict,
                       *, force: bool = False) -> dict:
    """Return:
        {"text": "...", "unverified": [...], "from_cache": bool, "model": str}
    or:
        {"error": "...", "from_cache": False}
    """
    slice_d = _slice_for(crew_id, dashboard)
    h = _hash(slice_d)
    cache_path = _cache_path(crew_id, h)

    if cache_path.exists() and not force:
        text = cache_path.read_text(encoding="utf-8")
        unverified = verify.find_unverified_numbers(text, slice_d)
        return {"text": text, "unverified": unverified,
                "from_cache": True, "model": "(cached)"}

    user = prompts.NARRATIVE_USER_TEMPLATE.format(
        crew_id=crew_id,
        json_blob=json.dumps(slice_d, indent=2)[:18000],
    )
    resp = client.generate(prompts.NARRATIVE_SYSTEM, user,
                           max_tokens=600, temperature=0.2)
    if "error" in resp:
        return {"error": resp["error"], "from_cache": False}

    text = (resp.get("text") or "").strip()
    unverified = verify.find_unverified_numbers(text, slice_d)

    # one-shot retry if the first pass invented numbers
    if unverified:
        retry_user = (user + "\n\n"
                      "REMINDER: every number in your reply must appear "
                      "VERBATIM in the JSON above. The previous response "
                      f"included these unverified numbers: "
                      f"{', '.join(unverified)}. "
                      "Rewrite the two paragraphs and cite only numbers "
                      "from the JSON.")
        retry = client.generate(prompts.NARRATIVE_SYSTEM, retry_user,
                                max_tokens=600, temperature=0.0)
        if "error" not in retry:
            retry_text = (retry.get("text") or "").strip()
            retry_unverified = verify.find_unverified_numbers(
                retry_text, slice_d)
            if len(retry_unverified) < len(unverified):
                text = retry_text
                unverified = retry_unverified

    if not unverified:
        cache_path.write_text(text, encoding="utf-8")

    return {"text": text, "unverified": unverified,
            "from_cache": False, "model": resp.get("model", "?")}
