# risk_profile_claude

Population-anchored per-astronaut risk scoring on top of `analysis/`.

This folder is **additive** — it does not modify [analysis/](../analysis/),
which is your partner's territory per [CLAUDEPLAN.md](../CLAUDEPLAN.md). It
reads cached OSDR data (downloaded by `analysis/`) and the per-dataset DE
CSVs in [analysis/results/](../analysis/results/), then writes a JSON file
that conforms to the GUI data contract documented in
[CLAUDEPLAN.md](../CLAUDEPLAN.md#data-contract--the-most-important-section).

## What this adds beyond `analysis/`

The pipeline in `analysis/` answers: *"did all four crew change concordantly,
and by how much?"* It produces lists of features and pooled DE tables. That's
the right output for a molecular-perturbation report, but it doesn't directly
produce per-astronaut, per-timepoint trajectories — which is what the
[Track 2 dashboard](../README.md#deliverable) needs.

This folder closes that gap. It computes, for each astronaut and each
timepoint:

1. **Own-baseline z-score.** `(value - mean(self_preflight)) / sd(self_preflight)`
   — how far this astronaut has moved from their own preflight values.
2. **Population-anchored z-score.** `(value - range_midpoint) / (range_width / 3.92)`
   using the clinical reference ranges that ship inside the OSD-575 CMP and
   OSD-569 CBC files (`*_range_min` / `*_range_max` rows). The
   `analysis/common.py` pipeline drops these as "uninformative" before DE
   testing — but for population anchoring they *are* the population, so we
   keep them.
3. **Panel Mahalanobis distance.** Multivariate deviation across a small
   correlated panel (e.g., the lipid-membrane panel: LysoPC family + S1P +
   sphingomyelins). Marginal SDs come from the population reference range;
   the correlation matrix is estimated from the preflight pool (12 samples =
   4 crew × 3 preflight timepoints). This is a hybrid: population-anchored
   scale, cohort-anchored coupling. The methods note in the JSON output
   states this explicitly.

These three numbers feed the four Track 2 axes (immune regulation,
inflammation & oxidative stress, DDR, mitochondrial). Each axis carries an
in-flight observability flag — not all panels were collected in flight.

## Why population anchoring matters at n=4

Own-baseline z-scoring (3 preflight timepoints per astronaut) gives a
narrow, possibly unstable denominator. Population-reference z-scoring
gives an absolute biological scale that is interpretable on its own:
"this LDL value is 4σ outside the healthy adult range" is a meaningful
statement *even with one observation*, while "this LDL value is 1.8σ above
the astronaut's own three preflight measurements" is hard to act on without
a larger baseline.

The two are reported side by side. Disagreement between them is itself
informative — for example, a marker that has moved a lot relative to its
own baseline but stayed inside the population reference range is a
"recalibration within healthy" rather than a "departure from healthy."

## What it reads

| Source | Used for |
|---|---|
| `analysis/.cache/LSDS-8_Comprehensive_Metabolic_Panel_CMP_TRANSFORMED.csv` | OSD-575 CMP per-subject + reference ranges |
| `analysis/.cache/LSDS-7_Complete_Blood_Count_CBC.upload_SUBMITTED.csv` | OSD-569 CBC per-subject + reference ranges |
| `analysis/.cache/LSDS-8_Multiplex_serum_immune_EvePanel_TRANSFORMED.csv` | OSD-575 cytokines per-subject |
| `analysis/.cache/LSDS-8_Multiplex_serum.immune.AlamarPanel_TRANSFORMED.csv` | OSD-575 cytokines per-subject |
| `analysis/.cache/LSDS-8_Multiplex_serum_cardiovascular_EvePanel_TRANSFORMED.csv` | OSD-575 cardio per-subject |
| `analysis/.cache/LSDS-64_Multiplex_urine.immune.AlamarPanel_TRANSFORMED.csv` | OSD-656 urine per-subject |
| `analysis/results/OSD-571_*_pooled_DE.csv` | Pooled DE for mitochondrial axis (per-cohort, not per-astronaut) |
| `analysis/results/OSD-569_rna_blood_post_vs_pre.csv` | Pooled DE for DDR axis |

If a cache file is missing, the corresponding axis is filled with mock data
so the GUI MVP can still render every panel.

## What it writes

- `data/dashboard_data.json` — the file the GUI consumes (see
  [SCHEMA.md](SCHEMA.md))
- `risk_profile_claude/mock_dashboard_data.json` — committed plausible
  fallback the GUI partner can build against immediately, no analysis run
  required

Both files are valid against the same schema. Swap one for the other by
changing which path the GUI loads.

## How to run

```powershell
cd Torchlight_SamEitan
python risk_profile_claude\build_risk_profile.py
```

Outputs `data/dashboard_data.json`. Re-running is idempotent and overwrites.
The script runs entirely against the local cache — no network calls.

If you'd like a dry run that only regenerates the mock without touching
the real cache, pass `--mock-only`.

## Honest caveats (these go into the JSON `methods_note` per axis)

- **Astronauts are pre-screened for fitness.** Population reference ranges
  are healthy-adult intervals (typically central 95%), not matched-control
  intervals. A reading inside the reference range tells us less than one
  outside it.
- **Reference ranges assume 95% interval = ±1.96σ.** For analytes whose
  population distribution is heavily skewed (e.g., CRP, ferritin), this
  underestimates the right-tail SD. Where this matters, the methods note
  flags it and prefers the own-baseline z.
- **Mahalanobis correlation matrix is estimated from 12 samples.** The
  preflight pool is small. We use Ledoit–Wolf shrinkage toward a diagonal
  identity to keep the inverse stable, but the correlation structure should
  be treated as a regularized estimate, not a population truth.
- **In-flight observability is panel-dependent.** Blood / urine / CMP /
  CBC are ground-only on Inspiration-4 (no in-flight phlebotomy). Those
  trajectories show pre and post points only; in-flight slots are masked
  and carry an `observable: false` flag in the JSON.
- **n=4.** Per-astronaut effects only. No group-level p-values. The
  within-cohort comparison reports each astronaut against the other three
  for context, not for hypothesis testing.

## Folder layout

```
risk_profile_claude/
├── README.md                   # This file
├── SCHEMA.md                   # JSON output contract
├── build_risk_profile.py       # Entry point — does everything
└── mock_dashboard_data.json    # Fallback for GUI development
```

One-file design is deliberate: 72-hour hackathon, you want all the scoring
logic in a single readable script your partner can audit in one sitting.
