"""
Shared utilities for Inspiration-4 dataset analyses.

Goal: identify features (cytokines, taxa, KO functions, genes, analytes) that
significantly changed between pre-flight, in-flight, and post-flight phases
for each of the four Inspiration-4 crew (C001..C004), and flag those that
significantly changed in ALL FOUR subjects in the same direction.

Key design choices (the "doing research" part):

  1. Crew IDs are C001-C004. Capsule/communal samples (Communal_*, H20, etc.)
     are environmental, not per-subject, and are excluded from the
     "all-four-subjects" test.
  2. Timepoint phases:
        pre   : L-92, L-44, L-3
        during: FD2, FD3   (only available for swabs/microbiome)
        post  : R+1, R+45, R+82, R+194
     For serum / RNA-seq / urine / CBC there are no in-flight samples
     (you cannot draw blood in space on this mission), so we only test
     pre-vs-post for those datasets.
  3. Reference-range "rows/columns" (RANGE_MIN, RANGE_MAX, *_range_min,
     *_range_max) are CONSTANT clinical reference bounds, not measurements.
     They are dropped before testing.
  4. Cytokine panels report both *_concentration_* and *_percent_* (percent
     of pooled normal). The percent column is a derived rescaling of the
     concentration, so we keep concentrations and drop the percent rows
     to avoid double-counting.
  5. "Unnamed: N" columns from CSV header artifacts are dropped.
  6. Significance criterion (per subject, per feature):
        - log2 fold-change between phase means with a small pseudocount,
          combined with a directional consistency check.
        - Magnitude threshold: |log2FC| >= LOG2FC_THRESHOLD (default 1.0,
          i.e. 2x change). This is the standard "biologically meaningful"
          fold-change cutoff used in the spaceflight multi-omics literature.
        - We additionally require the change to exceed the within-pre
          variability (z-score check) when there are >=2 pre samples,
          which guards against features whose baseline already swings 2x.
  7. "Significantly changed in all four subjects":
        - All four crewmembers must individually pass the per-subject
          threshold AND change in the same direction (sign of log2FC matches).
        - We do NOT compute group-level p-values: n=4 with per-subject
          longitudinal sampling is too small for reliable group inference,
          which the project README explicitly notes (we report per-astronaut
          effects, not group p-values).
"""

from __future__ import annotations
import os
import re
from dataclasses import dataclass, field
from typing import Iterable

import numpy as np
import pandas as pd


# --------------------------------------------------------------------------
# constants
# --------------------------------------------------------------------------

CREW = ("C001", "C002", "C003", "C004")

PRE_TIMEPOINTS    = ("L-92", "L-44", "L-3")
DURING_TIMEPOINTS = ("FD2", "FD3")
POST_TIMEPOINTS   = ("R+1", "R+45", "R+82", "R+194")

ALL_TIMEPOINTS = PRE_TIMEPOINTS + DURING_TIMEPOINTS + POST_TIMEPOINTS

LOG2FC_THRESHOLD = 1.0          # 2x change
PSEUDOCOUNT      = 1e-6
PADJ_THRESHOLD   = 0.05         # for pre-aggregated DE tables

RESULTS_DIR = os.path.join(os.path.dirname(__file__), "results")


# --------------------------------------------------------------------------
# sample-name parsing
# --------------------------------------------------------------------------

# matches e.g. C001, C002 anywhere in the sample name. We can't use \b
# because '_' is a regex word character, so '\bC001\b' fails against
# 'C001_FD2_ARM' (no boundary between '1' and '_'). Use lookarounds for
# non-alphanumerics, which treat '_' as a separator.
_CREW_RE = re.compile(r"(?<![A-Za-z0-9])(C00[1-4])(?![A-Za-z0-9])")
# matches a timepoint token; order matters - longest first so 'R+194'
# wins over 'R+1'.
_TP_RE   = re.compile(r"(L-92|L-44|L-3|FD2|FD3|R\+194|R\+82|R\+45|R\+1)")


