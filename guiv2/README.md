# guiv2

Unified Streamlit dashboard — proposed hackathon submission.

Integrates three complementary halves of the project into one app:

| Source | Where it lands in guiv2 |
|---|---|
| Eitan's CSV-driven scaffold ([gui/](../gui/)) | Manifest pattern, per-subject heatmap, pooled bar chart, honesty banner |
| Claude's risk-profile JSON pipeline ([risk_profile_claude/](../risk_profile_claude/)) | Per-astronaut trajectory panels, 4-axis overview, real Sankey flow diagram |
| Partner's analysis output ([analysis/results/](../analysis/results/)) | Read directly, no regeneration step |

This folder is **additive** — `gui/` is left untouched so Eitan's work
remains intact and reviewable. To pick guiv2 as the submission, point the
README and any deploy config at `guiv2/app.py`.

## Layout

```
guiv2/
├── README.md
├── app.py                      # Streamlit entry point
├── config.py                   # Colors, paths, constants
├── data.py                     # CSV + JSON + manifest loading (cached)
├── manifest.json               # Editorial layer — edit to add/reorder views
├── assets/styles.css
└── components/
    ├── __init__.py             # RENDERERS registry
    ├── honesty_banner.py       # adapted from gui/
    ├── per_subject_table.py    # adapted from gui/
    ├── pooled_table.py         # adapted from gui/
    ├── risk_overview.py        # NEW — 4-axis small-multiples summary
    ├── risk_axis_panel.py      # NEW — per-axis trajectory + ranking + methods
    └── flow_diagram.py         # NEW — real Sankey from JSON (replaces placeholder)
```

## Running

```powershell
# 1. install deps (one-time)
pip install -r ../requirements.txt

# 2. make sure the risk-profile JSON exists
python ../risk_profile_claude/build_risk_profile.py

# 3. launch
streamlit run app.py
```

If the JSON is missing, the risk-profile panels show a clear error pointing
at the build script. The molecular-perturbation panels work as long as
[../analysis/results/](../analysis/results/) is populated.

## Tab structure

1. **Individualized Risk Profile** (Track 2 deliverable)
   - 4-axis overview with R+1 deviation ranking table
   - One drill-down panel per axis (Immune, Inflammation, DDR, Mitochondrial)
   - Each panel: trajectory chart with selectable score channel + 95% CI band,
     within-cohort ranking, prior-cohort comparison, scoring method, raw data
2. **Capsule → Barrier → Systemic Flow**
   - Per-astronaut Sankey with edge-evidence color coding
3. **Molecular Perturbations · Microbiome**
   - OSD-572 per-subject heatmaps + OSD-574 pooled bar chart
4. **Molecular Perturbations · Systemic**
   - OSD-569 RNA-seq heatmap + OSD-570/571 pooled bar charts

## How to extend

- **Add a new view to an existing tab** — append an entry to `panels[].views`
  in [manifest.json](manifest.json). No code change.
- **Add a new tab** — append to `panels[]`.
- **Add a new view *type*** — write `components/<name>.py` exposing
  `render_<name>(view, manifest)`, register it in
  [components/__init__.py](components/__init__.py), reference
  `"type": "<name>"` from the manifest.

## Data contract

Two parallel contracts:

- **CSVs** in [`../analysis/results/`](../analysis/results/) — produced by
  partner's pipeline. Schema is the column names; breaks loudly on mismatch.
- **JSON** at [`../data/dashboard_data.json`](../data/dashboard_data.json) —
  produced by [`../risk_profile_claude/build_risk_profile.py`](../risk_profile_claude/build_risk_profile.py).
  Schema documented in
  [`../risk_profile_claude/SCHEMA.md`](../risk_profile_claude/SCHEMA.md).

The GUI never recomputes statistics. If a number looks wrong, fix it in
the upstream pipeline, not here.

## Why two GUIs in the repo?

`gui/` is Eitan's first scaffold — small, focused, CSV-only. Useful as a
reference and a dev-loop sandbox.

`guiv2/` integrates the risk-profile work and is intended as the
submission. If we choose to ship `guiv2/`, `gui/` can be removed in a
later cleanup commit; we are not removing it now because it's still
useful as a comparison and Eitan may want to iterate on it.
