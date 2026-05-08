# ClaudePlan.md

> **Briefing for Claude Code.** This document is the plan handed off from Claude (chat, web) to Claude Code (CLI, in VS Code). Read it fully before writing any code, then verify it against the actual state of the repo and surface any conflicts to the user before proceeding.

## Project context

This is the **Microbiome–Immune–Barrier Axis Integrator**, our submission for the **Torchlight Summit Biosovereignty Hackathon** (May 6–9 2026, UATX, Austin TX). We are pursuing **Track 2 — Individualized Risk Profile**.

The canonical project description is in `README.md`. The short version: build a per-astronaut Track 2 dashboard for the Inspiration4 crew (n = 4) that scores them on four axes — immune regulation, inflammation & oxidative stress, DNA damage response, mitochondrial function — using nine OSDR datasets, with a microbiome → barrier → immune signature visual integrated into the immune and inflammation panels.

Submission is the GitHub repo, evaluated by judges from aerospace medicine, space omics, and military health. **There is no live presentation. Judges read the repo.**

Win condition (from the kickoff deck): "Honest analysis on a small, real, messy dataset that helps a future explorer make a better decision about their own body."

## Role boundaries — read carefully

Two-person team:

- **The user (me)** — building the GUI / dashboard. Owns `gui/`, `data/`, and is the primary editor for shared root-level files (`README.md`, `requirements.txt`, this file).
- **The user's partner** — building the analysis pipeline. **`analysis/` is their territory. Do not modify any file inside `analysis/` without explicit instruction from the user.** This is a hard rule.

The contract between the two halves of the project is a single output file produced by `analysis/` and consumed by `gui/`. See **Data contract** below — that section is the most important one in this document.

## Tech stack — proposed

**Recommendation: Streamlit.** Rationale:

- Python-native, so it consumes the partner's pandas DataFrames or JSON output with zero friction.
- Built-in dashboard primitives (charts, columns, tabs, metrics) get a four-panel dashboard up in hours, not days.
- Hot-reload makes iteration cheap — the "very editable" requirement is a Streamlit native feature.
- Deploys free to Streamlit Community Cloud, so judges can interact with the dashboard directly from a link in `README.md`, not just read code.
- Plotly works cleanly inside Streamlit for the trajectory charts. The flow diagram can use Plotly Sankey or a custom SVG component.

Alternatives considered: React (too much overhead for 72 hours unless the user is already fluent), Plotly Dash (more boilerplate for the same outcome), Jupyter widgets (less polished, harder for judges to interact with).

**First action for Claude Code:** Confirm Streamlit with the user before scaffolding. If they want a different stack, this whole plan adapts but the architecture (separation of concerns, data contract, editability principles) stays.

## Proposed file structure

```
/
├── analysis/                          # PARTNER'S TERRITORY — DO NOT TOUCH
│   └── ...
├── gui/                               # USER'S TERRITORY
│   ├── app.py                         # Streamlit entry point
│   ├── config.py                      # Panel definitions, colors, layout knobs
│   ├── data.py                        # Loads dashboard_data.json
│   ├── components/
│   │   ├── __init__.py
│   │   ├── panel.py                   # Reusable axis panel (used 4×)
│   │   ├── trajectory_chart.py        # Score-over-time with CI bands
│   │   ├── comparison.py              # Within-cohort & prior-cohort views
│   │   └── flow_diagram.py            # Microbiome → barrier → immune visual
│   └── assets/
│       └── styles.css                 # Custom Streamlit styling
├── data/
│   ├── dashboard_data.json            # Real output from analysis/ (gitignored or symlinked)
│   └── dashboard_data.mock.json       # Mock data, committed, used until real data lands
├── README.md                          # Project proposal (already written)
├── ClaudePlan.md                      # This file
├── SCHEMA.md                          # Data contract spec — Claude Code writes this
└── requirements.txt
```

If anything in the existing repo conflicts with this layout, surface it to the user before reorganizing. Don't silently move files.

## Data contract — the most important section

The single file at `data/dashboard_data.json` is the boundary between `analysis/` and `gui/`. Get this right, document it in `SCHEMA.md`, and:

- The partner can iterate `analysis/` freely.
- The user can iterate `gui/` freely.
- Integration becomes "drop the new file in `data/`" instead of a rewrite at hour 65.

Proposed schema:

```json
{
  "metadata": {
    "mission": "Inspiration4",
    "generated_at": "2026-05-08T14:00:00Z",
    "n_astronauts": 4,
    "timepoints": ["L-92", "L-44", "L-3", "FD1", "FD2", "FD3", "R+1", "R+45", "R+82", "R+194"],
    "in_flight_timepoints": ["FD1", "FD2", "FD3"]
  },
  "astronauts": [
    {"id": "I4_01", "name": "Jared Isaacman",  "role": "Mission Commander"},
    {"id": "I4_02", "name": "Hayley Arceneaux","role": "Medical Officer"},
    {"id": "I4_03", "name": "Sian Proctor",    "role": "Pilot"},
    {"id": "I4_04", "name": "Chris Sembroski", "role": "Mission Specialist"}
  ],
  "axes": [
    {
      "id": "immune",
      "label": "Immune Regulation",
      "description": "Short prose for the panel header.",
      "scoring_method": "Markdown describing the scoring function.",
      "datasets_used": ["OSD-570", "OSD-575"],
      "in_flight_observable": true,
      "ground_only_note": null,
      "actionable_line": "What an astronaut would do with this score.",
      "trajectories": {
        "I4_01": {
          "scores":   [0.0, -0.1, 0.0, 1.2, 1.5, 1.6, 0.8, 0.3, 0.1, 0.0],
          "ci_lower": [...],
          "ci_upper": [...],
          "observable_mask": [true, true, true, true, true, true, true, true, true, true]
        }
      },
      "within_cohort_comparison": { "summary": "...", "data": {} },
      "prior_cohort_comparison":  { "summary": "...", "source": "Tierney et al. 2024", "data": {} }
    }
  ],
  "flow_diagram": {
    "per_astronaut": {
      "I4_01": {
        "nodes": [
          {"id": "capsule_taxon_X", "layer": "environment", "label": "...", "value": 0.4}
        ],
        "edges": [
          {"source": "capsule_taxon_X", "target": "skin_site_Y", "value": 0.3, "evidence": "temporal"}
        ]
      }
    }
  }
}
```