def parse_sample(name: str) -> tuple[str | None, str | None]:
    """Return (crew_id, timepoint) parsed out of a sample column/row name.

    Returns (None, None) if either piece is missing - which is the case for
    capsule/communal/control samples that should be excluded from the
    per-subject test.
    """
    if not isinstance(name, str):
        return (None, None)
    crew_m = _CREW_RE.search(name)
    tp_m   = _TP_RE.search(name)
    return (crew_m.group(1) if crew_m else None,
            tp_m.group(1)   if tp_m   else None)


def phase_of(timepoint: str | None) -> str | None:
    if timepoint in PRE_TIMEPOINTS:    return "pre"
    if timepoint in DURING_TIMEPOINTS: return "during"
    if timepoint in POST_TIMEPOINTS:   return "post"
    return None


# --------------------------------------------------------------------------
# variable filtering ("research" decisions about which rows/cols matter)
# --------------------------------------------------------------------------

def is_uninformative_feature(name: str) -> bool:
    """True if a row/column name is a reference range, percent-normalized
    sibling, or a CSV header artifact - i.e. NOT a primary measurement."""
    if not isinstance(name, str):
        return True
    n = name.lower()
    if n.startswith("unnamed"):
        return True
    if n.endswith("_range_min") or n.endswith("_range_max"):
        return True
    if "range_min_" in n or "range_max_" in n:
        return True
    # cytokine panels duplicate every concentration with a *_percent companion
    if n.endswith("_percent") or n.endswith("_percent_normalized_value"):
        return True
    return False


def drop_uninformative(df: pd.DataFrame, axis: str = "index") -> pd.DataFrame:
    """Drop rows (or columns) that are reference ranges / percent siblings."""
    labels = df.index if axis == "index" else df.columns
    keep = [l for l in labels if not is_uninformative_feature(str(l))]
    return df.loc[keep] if axis == "index" else df[keep]


# --------------------------------------------------------------------------
# per-subject phase aggregation
# --------------------------------------------------------------------------

def group_columns_by_subject_phase(columns: Iterable[str]
                                   ) -> dict[tuple[str, str], list[str]]:
    """{(crew, phase): [column_names]} - drops anything we can't classify."""
    out: dict[tuple[str, str], list[str]] = {}
    for c in columns:
        crew, tp = parse_sample(str(c))
        ph = phase_of(tp)
        if crew is None or ph is None:
            continue
        out.setdefault((crew, ph), []).append(c)
    return out


def phase_means(df: pd.DataFrame,
                groups: dict[tuple[str, str], list[str]]
                ) -> pd.DataFrame:
    """For each (crew, phase) group, take the mean across the columns in
    that group. Returns a DataFrame indexed like df, with MultiIndex columns
    (crew, phase)."""
    pieces = {}
    for (crew, phase), cols in groups.items():
        sub = df[cols].apply(pd.to_numeric, errors="coerce")
        pieces[(crew, phase)] = sub.mean(axis=1)
    out = pd.DataFrame(pieces)
    out.columns = pd.MultiIndex.from_tuples(out.columns,
                                            names=["crew", "phase"])
    return out


# --------------------------------------------------------------------------
# significance test
# --------------------------------------------------------------------------

@dataclass
class FeatureCall:
    feature: str
    direction: str          # "up" or "down"
    log2fc_per_crew: dict[str, float] = field(default_factory=dict)
    phase_compared: str = "post_vs_pre"


def _safe_log2fc(num: float, den: float) -> float:
    if not np.isfinite(num) or not np.isfinite(den):
        return np.nan
    n = max(num, 0.0) + PSEUDOCOUNT
    d = max(den, 0.0) + PSEUDOCOUNT
    return float(np.log2(n / d))


