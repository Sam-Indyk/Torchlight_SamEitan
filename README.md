# Microbiome–Immune–Barrier Axis Integrator

**Track 2 — Individualized Risk Profile.** Inspiration4 (n = 4), Torchlight Summit Biosovereignty Hackathon, May 6–9 2026.

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

- **Hours 0–6 — Orient.** Save Colab copy. Make the README. Inventory all nine datasets. Read Tierney/Park supplementary tables. Confirm dataset shapes (abundance matrix vs pre-computed differential).
- **Hours 6–24 — Explore.** Distributions, missingness, batch checks per dataset. No scoring yet. End with a one-page note on what's actually trustworthy in each dataset.
- **Hours 24–48 — Build.** MVP first: one astronaut, immune + inflammation panels only, end-to-end. Then extend to all four crew members and the two secondary axes. ≥ 2 GitHub commits in this window.
- **Hours 48–66 — Stress-test.** Recompute one score from scratch by hand. Try to break our own findings — swap astronaut labels and check whether the scoring still produces a "signal" it shouldn't. Write methods note.
- **Hours 66–72 — Ship.** README finalized last. Restart kernel, run top to bottom. Tag final commit.

## Honesty clauses

- **Null-result clause.** If we find no correlation between capsule taxa and barrier-gene downregulation, or none between microbial shifts and cytokine response, we report that and explain why (small n, inter-individual variability, modality mismatch). A negative result is a result.
- **Causal language.** Causal phrasing is avoided where evidence is correlational. The flow diagram is a summary of correlated transitions with temporal ordering, not a causal model.
- **AI usage.** AI tools are used for code scaffolding, literature surfacing, and prose editing. Every clinical-sounding claim is verified against the source data or published literature. No clinical recommendations are made — this is a research artifact, not medical advice.

## Reproducibility

Restart kernel, run top to bottom. Final commit tagged. Environment pinned in `requirements.txt`. Random seeds set in `config.py`.
