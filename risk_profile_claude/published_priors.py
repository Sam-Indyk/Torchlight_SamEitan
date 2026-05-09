"""Approximate per-axis R+1 reference values pulled from prior spaceflight
multi-omics cohorts (Tierney 2024, Park 2024). Used to overlay a
"what other studies found at this timepoint" reference line on each
axis trajectory chart in the GUI.

These numbers are APPROXIMATE — converted from the fold-change magnitudes
those papers report into our z-score scale (own-baseline preflight SD).
The conversion assumes a similar preflight SD to ours, which is a
reasonable but imperfect mapping.

They serve as a calibration check, not a precise comparator: judges can
see at a glance whether this cohort's R+1 deviation is in the same
ballpark as published priors, or unusually high/low.

To replace any of these with values pulled directly from a paper's
supplementary tables, edit the matching entry's `r1_score_estimate`,
update `method`, and change the `is_approximate` flag to False.
"""

from __future__ import annotations


# Per-axis prior-cohort reference values. Keyed by axis id from build_*.
PRIORS: dict[str, dict] = {
    "immune": {
        "tp": "R+1",
        "r1_score_estimate": 1.5,
        "source": "Tierney et al. 2024 (Inspiration-4 multi-omics)",
        "method": ("Tierney 2024 reports per-astronaut Th1/Th2/Treg cytokine "
                   "shifts of approximately 1-2x preflight magnitude at R+1 "
                   "across most crew. Converted to ~1.5 own-baseline SD."),
        "is_approximate": True,
    },
    "inflammation": {
        "tp": "R+1",
        "r1_score_estimate": 2.0,
        "source": "Tierney et al. 2024; Park et al. 2024",
        "method": ("Tierney 2024 reports IL-6 elevations of ~2-3x baseline "
                   "and TNF-alpha elevations of ~1.5-2x at R+1; Park 2024 "
                   "reports concordant PF4/TGFB1 plasma elevations. "
                   "Converted to ~2.0 own-baseline SD as a representative "
                   "magnitude."),
        "is_approximate": True,
    },
    "ddr": {
        "tp": "R+1",
        "r1_score_estimate": 1.5,
        "source": "Spaceflight DDR literature (Garrett-Bakelman 2019, "
                  "Tierney 2024)",
        "method": ("DDR gene-set induction at R+1 in spaceflight cohorts "
                   "typically runs ~1-2 SD above ground-control baseline. "
                   "Approximate."),
        "is_approximate": True,
    },
    "mitochondrial": {
        "tp": "R+1",
        "r1_score_estimate": 1.5,
        "source": "Tierney et al. 2024",
        "method": ("Tierney 2024 reports LysoPC family suppression and "
                   "TCA-cycle perturbation magnitudes consistent with ~1-2 "
                   "SD post-flight deviation."),
        "is_approximate": True,
    },
}


def get(axis_id: str) -> dict | None:
    """Return the prior-cohort overlay block for an axis id, or None."""
    return PRIORS.get(axis_id)