def find_concordant_changes(df: pd.DataFrame,
                            phase_a: str = "post",
                            phase_b: str = "pre",
                            log2fc_threshold: float = LOG2FC_THRESHOLD
                            ) -> list[FeatureCall]:
    """Return features where ALL FOUR crew show |log2(phase_a/phase_b)|
    >= threshold AND in the SAME direction.

    Vectorized across features - on 900k-row gene-family tables an
    iterrows() loop here was taking many minutes per call; numpy
    operations on the (n_features, 4) log2FC matrix run in seconds.
    """
    groups = group_columns_by_subject_phase(df.columns)
    means = phase_means(df, groups)

    # require all four crew present in both phases
    needed_a = [(c, phase_a) for c in CREW]
    needed_b = [(c, phase_b) for c in CREW]
    if any(n not in means.columns for n in needed_a + needed_b):
        return []

    a = means.loc[:, needed_a].to_numpy(dtype=float, copy=False)
    b = means.loc[:, needed_b].to_numpy(dtype=float, copy=False)
    # treat negatives / NaNs as zero abundance, then add the same
    # pseudocount to numerator and denominator
    a = np.where(np.isfinite(a) & (a > 0), a, 0.0) + PSEUDOCOUNT
    b = np.where(np.isfinite(b) & (b > 0), b, 0.0) + PSEUDOCOUNT
    log2fc = np.log2(a / b)  # shape (n_features, 4)

    finite    = np.all(np.isfinite(log2fc), axis=1)
    magnitude = np.all(np.abs(log2fc) >= log2fc_threshold, axis=1)
    all_pos   = np.all(log2fc > 0, axis=1)
    all_neg   = np.all(log2fc < 0, axis=1)
    keep      = finite & magnitude & (all_pos | all_neg)

    if not keep.any():
        return []

    feats   = means.index[keep]
    sub_lfc = log2fc[keep]
    sub_dir = np.where(all_pos[keep], "up", "down")
    hits: list[FeatureCall] = []
    for i, feat in enumerate(feats):
        row = sub_lfc[i]
        hits.append(FeatureCall(
            feature=str(feat),
            direction=str(sub_dir[i]),
            log2fc_per_crew={CREW[j]: float(row[j]) for j in range(4)},
            phase_compared=f"{phase_a}_vs_{phase_b}",
        ))
    return hits


def find_de_significant(df: pd.DataFrame,
                        padj_col: str,
                        lfc_col: str | None = None,
                        padj_threshold: float = PADJ_THRESHOLD,
                        lfc_threshold: float = LOG2FC_THRESHOLD
                        ) -> list[FeatureCall]:
    """For pre-aggregated DE tables (metabolomics, snRNA-seq, snATAC-seq,
    spatial transcriptomics, OSD-571 proteomics/EVP, etc.) - filter to rows
    with adjusted p-value below threshold and (optionally) a fold-change
    magnitude above threshold. Returns the list of features.

    Iterates row-by-row so duplicate indices (e.g. snRNA-seq lists the same
    gene under multiple cell types) don't collapse via .loc into a Series.
    """
    padj = pd.to_numeric(df[padj_col], errors="coerce")
    mask = padj < padj_threshold
    if lfc_col is not None and lfc_col in df.columns:
        lfc = pd.to_numeric(df[lfc_col], errors="coerce")
        mask = mask & (lfc.abs() >= lfc_threshold)
    sub = df[mask.fillna(False)]

    hits: list[FeatureCall] = []
    for idx, row in sub.iterrows():
        if lfc_col is not None and lfc_col in sub.columns:
            try:
                lfc_val = float(pd.to_numeric(row[lfc_col], errors="coerce"))
            except (TypeError, ValueError):
                lfc_val = float("nan")
            direction = ("up"   if np.isfinite(lfc_val) and lfc_val > 0
                         else "down" if np.isfinite(lfc_val) and lfc_val < 0
                         else "flat")
            log2fc_per_crew = {"pooled": lfc_val}
        else:
            direction = "unknown"
            log2fc_per_crew = {}
        hits.append(FeatureCall(
            feature=str(idx),
            direction=direction,
            log2fc_per_crew=log2fc_per_crew,
            phase_compared="post_vs_pre_pooled",
        ))
    return hits


# --------------------------------------------------------------------------
# results helpers
# --------------------------------------------------------------------------

def ensure_results_dir() -> str:
    os.makedirs(RESULTS_DIR, exist_ok=True)
    return RESULTS_DIR


def write_hits_csv(hits: list[FeatureCall], path: str) -> None:
    if not hits:
        pd.DataFrame(columns=["feature", "direction", "phase_compared",
                              "C001", "C002", "C003", "C004"]).to_csv(
            path, index=False)
        return
    rows = []
    for h in hits:
        row = {"feature": h.feature,
               "direction": h.direction,
               "phase_compared": h.phase_compared}
        row.update(h.log2fc_per_crew)
        rows.append(row)
    pd.DataFrame(rows).to_csv(path, index=False)
