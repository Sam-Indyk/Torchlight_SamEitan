# Microbiome–Immune–Barrier Axis Integrator

**Track 2 — Individualized Risk Profile.** Inspiration4 (n = 4), Torchlight Summit Biosovereignty Hackathon, May 6–9 2026.

---

## 🚀 Open the live dashboard

# **[torchlightsameitan-d6ydnn3ximwbpt6yiko3gp.streamlit.app](https://torchlightsameitan-d6ydnn3ximwbpt6yiko3gp.streamlit.app/)**

No install required. Public, hosted on Streamlit Cloud. The app *is* the deliverable — this README is the supporting documentation.

---

## What this is, in one paragraph

A per-astronaut risk profile of the Inspiration-4 spaceflight cohort, integrating nine OSDR multi-omics datasets into the four Track 2 health axes — **immune regulation**, **inflammation & oxidative stress**, **DNA damage response**, and **mitochondrial function**. Each axis is scored against the astronaut's own preflight baseline *and* against published healthy-adult reference ranges, with bootstrap CIs and exponential recovery-rate fits. A grounded-LLM layer lets users ask natural-language questions over the precomputed scores, with a regex verifier that rejects any AI claim not present in the source data. Every chart has explicit units and a "Why this chart?" expander. **No synthetic data, no causal claims, no clinical recommendations** — n = 4 is honored throughout.

---

## How to read the dashboard (left → right)

| # | Tab | What you'll find |
|---|---|---|
| 1 | **Mission Overview** | Hero, anonymous crew cards (C001–C004), at-a-glance stats (n=4, 9 datasets, 67k concordant features, **96% capsule→NAP taxa overlap**), mission timeline, and an interactive body-sample map with a **time-machine slider** flipping between preflight / in-flight / post-flight phases |
| 2 | **Individualized Risk Profile** *(Track 2 deliverable)* | Four-axis overview with R+1 ranking and recovery-half-life matrix · multi-system Mahalanobis (single risk number) · per-astronaut clinical-style report cards · **side-by-side astronaut comparison** with per-axis difference table · per-axis drill-downs with trajectory, 95% bootstrap CI, recovery-rate fits, prior-cohort overlay, methods note |
| 3 | **AI · grounded in the data** *(Best Use of AI submission)* | "Ask the dashboard" natural-language Q&A · per-astronaut AI narratives, both with regex-verified numeric grounding (visible green ✓ / yellow ⚠ badges) |
| 4 | **Upstream Causes** | Network view of 8 hand-curated cascades (microgravity / radiation / fluid-shift → root causes → match against data) · per-cascade detail with chain-of-pills visualization, terminal-observation match table, and citations |
| 5 | **Capsule → Barrier → Systemic Flow** | Per-astronaut signature visual: 4-column SVG flow with computed edge weights showing capsule taxa → body sites → skin barrier → systemic cytokines |
| 6 | **Molecular Perturbations · Microbiome / Systemic** | Heatmaps and bar charts of the underlying DE results, read directly from `analysis/results/` CSVs |
| 7 | **Data Sources & Provenance** | What's real, what's calibrated. Every internal OSDR dataset and every external literature reference (population SDs, Tierney/Park overlays) with citations |

Every chart has an **ⓘ About this chart** expander documenting type, units, and rationale.

---

## Run it locally (optional)

The live deploy above is the canonical way to look at the project. If you want to run the dashboard locally — to inspect the code, regenerate the JSON, or develop on top of it — here's the three-command path:

```bash
git clone https://github.com/Sam-Indyk/Torchlight_SamEitan.git
cd Torchlight_SamEitan
pip install -r requirements.txt
streamlit run guiv2/app.py
```

Streamlit prints `http://localhost:8501/` and auto-opens the browser. Use the `streamlit` CLI, not `python guiv2/app.py` — Streamlit apps must be launched through their CLI runner. If `streamlit` isn't on PATH, `python -m streamlit run guiv2/app.py` works.

For the AI tab, set `ANTHROPIC_API_KEY` in your shell before launching, or paste a key into the in-app password gate (session-only, never written to disk). The free tier is plenty for a few minutes of exploration.

To regenerate `data/dashboard_data.json` from the cached OSDR data:

```bash
python risk_profile_claude/build_risk_profile.py
```

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

## How we used AI

