# Data Contract: GUI ↔ Analysis

The boundary between [analysis/](analysis/) (partner's territory) and [gui/](gui/) (dashboard).

## TL;DR

- **Source of truth for data**: CSVs in [analysis/results/](analysis/results/), produced by [analysis/master.py](analysis/master.py).
- **Source of truth for what to show**: [gui/manifest.json](gui/manifest.json) — a thin editorial layer that points the GUI at specific CSVs and gives them titles, prose, and panel placement.
- **No regeneration step.** Partner edits a CSV → user reloads Streamlit → dashboard updates.

## Why a manifest, not one big JSON

The partner's pipeline naturally produces one CSV per (dataset, table, body_site, phase). Forcing it through a single `dashboard_data.json` would mean a regeneration script that has to be re-run every time analysis changes — that script is the bug surface we want to avoid in a 72-hour build.

A manifest decouples *what's shown* from *what was computed*. The user (GUI side) controls the manifest; the partner (analysis side) controls the CSVs. They almost never edit each other's files.

## CSV shapes (read from disk, not redefined)

Three flavors, already produced by [analysis/master.py](analysis/master.py):

### 1. Per-subject longitudinal

```
feature,direction,phase_compared,C001,C002,C003,C004
1002691,up,during_vs_pre,20.6,23.7,20.7,19.0
```

- One row per feature that passed the all-4-same-direction concordance filter.
- `direction` ∈ {`up`, `down`}.
- `phase_compared` ∈ {`during_vs_pre`, `post_vs_pre`}.
- `C001..C004` columns are per-subject log2FC.

Files: `OSD-572_*`, `OSD-575_*`, `OSD-630_*`, `OSD-656_*`, `OSD-569_rna_blood_*`, `OSD-569_m6A_*`, `OSD-569_cbc_*`, `OSD-570_vdj_*`.

### 2. Pooled DE

```
feature,direction,phase_compared,pooled
CD58,up,post_vs_pre_pooled,3.34
```

- Group-level test only (the underlying data is already pooled, no per-subject test possible).
- `pooled` is a single log2FC.

Files: `OSD-570_snrnaseq_*`, `OSD-570_snatacseq_*`, `OSD-571_*`, `OSD-574_spatial_*`.

### 3. Capsule detected (OSD-573 only)

```
feature
100
1000566
```

- Just a presence list. No effect size — these are taxa/genes detected on capsule surfaces during flight.

### 4. Master roll-up (computed across all three flavors)

[analysis/results/MASTER_significant_features.csv](analysis/results/MASTER_significant_features.csv):

```
dataset,table,body_site,phase,feature,direction,mode
OSD-572,kegg,ARM,during_vs_pre,K00001,up,all_four_subjects
```

Used for the cohort-summary view ("how many features moved per dataset/site/phase").

[analysis/results/MASTER_summary.json](analysis/results/MASTER_summary.json) holds the same information aggregated to counts per (dataset, table, body_site, phase). Useful for the overview tile at the top of the dashboard.

## Manifest schema (`gui/manifest.json`)

The manifest is what the user (GUI side) edits to add/remove/reorder views. Adding a new view = one entry. No code change.

```json
{
  "metadata": {
    "mission": "Inspiration4",
    "crew": [
      {"id": "C001", "name": "Jared Isaacman",    "role": "Mission Commander"},
      {"id": "C002", "name": "Hayley Arceneaux",  "role": "Medical Officer"},
      {"id": "C003", "name": "Sian Proctor",      "role": "Pilot"},
      {"id": "C004", "name": "Chris Sembroski",   "role": "Mission Specialist"}
    ],
    "filter_criteria": {
      "per_subject_log2fc_threshold": 1.0,
      "per_subject_concordance": "all 4 crew, same direction",
      "pooled_DE_padj_threshold": 0.05,
      "pooled_DE_log2fc_threshold": 1.0
    },
    "honesty_notes": [
      "Strict 4-of-4 concordance + |log2FC| ≥ 1 found no hits in OSD-575 (serum cytokines), OSD-656 (urine inflammation), OSD-630 (stool), OSD-569 (CBC clinical labs), OSD-570 (snATAC-seq, V(D)J). This is a high-bar filter; absence here likely reflects inter-individual variability, not absence of biological effect."
    ]
  },
  "panels": [
    {
      "id": "microbiome",
      "label": "Microbiome shifts: capsule → crew → barrier",
      "intro_md": "Short prose for the panel header.",
      "views": [
        {
          "id": "osd572-axillary-during",
          "type": "per_subject_table",
          "title": "Axillary skin (during vs pre): top features",
          "csv": "analysis/results/OSD-572_taxonomy_ARM_during_vs_pre.csv",
          "top_n": 25,
          "sort_by": "magnitude"
        },
        {
          "id": "flow-diagram",
          "type": "flow_diagram",
          "title": "Capsule → crew → barrier",
          "sources": {
            "capsule": "analysis/results/OSD-573_taxonomy_detected_during_flight.csv",
            "crew_swabs": "analysis/results/OSD-572_taxonomy_ARM_during_vs_pre.csv",
            "barrier": "analysis/results/OSD-574_spatial_pooled_DE.csv"
          }
        }
      ]
    },
    {
      "id": "systemic",
      "label": "Systemic molecular changes",
      "intro_md": "Short prose for the panel header.",
      "views": [
        {
          "id": "osd569-rna",
          "type": "per_subject_table",
          "title": "Whole blood RNA-seq (post vs pre)",
          "csv": "analysis/results/OSD-569_rna_blood_post_vs_pre.csv",
          "top_n": 25,
          "sort_by": "magnitude"
        },
        {
          "id": "osd571-metabolomics",
          "type": "pooled_table",
          "title": "Plasma metabolomics (post vs pre, pooled)",
          "csv": "analysis/results/OSD-571_metabolomics_pooled_DE.csv",
          "top_n": 25
        }
      ]
    }
  ]
}
```

### Field types

| Field | Type | Required | Notes |
|---|---|---|---|
| `metadata.mission` | string | yes | Display only. |
| `metadata.crew[].id` | string | yes | Must match column headers in per-subject CSVs (`C001..C004`). |
| `metadata.crew[].name` | string | yes | Display name for the dashboard. |
| `metadata.crew[].role` | string | yes | Display role. |
| `metadata.filter_criteria` | object | yes | Mirrors `analysis/results/MASTER_summary.json["criteria"]`. |
| `metadata.honesty_notes` | string[] | yes | Surfaced at the top of the dashboard. |
| `panels[].id` | string | yes | Stable identifier; URL-safe. |
| `panels[].label` | string | yes | Tab/header text. |
| `panels[].intro_md` | string | optional | Markdown rendered above the panel's views. |
| `panels[].views[].id` | string | yes | Stable identifier. |
| `panels[].views[].type` | enum | yes | `per_subject_table` \| `pooled_table` \| `flow_diagram`. |
| `panels[].views[].title` | string | yes | Header above the view. |
| `panels[].views[].csv` | path | required for table types | Path relative to repo root. |
| `panels[].views[].top_n` | int | optional | Default: 25. |
| `panels[].views[].sort_by` | enum | optional | `magnitude` (default) \| `feature` \| `direction`. |
| `panels[].views[].sources` | object | required for `flow_diagram` | Maps role → CSV path. |

### View types and how the GUI renders them

| `type` | Renders as |
|---|---|
| `per_subject_table` | Heatmap of top N features × {C001..C004}, colored by log2FC, with `direction` badge. |
| `pooled_table` | Sorted bar chart of top N features by pooled log2FC, up/down colored. |
| `flow_diagram` | Three-column Sankey-style: capsule taxa → crew body sites → barrier-gene response. |

Adding a new view type = one renderer in [gui/components/](gui/components/) plus one new value in the `type` enum here.

## What the GUI never does

- **Recompute statistics.** Filtering, thresholding, and concordance logic all live in `analysis/`. The GUI shows what the partner already computed.
- **Modify CSVs.** Read-only. If a CSV is wrong, the partner fixes it.
- **Hard-code crew names, dataset IDs, or panel labels in component code.** Everything driven by the manifest.

## Versioning

When the partner changes the shape of a CSV, the GUI breaks loudly (Pandas error on column mismatch) — that's the intended fail-fast. We don't add a schema-version field; the contract is the column names.
