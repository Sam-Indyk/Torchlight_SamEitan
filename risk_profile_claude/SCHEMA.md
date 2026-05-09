# dashboard_data.json — schema

This is the data contract between [risk_profile_claude/](.) and the GUI MVP.
It extends the schema sketched in
[CLAUDEPLAN.md](../CLAUDEPLAN.md#data-contract--the-most-important-section)
with the population-anchored fields needed to render the trajectory and
comparison views without re-deriving them in the GUI.

The GUI partner can build against [mock_dashboard_data.json](mock_dashboard_data.json)
in this folder. When the real `data/dashboard_data.json` lands, no GUI
code changes are required.

## Top-level structure

```jsonc
{
  "metadata": { ... },
  "astronauts": [ ... ],
  "axes": [ ... ],
  "flow_diagram": { ... }
}
```

## metadata

```jsonc
{
  "mission": "Inspiration4",
  "generated_at": "2026-05-08T14:00:00Z",     // ISO-8601 UTC
  "generator": "risk_profile_claude/build_risk_profile.py v0.1",
  "n_astronauts": 4,
  "timepoints": ["L-92","L-44","L-3","FD1","FD2","FD3","R+1","R+45","R+82","R+194"],
  "in_flight_timepoints": ["FD1","FD2","FD3"],
  "preflight_timepoints":  ["L-92","L-44","L-3"],
  "postflight_timepoints": ["R+1","R+45","R+82","R+194"],
  "scoring_conventions": {
    "own_baseline_z":   "(value - mean(self_preflight)) / sd(self_preflight)",
    "population_z":     "(value - range_mid) / (range_width / 3.92)",
    "mahalanobis":      "sqrt((x - mu_pre)^T * Σ^-1 * (x - mu_pre)) over a panel",
    "sign_convention":  "positive = elevated relative to baseline / population midpoint"
  }
}
```

## astronauts

A short list, ordered for stable iteration in the GUI:

```jsonc
[
  { "id": "C001", "display_id": "C001", "role_label": "Crew member 1" },
  { "id": "C002", "display_id": "C002", "role_label": "Crew member 2" },
  { "id": "C003", "display_id": "C003", "role_label": "Crew member 3" },
  { "id": "C004", "display_id": "C004", "role_label": "Crew member 4" }
]
```

Real names (Isaacman / Arceneaux / Proctor / Sembroski) are intentionally
*not* mapped here — OSDR pseudonymizes the crew as C001–C004 and the
de-anonymization is publicly known but not part of the dataset. If you
choose to display real names in the GUI, do that in `gui/config.py`,
not here.

## axes

Array of four objects, one per Track 2 axis, in this order:

1. `immune` — Immune Regulation
2. `inflammation` — Inflammation & Oxidative Stress
3. `ddr` — DNA Damage Response
4. `mitochondrial` — Mitochondrial Function

Per-axis shape:

```jsonc
{
  "id": "immune",
  "label": "Immune Regulation",
  "description": "Composite z-score of PBMC immune-cell proportion deviations and Th1/Th2/Treg-aligned serum cytokine deviations.",
  "scoring_method": "Markdown string. What features feed the score, how they're combined, what the uncertainty bands mean, what could break the inference.",
  "datasets_used": ["OSD-570", "OSD-575"],
  "in_flight_observable": false,            // can this panel see anything during FD1/FD2/FD3?
  "ground_only_note": "OSD-570 and OSD-575 require phlebotomy; no in-flight blood draws on Inspiration-4. In-flight slots show NaN.",
  "actionable_line":  "On a longer-duration mission, saliva-based cytokine surrogates would partially close the in-flight gap.",
  "feature_panel": [                        // the analytes that feed this axis
    { "name": "IL-6",  "source": "OSD-575_immune_eve",   "direction_meaning": "up = pro-inflammatory" },
    { "name": "TNF-α", "source": "OSD-575_immune_eve",   "direction_meaning": "up = pro-inflammatory" }
  ],
  "trajectories": {
    "C001": {
      "scores":            [0.0,  -0.1,  0.0,  null, null, null,  1.5,  0.8,  0.3,  0.0],
      "ci_lower":          [-0.3, -0.4, -0.2, null, null, null,  0.9,  0.4,  0.0, -0.2],
      "ci_upper":          [ 0.3,  0.2,  0.2, null, null, null,  2.1,  1.2,  0.6,  0.2],
      "own_baseline_z":    [ 0.0, -0.1,  0.0, null, null, null,  1.4,  0.7,  0.3,  0.0],
      "population_z":      [ 0.2,  0.1,  0.2, null, null, null,  2.4,  1.3,  0.6,  0.3],
      "mahalanobis":       [ 0.4,  0.3,  0.5, null, null, null,  3.7,  2.1,  1.0,  0.5],
      "observable_mask":   [true, true, true, false, false, false, true, true, true, true]
    },
    "C002": { ... },
    "C003": { ... },
    "C004": { ... }
  },
  "within_cohort_comparison": {
    "summary": "C002 has the largest R+1 deviation; C004 the smallest.",
    "ranking_at_R+1": [
      { "astronaut": "C002", "score": 2.1 },
      { "astronaut": "C001", "score": 1.5 },
      { "astronaut": "C003", "score": 1.0 },
      { "astronaut": "C004", "score": 0.6 }
    ]
  },
  "prior_cohort_comparison": {
    "summary": "Mean R+1 IL-6 elevation in this cohort exceeds the Tierney 2024 reported magnitude.",
    "source": "Tierney et al. 2024 (Inspiration-4 multi-omics integration)",
    "data": null
  }
}
```

### Required vs optional

| Field | Required | Notes |
|---|---|---|
| `id`, `label`, `description` | required | display strings |
| `scoring_method` | required | shown in a "Methods" expander |
| `datasets_used` | required | array of OSD IDs |
| `in_flight_observable` | required | drives the FD1/FD2/FD3 mask |
| `ground_only_note` | required if `in_flight_observable=false` | otherwise null |
| `actionable_line` | required | shown at the bottom of the panel |
| `feature_panel` | required | drives the "what's in this score" tooltip |
| `trajectories` | required | keys are astronaut IDs from `astronauts[].id` |
| `trajectories[id].scores` | required | length = `metadata.timepoints.length`. `null` for unobservable |
| `trajectories[id].ci_lower` / `ci_upper` | required | bootstrap intervals; `null` for unobservable |
| `trajectories[id].own_baseline_z` / `population_z` | optional but populated | for the secondary lines on the chart |
| `trajectories[id].mahalanobis` | optional | only set for axes where a multivariate panel is defined |
| `trajectories[id].observable_mask` | required | parallel array of booleans |
| `within_cohort_comparison` | required | summary always present, ranking optional |
| `prior_cohort_comparison` | optional | `null` when no prior available |

## flow_diagram

The signature visual described in [README.md](../README.md#deliverable). For
each astronaut, a small directed graph showing
capsule-environment → body-site microbiome shift → barrier-gene response →
downstream cytokine response.

```jsonc
{
  "per_astronaut": {
    "C001": {
      "nodes": [
        { "id": "capsule_NAP_taxa",  "layer": "environment", "label": "Capsule taxa (NAP-relevant)", "magnitude": 0.7 },
        { "id": "host_NAP",          "layer": "host_site",   "label": "Nasopharynx microbiome",       "magnitude": 0.9 },
        { "id": "barrier_FLG",       "layer": "barrier",     "label": "FLG (filaggrin) expression",   "magnitude": -0.6 },
        { "id": "cytokine_IL6",      "layer": "systemic",    "label": "IL-6",                          "magnitude": 0.8 }
      ],
      "edges": [
        { "source": "capsule_NAP_taxa", "target": "host_NAP",     "weight": 0.7, "evidence": "shared_taxa_temporal" },
        { "source": "host_NAP",         "target": "barrier_FLG",  "weight": 0.4, "evidence": "correlation_only" },
        { "source": "barrier_FLG",      "target": "cytokine_IL6", "weight": 0.5, "evidence": "correlation_only" }
      ]
    }
  },
  "evidence_legend": {
    "shared_taxa_temporal": "Taxon present pre-launch in capsule, absent on crew member preflight, present on crew during/post flight.",
    "correlation_only":     "Direction not established; reported as undirected association."
  }
}
```

`magnitude` is signed (positive = up vs. baseline, negative = down). `weight`
on edges is unsigned in [0, 1] — render thickness from this.

## Versioning

The schema is versioned via `metadata.generator`. Bump the version string
when adding required fields. The GUI should treat unknown fields as
forward-compatible (ignore them).
