"""Score cascades from pathway_priors.py against the actual analysis output.

Reads the per-dataset DE CSVs in analysis/results/, builds a
{feature_substring: signed_log2FC_or_logfc} table per dataset, and
checks each cascade's terminal observations:
  - Was the feature observed?
  - Did it move in the expected direction?
  - How strongly?

Each cascade gets a score, the breakdown of which observations matched,
and a summary the GUI can render.

Output: a list of cascade dicts ready to attach to dashboard_data.json
under the key "cascade_inference".

This is HYPOTHESIS-GENERATING. With n=4 we cannot prove a causal chain;
we can only flag that the observed terminal pattern is consistent with
a known upstream cause. The panel that renders these is explicit.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

import pathway_priors as priors


REPO_ROOT = Path(__file__).resolve().parent.parent
RESULTS_DIR = REPO_ROOT / "analysis" / "results"


# ---------------------------------------------------------------------------
# load all DE-style CSVs into a feature-direction map
# ---------------------------------------------------------------------------

def _load_observed_directions() -> list[dict]:
    """Return a flat list of:
        {feature: lower_string, direction: 'up'|'down', strength: float, source: csv_name}
    pulled from every CSV in analysis/results/ that has 'feature' +
    either ('direction' AND ('pooled' OR a crew column)).
    """
    out: list[dict] = []
    if not RESULTS_DIR.exists():
        return out

    for path in sorted(RESULTS_DIR.glob("*.csv")):
        try:
            df = pd.read_csv(path)
        except Exception:
            continue
        if df.empty or "feature" not in df.columns:
            continue
        dir_col = "direction" if "direction" in df.columns else None
        if dir_col is None:
            continue

        # strength column: prefer 'pooled' (DE tables); else mean across
        # C001-C004 if those columns exist.
        crew_cols = [c for c in ("C001", "C002", "C003", "C004")
                     if c in df.columns]
        if "pooled" in df.columns:
            strengths = pd.to_numeric(df["pooled"], errors="coerce")
        elif crew_cols:
            crew_numeric = df[crew_cols].apply(
                pd.to_numeric, errors="coerce")
            strengths = crew_numeric.mean(axis=1)
        else:
            strengths = pd.Series([0.0] * len(df))

        for i, row in df.iterrows():
            feat = str(row.get("feature", ""))
            d = str(row.get(dir_col, "")).strip().lower()
            if d not in ("up", "down"):
                continue
            s_val = strengths.iloc[i]
            s = float(abs(s_val)) if pd.notna(s_val) else 0.0
            out.append({
                "feature":   feat.lower(),
                "direction": d,
                "strength":  s,
                "source":    path.name,
            })
    return out


# ---------------------------------------------------------------------------
# match cascades to observations
# ---------------------------------------------------------------------------

def _match_terminal(term: dict,
                    observations: list[dict]) -> dict | None:
    """Return the best-matching observation for a single terminal node, or
    None if no observation contained the feature substring in a relevant
    source CSV. Best = highest absolute strength.
    """
    needle = term["feature"].lower()
    src_substr = term.get("source_csv_substr", "").lower()
    expected_dir = term["direction"]
    candidates = []
    for obs in observations:
        if needle not in obs["feature"]:
            continue
        if src_substr and src_substr not in obs["source"].lower():
            continue
        candidates.append(obs)
    if not candidates:
        return None
    best = max(candidates, key=lambda o: o["strength"])
    return {
        "expected":  expected_dir,
        "observed":  best["direction"],
        "agreement": (best["direction"] == expected_dir) if expected_dir != "either"
                     else True,
        "strength":  round(best["strength"], 3),
        "source":    best["source"],
        "n_candidates": len(candidates),
    }


def score_cascade(cascade: dict,
                  observations: list[dict]) -> dict:
    """Run one cascade against the observation list."""
    terminal_results = []
    score = 0.0
    max_possible = 0.0
    for term in cascade["terminal_observations"]:
        m = _match_terminal(term, observations)
        max_possible += term["weight"]
        if m is None:
            terminal_results.append({
                "feature":  term["feature"],
                "expected": term["direction"],
                "observed": None,
                "agreement": None,
                "strength": 0.0,
                "weight":   term["weight"],
                "source":   None,
            })
            continue
        # boost score by both the cascade's weight on this term and the
        # observed strength (clipped to [0.5, 2] so a single mega-strong
        # match doesn't dominate)
        boost = float(np.clip(0.5 + 0.5 * m["strength"], 0.5, 2.0))
        if m["agreement"]:
            score += term["weight"] * boost
        else:
            score -= term["weight"] * 0.4   # disagreement is a soft penalty
        terminal_results.append({
            "feature":   term["feature"],
            "expected":  term["direction"],
            "observed":  m["observed"],
            "agreement": m["agreement"],
            "strength":  m["strength"],
            "weight":    term["weight"],
            "source":    m["source"],
        })

    n_matched = sum(1 for r in terminal_results
                    if r.get("agreement") is True)
    n_disagreed = sum(1 for r in terminal_results
                      if r.get("agreement") is False)
    n_missing = sum(1 for r in terminal_results
                    if r.get("agreement") is None)

    return {
        "id":        cascade["id"],
        "name":      cascade["name"],
        "stressor":  cascade["stressor"],
        "root_cause": cascade["root_cause"],
        "mechanism": cascade["mechanism"],
        "intermediate_nodes": cascade["intermediate_nodes"],
        "evidence":  cascade["evidence"],
        "confidence": cascade["confidence"],
        "score":     round(float(score), 3),
        "max_possible": round(float(max_possible), 3),
        "score_ratio": round(float(score / max_possible), 3)
                       if max_possible > 0 else 0.0,
        "n_matched":   int(n_matched),
        "n_disagreed": int(n_disagreed),
        "n_missing":   int(n_missing),
        "terminal_results": terminal_results,
    }


def run() -> dict:
    """Top-level entrypoint. Load observations, score every cascade,
    return the structured object that goes into dashboard_data.json."""
    observations = _load_observed_directions()
    scored = [score_cascade(c, observations) for c in priors.list_cascades()]
    scored.sort(key=lambda r: r["score_ratio"], reverse=True)
    return {
        "method":       (
            "Each cascade in pathway_priors.py declares a set of terminal "
            "observable features and an expected direction. We scan all "
            "DE-style CSVs in analysis/results/, look up each terminal "
            "feature, and score cascades by the weighted sum of "
            "directional agreements (minus a soft penalty for "
            "disagreements). Cascades are ranked by score_ratio = "
            "score / sum_of_weights."
        ),
        "n_observations":  len(observations),
        "cascades":        scored,
        "honesty_note":    (
            "These are HYPOTHESIS-GENERATING. n = 4 cannot prove a "
            "causal chain; we are flagging that the observed terminal "
            "pattern is consistent with a known upstream cause. The "
            "actual root-cause attribution is supported by the cited "
            "literature, not by this dataset."
        ),
    }


if __name__ == "__main__":
    import json
    print(json.dumps(run(), indent=2)[:6000])
