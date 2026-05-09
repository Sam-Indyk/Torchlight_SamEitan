# Microbiome–Immune–Barrier Axis Integrator

**Track 2 — Individualized Risk Profile.** Inspiration4 (n = 4), Torchlight Summit Biosovereignty Hackathon, May 6–9 2026.

> **For judges:** the dashboard is the deliverable. Run it in three commands (next section), then open `http://localhost:8501/` and follow the tab order — Mission Overview → Individualized Risk Profile → AI · grounded in the data → Capsule → Barrier → Systemic Flow → Molecular Perturbations → Data Sources & Provenance.

---

## Quick start — run the dashboard

**Prerequisites:** Python 3.10 or newer with `pip` available.

```bash
# 1. Clone and enter the repo
git clone https://github.com/Sam-Indyk/Torchlight_SamEitan.git
cd Torchlight_SamEitan

# 2. Install dependencies
pip install -r requirements.txt

# 3. (Optional) Set the Anthropic API key for the AI tab
#    Without this, the dashboard runs unchanged but the AI tab will
#    prompt you to paste a key into the GUI (session-only, never written
#    to disk). A free-tier key works.
#
#    Mac/Linux:  export ANTHROPIC_API_KEY=sk-ant-...
#    Windows:    $env:ANTHROPIC_API_KEY = "sk-ant-..."

# 4. Launch the dashboard
streamlit run guiv2/app.py
```

Streamlit prints the URL when it starts — usually **http://localhost:8501/**.
It also auto-opens the browser. To stop the server, press `Ctrl+C` in the terminal.

> **Heads up:** `python guiv2/app.py` will *not* work — Streamlit apps must be launched through the `streamlit` CLI. If `streamlit` isn't on your PATH, use `python -m streamlit run guiv2/app.py`.

### What if I just want to look at the data?

The risk-profile JSON the dashboard reads is checked into the repo at
[`data/dashboard_data.json`](data/dashboard_data.json). It's the schema-driven
single source of truth for the per-astronaut axes and is fully documented in
[`risk_profile_claude/SCHEMA.md`](risk_profile_claude/SCHEMA.md).

To regenerate it from scratch (reads the cached OSDR data via `analysis/`):

```bash
python risk_profile_claude/build_risk_profile.py
```

---

## Tour the dashboard — what you'll see in each tab

1. **Mission Overview** — Hero banner, anonymous crew cards (C001–C004), at-a-glance stats (n=4, datasets used, 67k concordant features, 96% capsule→NAP overlap), mission timeline strip, and a body-sample map showing where every OSDR sample was collected.
2. **Individualized Risk Profile** — *the Track 2 deliverable.*
   - Four-axis overview with a per-axis × per-astronaut R+1 ranking and a half-life recovery matrix.
   - **Multi-system Mahalanobis** — the single risk number per astronaut combining all four axes.
   - **Per-astronaut report cards** — rule-based clinical-style summaries.
   - One drill-down per axis (Immune, Inflammation, DDR, Mitochondrial), each with full trajectory, 95% bootstrap CI, recovery-rate fits, prior-cohort overlay, and a methods expander.
3. **AI · grounded in the data** — *the $100 AI-prize submission.*
   - **Ask the dashboard** — natural-language Q&A grounded in the precomputed JSON, with a numeric verifier.
   - **Per-astronaut AI narratives** — Claude-written 2-paragraph factual summaries, every number checked against source.
   - See [`AI_USES.md`](AI_USES.md) for the disclosure and [`AI_PLAN.md`](AI_PLAN.md) for the design rationale.
4. **Capsule → Barrier → Systemic Flow** — Per-astronaut Sankey: capsule taxa → host body sites → skin barrier → systemic cytokines, with computed edge weights.
5. **Molecular Perturbations · Microbiome / · Systemic** — Eitan's CSV-driven heatmaps and bar charts of the underlying differential-expression results from `analysis/results/`.
6. **Data Sources & Provenance** — Card grid documenting every internal OSDR dataset and every external literature reference (population SDs, prior-cohort overlays). The "what's real, what's calibrated" page.

Every chart in the dashboard has an **ⓘ About this chart** expander beneath it that documents what the chart is showing, the units of each axis, and why we chose that chart type.

---

## Architecture in one diagram

```
   OSDR endpoints  ──►  analysis/master.py  ──►  analysis/.cache/  +  analysis/results/*.csv
                                                          │
                          ┌───────────────────────────────┴──────────────────────────┐
                          ▼                                                          ▼
            risk_profile_claude/build_risk_profile.py                       guiv2/components/
            (own-baseline z, population z, Mahalanobis,                     per_subject_table.py
             recovery τ, multi-system Mahalanobis,                          pooled_table.py
             real microbiome→barrier flow)                                  (read CSVs directly)
                          │
                          ▼
              data/dashboard_data.json
              (schema in risk_profile_claude/SCHEMA.md)
                          │
                          ▼
           guiv2/components/  +  guiv2/ai/  ──►  Streamlit dashboard at localhost:8501
```

