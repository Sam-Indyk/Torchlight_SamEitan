"""Healthy-adult reference values for serum cytokines and CRP.

Used to populate the population_z trajectory channel for analytes whose
panel CSV does not embed clinical reference ranges (multiplex cytokines,
which include OSD-575 Eve and OSD-575 cardio Eve).

Scale calibration is critical: Luminex and Olink/Alamar panels produce
values on incompatible scales, so reference values are stored together
with an `assay_class` tag and matched at lookup time.

  - eve_pgml         : Eve / Quanterix multiplex, absolute pg/mL
  - eve_pgml_crp     : same panel, but for CRP whose literature is in mg/L
                       (1 mg/L = 1e6 pg/mL); the reference values below are
                       stored in pg/mL to match the cached file.
  - alamar_npq       : Olink-derived Normalized Protein eXpression Quantity;
                       no published population SD exists, so we deliberately
                       do NOT publish population_z for these analytes.

Values are best-effort estimates compiled from:
  - Kleiner et al. 2013 (Cytokine 50:1, n=146 healthy adults, Luminex)
  - Biancotto et al. 2013 (PLoS One 8:e76091, n=27 healthy donors, multiplex)
  - Said et al. 2021 (Cytokine 142:155501, healthy reference Luminex)
  - NHANES (CRP, n>20,000 healthy adults; median 1.5 mg/L,
    95th percentile ~10 mg/L)

These are APPROXIMATE. Different multiplex platforms differ in absolute
scale by 2-10x; treat population_z as a directional, not precise,
clinical comparator. The methods note in the GUI surfaces this caveat.
"""

from __future__ import annotations
import re
from typing import Iterable

# --- the reference table ---------------------------------------------------

# Each entry:
#   key (lower-case)  : a substring that the analyte label must contain
#   median, sd        : both in pg/mL (matched to the Eve panel scale)
#   assay_class       : one of "eve_pgml", "eve_pgml_crp"
#   source, notes     : provenance for the methods note

EVE_REFS: dict[str, dict] = {
    "il_6": {
        "median": 1.8, "sd": 4.5,
        "assay_class": "eve_pgml",
        "source": "Kleiner 2013 / Biancotto 2013 (Luminex multiplex healthy adults)",
        "notes": "Right-skewed distribution; sd reflects upper-tail spread; "
                 "values inside ~5 pg/mL are typical, >10 is acute-phase elevated.",
    },
    "il_10": {
        "median": 3.5, "sd": 8.0,
        "assay_class": "eve_pgml",
        "source": "Kleiner 2013, Said 2021",
        "notes": "Anti-inflammatory cytokine; healthy median low single-digit pg/mL.",
    },
    "il_4": {
        "median": 0.8, "sd": 2.5,
        "assay_class": "eve_pgml",
        "source": "Biancotto 2013",
        "notes": "Th2 cytokine; very low in healthy adults.",
    },
    "il_2": {
        "median": 1.0, "sd": 5.0,
        "assay_class": "eve_pgml",
        "source": "Kleiner 2013",
        "notes": "Th1 / T-cell growth factor; typically <5 pg/mL at rest.",
    },
    # IFN-gamma; the Eve label is 'ifn?_concentration...' where the ? is a
    # unicode gamma. We match on 'ifn' but require it not to also match
    # ifn-alpha-2 ('ifn_?2').
    "ifn": {
        "median": 5.0, "sd": 25.0,
        "assay_class": "eve_pgml",
        "source": "Kleiner 2013, Said 2021",
        "notes": "IFN-gamma. Highly variable in healthy adults; some carriers "
                 "of latent infection sit much higher.",
        "exclude_substrings": ["ifn_?2", "ifna", "ifn_a2"],  # exclude IFN-alpha-2
    },
    "tnf": {
        "median": 8.0, "sd": 12.0,
        "assay_class": "eve_pgml",
        "source": "Kleiner 2013, Biancotto 2013",
        "notes": "TNF-alpha. Eve panel reads ~10x higher than ELISA Quantikine; "
                 "reference matched to Luminex/Eve scale.",
        "exclude_substrings": ["tnfrs", "tnfsf"],  # don't match receptor superfamily
    },
    "tgf": {
        "median": 18.0, "sd": 12.0,
        "assay_class": "eve_pgml",
        "source": "Said 2021",
        "notes": "TGF-beta active form on Eve panel (not the conventional total "
                 "TGF-beta in ng/mL).",
    },

    # CRP arrives in pg/mL on the cardio_eve panel. NHANES median is 1.5 mg/L
    # = 1.5e6 pg/mL; 95th percentile ~10 mg/L = 1e7 pg/mL.
    "crp": {
        "median": 1_500_000.0, "sd": 4_000_000.0,
        "assay_class": "eve_pgml_crp",
        "source": "NHANES (n>20000 healthy adults)",
        "notes": "Stored in pg/mL to match the cached file; equivalent to "
                 "median 1.5 mg/L, sd ~4 mg/L. Right-skewed.",
    },
}


def lookup(analyte_label: str) -> dict | None:
    """Return the reference entry whose `key` substring matches `analyte_label`,
    respecting any `exclude_substrings`. Returns None on no match.

    Matches are case-insensitive on the lowercased label.
    """
    s = analyte_label.lower()
    if "_percent" in s:
        return None
    if "range_min" in s or "range_max" in s:
        return None

    # Don't apply to non-Eve assays. NPQ scale is incompatible with our
    # pg/mL references.
    if "_npq" in s:
        return None

    for key, entry in EVE_REFS.items():
        if key not in s:
            continue
        excludes = entry.get("exclude_substrings", [])
        if any(ex in s for ex in excludes):
            continue
        return entry
    return None


def population_z(value: float, analyte_label: str) -> tuple[float, dict] | None:
    """Compute (z, reference_entry) using the linear-z approximation
    z = (x - median) / sd against the reference values above.

    Returns None when no reference is found. The linear approximation is
    rough for right-skewed cytokines but useful as a directional indicator;
    for example, a +2 pop_z on IL-6 means "about 2 SDs above the healthy
    median," which is informative even if the underlying distribution is
    log-normal.
    """
    import math
    entry = lookup(analyte_label)
    if entry is None:
        return None
    median = entry["median"]
    sd     = entry["sd"]
    if sd <= 0 or not math.isfinite(value):
        return None
    return ((value - median) / sd, entry)


def all_references_used(analyte_labels: Iterable[str]) -> list[dict]:
    """Return the list of distinct reference entries used by any of the
    analytes — for the methods-note 'Sources' line.
    """
    seen_keys: set[str] = set()
    out: list[dict] = []
    for label in analyte_labels:
        s = str(label).lower()
        for key, entry in EVE_REFS.items():
            if key in s and key not in seen_keys:
                excludes = entry.get("exclude_substrings", [])
                if any(ex in s for ex in excludes):
                    continue
                seen_keys.add(key)
                out.append({"key": key, **entry})
                break
    return out