> **Best Use of AI award submission.** TL;DR — AI is used in two
> grounded, verifiable roles inside the dashboard, plus as a
> development tool for the surrounding code. The model never touches
> raw OSDR data; it only reads the structured JSON our deterministic
> pipeline produced, and every numeric claim it makes is checked
> against that JSON before being shown.

### 1. Runtime AI features inside the dashboard *(this is the submission)*

Open the **AI · grounded in the data** tab. Two LLM features live there, both backed by Claude Haiku 4.5 via the Anthropic API:

- **Per-astronaut AI narratives** ([`guiv2/ai/narrative.py`](guiv2/ai/narrative.py))
  — for each crew member, a JSON slice of that astronaut's risk
  profile is sent to Claude with a tight system prompt; Claude returns
  a 2-paragraph factual summary covering the largest R+1 deviation,
  the recovery profile (slow vs fast), within-cohort context, and a
  one-sentence honest caveat. Cached on disk by `(crew_id, json_hash)`
  so reloads cost no tokens.

- **"Ask the dashboard" Q&A** ([`guiv2/ai/qa.py`](guiv2/ai/qa.py)) —
  a chat-style input box. Five suggested questions are pre-loaded as
  one-click buttons; users can also type their own. Claude reads a
  slimmed copy of `data/dashboard_data.json` and answers in 1–3
  sentences citing verbatim numbers from the source data.

**The grounding architecture (the bit we'd actually like the prize for):**

- **Hard system prompts** ([`guiv2/ai/prompts.py`](guiv2/ai/prompts.py))
  forbid (a) inventing numbers, (b) causal language, (c) clinical
  recommendations, and instruct the model to flag mock or
  cohort-level axes inline and redirect out-of-scope questions.
- **A regex numeric verifier**
  ([`guiv2/ai/verify.py`](guiv2/ai/verify.py)) scans every AI output
  for numeric claims and checks each one against the source JSON,
  with rounding and percent ↔ fraction tolerance. Unverified numbers
  trigger a one-shot retry with a stricter reminder; if anything is
  still unverified after retry, the panel surfaces a **yellow warning
  listing the unverified numbers** above the AI output. When all
  numbers pass, a **green ✓ "every number is grounded in the source"**
  badge is shown. Judges can watch grounding succeed or fail in
  real time.
- **The model never sees raw OSDR data.** It only sees
  [`data/dashboard_data.json`](data/dashboard_data.json), the output
  of our deterministic scoring pipeline. Every number it can possibly
  cite is one we precomputed.

**Pitch in one sentence.** *AI is used as a query translator and prose
generator over a precomputed, structured data object — never as a
source of truth — and a verifier rejects any claim not grounded in
that object.*

Full disclosure (data privacy, models used, what AI explicitly did
NOT do): [**`AI_USES.md`**](AI_USES.md). Design rationale and the
options we considered but skipped: [**`AI_PLAN.md`**](AI_PLAN.md).

### 2. Development-time AI use *(transparency, not part of the prize submission)*

Most of the code in [`risk_profile_claude/`](risk_profile_claude/) and
[`guiv2/`](guiv2/) was scaffolded by Claude Code (Opus 4.7) following
human-authored design briefs. A human directed every step, reviewed
every diff, and accepted or revised the output. The README and the
methods notes inside the dashboard panels were AI-assisted; every
clinical-sounding claim was checked against the source data or the
cited literature.

**What AI did NOT do:**

- **No statistics were invented by AI.** Every score, z-value,
  half-life, Mahalanobis distance, recovery τ, and edge weight in the
  dashboard comes from a deterministic computation in
  [`risk_profile_claude/build_risk_profile.py`](risk_profile_claude/build_risk_profile.py).
- **No synthetic astronauts.** The dataset contains four real crew
  members; we did not generate or simulate any additional data.
- **No fabricated citations.** Every paper cited (Tierney 2024,
  Park 2024, Kleiner 2013, Biancotto 2013, Said 2021, NHANES,
  Garrett-Bakelman 2019, da Silveira 2020, Versari 2013,
  Pakos-Zebrucka 2016) is a real publication. The hand-curated
  cascades in
  [`risk_profile_claude/pathway_priors.py`](risk_profile_claude/pathway_priors.py)
  cite real biology.
- **No clinical recommendations.** This is a research artifact, not
  medical advice. No AI output recommends or implies a fly/no-fly
  decision for any astronaut.

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