Two separate folders, two contracts:

- `gui/` (Eitan's original scaffold) reads CSVs from `analysis/results/` directly.
- `guiv2/` (the integrated submission) reads both the CSVs AND `data/dashboard_data.json`, plus runs the Anthropic-API-backed AI features.

To pick `guiv2/` as the submission, point the deploy at `guiv2/app.py`. `gui/` remains in the repo as Eitan's reference scaffold.

---

## Repo map

| Path | What's there |
|---|---|
| [`guiv2/`](guiv2/) | The integrated Streamlit dashboard — what judges run |
| [`risk_profile_claude/`](risk_profile_claude/) | The scoring pipeline that produces `data/dashboard_data.json` |
| [`analysis/`](analysis/) | OSDR data ingestion + per-dataset DE pipeline (Eitan's territory) |
| [`gui/`](gui/) | Eitan's first manifest-driven Streamlit scaffold |
| [`data/dashboard_data.json`](data/dashboard_data.json) | The single contract between scoring and rendering |
| [`AI_USES.md`](AI_USES.md) | Judge-facing AI disclosure (runtime + dev-time) |
| [`AI_PLAN.md`](AI_PLAN.md) | Design rationale for the AI features |
| [`FINDINGS.md`](FINDINGS.md) | Plain-language summary of what the analysis pipeline found |
| [`CLAUDEPLAN.md`](CLAUDEPLAN.md) | The kickoff plan handed from Claude (web) to Claude Code |

---

## Problem statement

Tierney et al. (2024) and Park et al. (2024) both identify the same open question in their Discussions: spaceflight shifts the skin, oral, and gut microbiome and disrupts the skin barrier, but the links between (a) the Dragon capsule's environmental microbiome, (b) what colonizes the crew, (c) skin-barrier breakdown, and (d) systemic immune and inflammatory response have not been integrated into a single cross-omic picture for any individual astronaut. OSD-630 (stool metagenomics) in particular remains under-analyzed in the published literature.

We use this gap to build the deliverable Track 2 actually asks for: a per-astronaut risk profile with a transparent scoring method, dashboard-shaped, written for the crew member it's about.

## The four Track 2 axes

Track 2 names four axes: immune regulation, inflammation & oxidative stress, DNA damage response, mitochondrial function. We commit to all four, but at honestly calibrated depth:

- **Primary (cross-omic integration).** Immune regulation and inflammation. Our microbiome–barrier–immune integration adds new signal here that single-modality analysis can't.
- **Secondary (single-modality readout).** DNA damage response from whole-blood RNA-seq pre-computed differentials (OSD-569) using a canonical DDR gene signature (ATM, ATR, BRCA1/2, TP53, H2AX, RAD51, GADD45A, XRCC family). Mitochondrial function from plasma metabolomics pre-computed differentials (OSD-571) — TCA-cycle intermediates and acylcarnitines as direct readouts.

Each axis gets its own dashboard panel. The primary axes carry the integration logic; the secondary axes are reported cleanly off existing differentials.

## Datasets

Nine of the twelve OSDR datasets in the starter notebook:

| Dataset | OSD ID | Role |
|---|---|---|
| Dragon capsule swabs | 573 | Environmental microbiome source |
| Crew skin / oral / nasal swabs | 572 | Host-site colonization |
| Stool metagenomics | 630 | Gut microbiome shifts |
| Spatial skin transcriptomics | 574 | Barrier-gene expression |
| PBMC profiling | 570 | Immune cell composition |
| Whole-blood transcriptomics | 569 | DDR gene signature |
| Serum cytokines & metabolic panel | 575 | Systemic inflammation, immune cytokines |
| Urine inflammation panel | 656 | Renal/systemic inflammation |
| Plasma metabolomics | 571 | Mitochondrial readout |

## Approach

### Core microbiome → barrier → immune integration

For each astronaut Claude tells us to compute:

1. **Shared-taxa fraction** between capsule surfaces (OSD-573) and the astronaut's body sites (OSD-572, OSD-630). Capsule taxa present pre-launch and absent on the crew member preflight, then present on the crew member in-flight or post-return, suggest environment-to-host transfer.
2. **Correlation** between site-specific microbial shifts and barrier-gene expression (FLG, CLDN, OCLN, HAS1/2/3) from OSD-574.
3. **Correlation** between gut and oral microbial shifts (OSD-630, OSD-572 oral) and downstream cytokine (OSD-575) and urine-inflammation (OSD-656) markers.

Directionality is earned through temporal precedence — capsule taxa observed pre-launch → crew colonization in-flight or post-return → barrier-gene downregulation → cytokine response — not by correlation alone. Where temporal precedence isn't supported, the link is reported as undirected.

### Scoring method

Each astronaut receives a four-panel score, one panel per Track 2 axis. We deliberately do not aggregate into a single risk number, as Track 2's astronaut-facing question is multifaceted and a single number would obscure it. But we reserve the right to create a single number risk factor for ease of viewing and comparison between astronauts to ensure a merit-based approach for determining which astronaut should go to space.

- **Immune regulation.** Composite z-score of PBMC immune-cell proportion deviations (OSD-570) and Th1/Th2/Treg-aligned serum cytokine deviations (OSD-575), normalized against each astronaut's own preflight baseline (L−92, L−44, L−3).
- **Inflammation & oxidative stress.** Composite z-score of acute-phase cytokines (IL-6, TNF, CRP from OSD-575), urine inflammation markers (OSD-656), and oxidative-stress-related metabolites (OSD-571).
- **DNA damage response.** Mean z-score of the canonical DDR gene signature from OSD-569, normalized against own preflight baseline.
- **Mitochondrial function.** Mean z-score of TCA-cycle intermediates and acylcarnitines from OSD-571, normalized against own preflight baseline.

Scores are reported as deviation-from-own-baseline **trajectories** across the ten timepoints (L−92, L−44, L−3, FD1, FD2, FD3, R+1, R+45, R+82, R+194), not as point estimates. Two comparisons accompany each trajectory:

- **Within-cohort.** Each astronaut against the other three.
- **Against published priors.** Tierney/Park supplementary tables where the marker overlaps.

n = 4 is honored by reporting per-astronaut effects rather than computing group-level p-values. Confidence intervals are bootstrap intervals over the three preflight baseline timepoints, with the explicit caveat that this captures within-baseline variance only.

### What each axis can see in orbit

Not every panel is observable in flight. The deck is explicit about which collections were ground-only:

- **In-flight readable.** Skin/oral/nasal microbiome (dry and wet swabs, OSD-572), saliva-based markers in OSD-575 (FD2 and FD3 only), DBS-derived analytes.
- **Ground-only (pre-vs-post contrasts only).** Stool metagenomics, urine inflammation, venous-blood transcriptomics, deltoid biopsies.

Each dashboard panel labels its observable timepoints, so a crew member reading their profile knows which markers a longer-duration mission could realistically monitor.

## Deliverable

A four-panel astronaut-readable dashboard, one panel per Track 2 axis. Each panel contains:

- The per-astronaut score trajectory across the ten timepoints, with bootstrap uncertainty bands.
- Within-cohort comparison and prior-cohort comparison where available.
- A short methods note: which features feed the score, how they're normalized, what the uncertainty bands mean, and what could break the inference.
- An **actionable line**: which marker is worth monitoring on a longer-duration mission, and what preflight baseline would tighten the estimate next time.

The signature visual is a per-crew-member microbiome → barrier → immune flow diagram, embedded in the immune and inflammation panels, showing capsule-to-skin taxa transfer, barrier-gene response, and downstream cytokine and urine markers.

## 72-hour plan

Mirroring the deck's arc.

- **Hours 0–6: Think about tracks.** Save Colab copy. Make the README. Inventory all nine datasets. Read Tierney/Park supplementary tables. Confirm dataset shapes (abundance matrix vs pre-computed differential).
- **Hours 6–24: Explore.** Distributions, missingness, batch checks per dataset. No scoring yet. End with a one-page note on what's actually trustworthy in each dataset.
- **Hours 24–48: Build.** MVP first: one astronaut, immune + inflammation panels only, end-to-end. Then extend to all four crew members and the two secondary axes. ≥ 2 GitHub commits in this window.
- **Hours 48–66: Stress-test.** Recompute one score from scratch by hand. Try to break our own findings — swap astronaut labels and check whether the scoring still produces a "signal" it shouldn't. Write methods note.
- **Hours 66–72: Ship.** README finalized last. Restart kernel, run top to bottom. Tag final commit.

## Honesty clauses

- **Null-result clause.** If we find no correlation between capsule taxa and barrier-gene downregulation, or none between microbial shifts and cytokine response, we report that and explain why (small n, inter-individual variability, modality mismatch). A negative result is a result.
- **Causal language.** Causal phrasing is avoided where evidence is correlational. The flow diagram is a summary of correlated transitions with temporal ordering, not a causal model.
- **AI usage.** AI tools are used for code scaffolding, reading existing literature, and editing the prose. Every clinical-sounding claim is verified against the source data or published literature. No clinical recommendations are made, as this is a research artifact, not medical advice.

## Reproducibility

Restart kernel, run top to bottom. Final commit tagged. Environment pinned in `requirements.txt`. Random seeds set in `config.py`.