**Action for Claude Code:**

1. Write `SCHEMA.md` formalizing the schema above with field types and required/optional flags.
2. Create `data/dashboard_data.mock.json` populated with plausible dummy values matching the schema. The GUI gets built against the mock first — the user is **not** blocked on the partner's analysis pipeline.
3. Once the partner produces a real `dashboard_data.json`, the only change is the file the GUI reads. No GUI code edits.

## The four panels

Each axis renders in an identical panel component, populated from its slice of the JSON. Specs from `README.md`:

1. **Immune Regulation.** Composite z-score of PBMC immune-cell proportion deviations (OSD-570) and Th1/Th2/Treg-aligned serum cytokine deviations (OSD-575).
2. **Inflammation & Oxidative Stress.** Composite of acute-phase cytokines (IL-6, TNF, CRP from OSD-575), urine inflammation markers (OSD-656), and oxidative-stress metabolites (OSD-571).
3. **DNA Damage Response.** Mean z-score of canonical DDR gene signature from OSD-569.
4. **Mitochondrial Function.** Mean z-score of TCA-cycle intermediates and acylcarnitines from OSD-571.

Each panel contains: trajectory chart with CI bands across the ten timepoints, within-cohort comparison, prior-cohort comparison, scoring methods note, in-flight visibility indicator, actionable line.

The signature visual (microbiome → barrier → immune flow diagram) appears in the immune and inflammation panels — it is *not* a fifth panel.

## "Very editable" — what this means concretely

This is the user's stated top requirement for the GUI. Operationalized:

- **All visual config in `gui/config.py`.** Panel order, colors, axis labels, descriptions, CI band styling, font choices. Edit one file, the whole dashboard updates.
- **No hard-coded astronaut names or axis names in components.** Everything reads from the JSON.
- **Adding a new axis = one entry in the JSON's `axes` array.** The panel auto-renders. No GUI code change required.
- **Component code is small and well-named.** A panel component should be readable in under 100 lines.
- **No clever indirection.** A custom-styled Streamlit element should be findable by ctrl-F on the visible text.
- **One source of truth per concern.** Colors live in config, not scattered across components. Layout lives in config, not scattered across components.

## Build order — GUI-side, 72 hours

Mirroring the deck's arc, scoped to the user's half of the project.

**Hours 0–6 — Orient.** Stack confirmed. `gui/` skeleton scaffolded. `requirements.txt`, `data/dashboard_data.mock.json`, `SCHEMA.md` written. One panel rendering from mock data locally.

**Hours 6–24 — Foundation.** All four panel slots laid out (mocked). Trajectory chart component working with CI bands. Comparison component working. `config.py` driving layout. Deployed to Streamlit Community Cloud so the partner can see GUI progress without cloning.

**Hours 24–48 — Build.** Flow diagram component. Methods note rendering (Markdown). Actionable line. In-flight visibility indicator. Real-data swap-in once partner ships first version of `dashboard_data.json`.

**Hours 48–66 — Polish.** Styling pass. Laptop / mobile render check. Edge cases (missing data, partial trajectories, malformed JSON). Re-deploy. Try to break the GUI with bad inputs and add graceful failure.

**Hours 66–72 — Ship.** `README.md` updated with the deployed URL. Final commit tagged. Fresh clone test — verify the app runs cleanly from a new checkout.

## First actions for Claude Code, in order

1. **Read the existing repo state.** `ls -la`, read `README.md`, see what's already in the repo. If anything conflicts with this plan, surface it to the user before writing code.
2. **Confirm Streamlit with the user.** If yes, proceed. If they want something else, ask which and adapt.
3. **Write `SCHEMA.md`** formalizing the data contract.
4. **Create `data/dashboard_data.mock.json`** with plausible dummy values matching the schema.
5. **Scaffold `gui/`** — `app.py`, `config.py`, `data.py`, `components/`, `assets/`, `requirements.txt` updated.
6. **Render one panel from mock data end-to-end.** Verify it works before building all four.
7. **Commit early, commit often.** The deck explicitly rewards visible GitHub history (≥ 2 commits during the build window).

## Open questions to surface to the user

- Streamlit confirmed, or different stack?
- Is the partner's `analysis/` already producing any output file we should align the schema to, or are we defining the contract from scratch?
- Should the deployed Streamlit URL be linked publicly from `README.md` immediately, or kept private until submission?
- Color palette / branding preference, or pick something appropriate? (Default suggestion: deep navy + ice blue + a sharp accent — clean, mission-aesthetic, not the AI-default cream.)
- Has the partner seen this plan? They should at least see the schema section before they start producing analysis outputs.

## References

- `README.md` — the project proposal. Source of truth on scope, scoring methodology, and deliverable definition. Defer to it for any analysis-side detail not repeated here.
- The hackathon kickoff deck (`Torchlight_Biosovereignty_Hackathon_Kickoff.pptx`) — deliverable spec, judging criteria, win condition.

---

*This plan was written by Claude (web chat) on 2026-05-08 based on the project README and the user's stated role split. It's a starting point, not a contract — adapt it as the build reveals what actually works.*
