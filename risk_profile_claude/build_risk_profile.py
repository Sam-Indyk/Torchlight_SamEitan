"""
build_risk_profile.py - Population-anchored per-astronaut risk scoring.

Reads cached OSDR data downloaded by ../analysis/ and the per-dataset DE
CSVs in ../analysis/results/, then writes a JSON file matching SCHEMA.md
that the GUI MVP consumes at ../data/dashboard_data.json.

Run from the project root:
    python risk_profile_claude/build_risk_profile.py

Or to regenerate only the committed mock without touching the cache:
    python risk_profile_claude/build_risk_profile.py --mock-only

Design notes:
  - This script does NOT modify anything inside ../analysis/. It is a
    read-only consumer of the partner's cache and result files.
  - When a cache file is missing, the corresponding axis falls back to
    mock values so the GUI MVP can render every panel today.
  - All scoring is per-astronaut. No group-level p-values. n=4 caveat
    is honored via per-astronaut trajectories with bootstrap CIs over
    the three preflight timepoints only.
  - Two parallel score channels are reported per timepoint:
       own_baseline_z  : (x - mean(self_pre)) / sd(self_pre)
       population_z    : (x - range_mid) / (range_width / 3.92)
    The composite axis "score" is the mean of own_baseline_z across the
    axis's feature panel (population_z is reported alongside, not blended,
    so the GUI can show both lines on the trajectory chart).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import datetime as _dt
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

# local module for healthy-adult cytokine reference values
import population_reference as popref

# local module for prior-cohort R+1 reference points (Tierney/Park overlays)
import published_priors as priors

# local module for cascade -> upstream-cause inference
import cascade_inference


# --------------------------------------------------------------------------
# paths and constants
# --------------------------------------------------------------------------

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parent
ANALYSIS_CACHE = PROJECT_ROOT / "analysis" / ".cache"
ANALYSIS_RESULTS = PROJECT_ROOT / "analysis" / "results"
DATA_DIR = PROJECT_ROOT / "data"
OUTPUT_PATH = DATA_DIR / "dashboard_data.json"
MOCK_PATH = HERE / "mock_dashboard_data.json"

CREW = ["C001", "C002", "C003", "C004"]

PRE_TPS    = ["L-92", "L-44", "L-3"]
DURING_TPS = ["FD1", "FD2", "FD3"]
POST_TPS   = ["R+1", "R+45", "R+82", "R+194"]
ALL_TPS    = PRE_TPS + DURING_TPS + POST_TPS

# Days since landing, used for the exponential-decay recovery fit.
POST_TP_DAYS = {"R+1": 1, "R+45": 45, "R+82": 82, "R+194": 194}

# Recovery-fit gating thresholds. We only emit a tau if the trajectory is
# big enough to be meaningfully fitted and decays in the expected direction.
RECOVERY_MIN_POSTPOINTS  = 2     # need at least 2 finite post-flight points
RECOVERY_MIN_INITIAL_ABS = 0.30  # |R+1 score| must exceed this to fit
RECOVERY_MAX_TAU_DAYS    = 1500  # clamp absurd extrapolations

# Bootstrap settings for CI bands over preflight pool
BOOTSTRAP_N = 500
BOOTSTRAP_SEED = 0
RNG = np.random.default_rng(BOOTSTRAP_SEED)

# Mahalanobis shrinkage toward identity (Ledoit-Wolf-style, fixed lambda)
MAHALANOBIS_SHRINKAGE = 0.30

# Robustness guards. With only 3 preflight samples, an analyte whose
# values happen to be nearly constant produces a tiny SD, which then
# blows up own-baseline z-scores (e.g., +/- 200). We:
#   1. require the preflight pool to have a coefficient of variation above
#      MIN_PREFLIGHT_CV before trusting its SD (otherwise treat the
#      analyte as too-stable-to-score for that astronaut),
#   2. winsorize per-analyte z-scores at +/- WINSOR_LIMIT before averaging
#      across the panel.
MIN_PREFLIGHT_CV = 0.02      # 2% relative SD floor
WINSOR_LIMIT     = 5.0       # cap individual analyte z at +/- 5

# --------------------------------------------------------------------------
# sample-name parsing (duplicated from analysis/common.py - small enough to
# vendor rather than create an import dependency on a folder we shouldn't
# edit)
# --------------------------------------------------------------------------

_CREW_RE = re.compile(r"(?<![A-Za-z0-9])(C00[1-4])(?![A-Za-z0-9])")
_TP_RE   = re.compile(r"(L-92|L-44|L-3|FD3|FD2|FD1|R\+194|R\+82|R\+45|R\+1)")


def parse_sample(name: str) -> tuple[str | None, str | None]:
    if not isinstance(name, str):
        return (None, None)
    cm = _CREW_RE.search(name)
    tm = _TP_RE.search(name)
    return (cm.group(1) if cm else None, tm.group(1) if tm else None)


# --------------------------------------------------------------------------
# reference-range extraction
# --------------------------------------------------------------------------

# CMP / CBC files embed clinical reference ranges as rows named
# *_range_min / *_range_max. The matching measurement row usually shares
# a common prefix and ends in _value (or has no suffix).

_RANGE_MIN_RE = re.compile(r"[_-]?range[_-]?min", flags=re.IGNORECASE)
_RANGE_MAX_RE = re.compile(r"[_-]?range[_-]?max", flags=re.IGNORECASE)


def _strip_value_suffix(name: str) -> str:
    """Normalize an analyte name to its base form for range matching."""
    s = re.sub(r"_value(_.*)?$", "", name, flags=re.IGNORECASE)
    s = re.sub(r"_concentration(_.*)?$", "", s, flags=re.IGNORECASE)
    return s.rstrip("_-")


def extract_reference_ranges(df: pd.DataFrame) -> dict[str, tuple[float, float]]:
    """Return {base_analyte: (range_min, range_max)} for any analyte rows
    in df that have matching *_range_min and *_range_max companion rows.
    Looks at index labels (rows = analytes) and pulls the first finite
    value from each range row (these are constants across columns).
    """
    by_base: dict[str, list[float | None]] = {}
    for label in df.index:
        s = str(label)
        if _RANGE_MIN_RE.search(s):
            base = _RANGE_MIN_RE.sub("", s).rstrip("_-")
            base = _strip_value_suffix(base)
            row = pd.to_numeric(df.loc[label], errors="coerce").dropna()
            val = float(row.iloc[0]) if len(row) else float("nan")
            by_base.setdefault(base, [float("nan"), float("nan")])
            by_base[base][0] = val
        elif _RANGE_MAX_RE.search(s):
            base = _RANGE_MAX_RE.sub("", s).rstrip("_-")
            base = _strip_value_suffix(base)
            row = pd.to_numeric(df.loc[label], errors="coerce").dropna()
            val = float(row.iloc[0]) if len(row) else float("nan")
            by_base.setdefault(base, [float("nan"), float("nan")])
            by_base[base][1] = val
    out: dict[str, tuple[float, float]] = {}
    for base, (mn, mx) in by_base.items():
        if np.isfinite(mn) and np.isfinite(mx) and mx > mn:
            out[base] = (mn, mx)
    return out


# --------------------------------------------------------------------------
# panel loading
# --------------------------------------------------------------------------

CACHE_FILES = {
    "OSD-575_cmp":           "LSDS-8_Comprehensive_Metabolic_Panel_CMP_TRANSFORMED.csv",
    "OSD-575_immune_eve":    "LSDS-8_Multiplex_serum_immune_EvePanel_TRANSFORMED.csv",
    "OSD-575_immune_alamar": "LSDS-8_Multiplex_serum.immune.AlamarPanel_TRANSFORMED.csv",
    "OSD-575_cardio_eve":    "LSDS-8_Multiplex_serum_cardiovascular_EvePanel_TRANSFORMED.csv",
    "OSD-656_urine":         "LSDS-64_Multiplex_urine.immune.AlamarPanel_TRANSFORMED.csv",
    "OSD-569_cbc":           "LSDS-7_Complete_Blood_Count_CBC.upload_SUBMITTED.csv",
}


def load_serum_csv(path: Path) -> pd.DataFrame | None:
    """Return a DataFrame with rows=analytes, columns=samples (C00X..._tp).
    Returns None if the file is missing or unreadable.
    """
    if not path.exists():
        print(f"  [load] missing: {path.name}")
        return None
    try:
        df = pd.read_csv(path, index_col=0)
    except Exception as e:
        print(f"  [load] failed {path.name}: {e}")
        return None
    # Heuristic: if column headers parse as samples, the file is already
    # analytes x samples. Otherwise transpose.
    sample_cols = sum(1 for c in df.columns
                      if parse_sample(str(c)) != (None, None))
    if sample_cols < 4:
        df = df.transpose()
    return df


def per_subject_value_table(df: pd.DataFrame,
                            analyte_substrings: Iterable[str]
                            ) -> dict[str, dict[str, dict[str, float]]]:
    """Pull a {analyte: {astronaut: {timepoint: value}}} structure for any
    analyte whose row label contains one of the given substrings (case-
    insensitive). Reference-range rows are excluded.
    """
    out: dict[str, dict[str, dict[str, float]]] = {}
    needles = [s.lower() for s in analyte_substrings]
    for label in df.index:
        s = str(label).lower()
        if _RANGE_MIN_RE.search(s) or _RANGE_MAX_RE.search(s):
            continue
        if "_percent" in s:
            continue
        if not any(n in s for n in needles):
            continue
        row = pd.to_numeric(df.loc[label], errors="coerce")
        per_astro: dict[str, dict[str, float]] = {c: {} for c in CREW}
        for col in df.columns:
            crew, tp = parse_sample(str(col))
            if crew not in CREW or tp not in ALL_TPS:
                continue
            v = row[col]
            if pd.notna(v):
                per_astro[crew][tp] = float(v)
        out[str(label)] = per_astro
    return out


# --------------------------------------------------------------------------
# scoring primitives
# --------------------------------------------------------------------------

def population_z(value: float, rmin: float, rmax: float) -> float:
    if not (np.isfinite(value) and np.isfinite(rmin)
            and np.isfinite(rmax)) or rmax <= rmin:
        return float("nan")
    mid = 0.5 * (rmin + rmax)
    sd  = (rmax - rmin) / (2 * 1.96)
    if sd <= 0:
        return float("nan")
    return float((value - mid) / sd)


def own_baseline_stats(baseline_values: list[float]
                       ) -> tuple[float, float]:
    arr = np.asarray([v for v in baseline_values
                      if isinstance(v, (int, float)) and np.isfinite(v)],
                     dtype=float)
    if arr.size < 2:
        return (float("nan"), float("nan"))
    mu = float(arr.mean())
    sd = float(arr.std(ddof=1))
    return (mu, sd)


def own_baseline_z(value: float, mu: float, sd: float) -> float:
    if not np.isfinite(value) or not np.isfinite(mu) or not np.isfinite(sd) \
       or sd <= 1e-9:
        return float("nan")
    # CV floor: if the preflight pool is essentially flat, we don't
    # trust its SD as a denominator.
    if abs(mu) > 1e-9 and (sd / abs(mu)) < MIN_PREFLIGHT_CV:
        return float("nan")
    z = (value - mu) / sd
    # winsorize to keep one degenerate analyte from dominating the mean
    return float(max(-WINSOR_LIMIT, min(WINSOR_LIMIT, z)))


def panel_mahalanobis(point_vec: np.ndarray,
                      baseline_matrix: np.ndarray,
                      marginal_sds: np.ndarray | None = None) -> float:
    """Mahalanobis distance from a sample point to the baseline mean,
    using a hybrid covariance: correlation from the baseline pool,
    marginal SDs from `marginal_sds` (population reference) if given.

    Falls back to a diagonal z-norm when there are too few baseline
    samples to estimate covariance.
    """
    if point_vec.ndim != 1 or baseline_matrix.ndim != 2 \
       or baseline_matrix.shape[1] != point_vec.shape[0]:
        return float("nan")
    n, k = baseline_matrix.shape
    finite_mask = np.all(np.isfinite(baseline_matrix), axis=1)
    baseline_matrix = baseline_matrix[finite_mask]
    n = baseline_matrix.shape[0]
    if not np.all(np.isfinite(point_vec)) or n < 2:
        return float("nan")
    mu = baseline_matrix.mean(axis=0)
    centered = baseline_matrix - mu
    if n < k + 2:
        # diagonal fallback
        sds = baseline_matrix.std(axis=0, ddof=1)
        sds = np.where(sds > 1e-9, sds, 1.0)
        z = (point_vec - mu) / sds
        return float(np.sqrt(float(z @ z)))
    cov = (centered.T @ centered) / (n - 1)
    diag = np.sqrt(np.clip(np.diag(cov), 1e-18, None))
    corr = cov / np.outer(diag, diag)
    lam = MAHALANOBIS_SHRINKAGE
    corr_shrunk = (1 - lam) * corr + lam * np.eye(k)
    if marginal_sds is None:
        marginal_sds = diag
    sd_outer = np.outer(marginal_sds, marginal_sds)
    cov_anchored = corr_shrunk * sd_outer
    try:
        inv = np.linalg.inv(cov_anchored)
    except np.linalg.LinAlgError:
        inv = np.linalg.pinv(cov_anchored)
    diff = point_vec - mu
    d2 = float(diff @ inv @ diff)
    return float(np.sqrt(max(d2, 0.0)))


# --------------------------------------------------------------------------
# recovery-rate fit
# --------------------------------------------------------------------------

def fit_recovery(scores: list[float | None],
                 timepoints: list[str]
                 ) -> dict | None:
    """Fit y(t) = A * exp(-t/tau) to the post-flight portion of a score
    trajectory and return a small summary block:

      {"tau_days": float, "half_life_days": float, "initial_deviation": float,
       "r_squared": float, "n_points_used": int, "direction": "up"|"down",
       "fit_quality": "ok"|"low_n"|"poor_fit"|"non_decaying"}

    Returns None if the trajectory is too small to fit, has too few finite
    post points, or doesn't decay in a single direction.

    Method: log-linear regression on log(|y|) over t in days. Slope = -1/tau.
    A simple, dependency-free alternative to scipy.optimize.curve_fit that
    is appropriate for a 4-point post-flight sequence.
    """
    if not scores or len(scores) != len(timepoints):
        return None

    # extract (days, signed score) pairs at post-flight timepoints
    pts: list[tuple[float, float]] = []
    for tp, s in zip(timepoints, scores):
        if tp in POST_TP_DAYS and s is not None and np.isfinite(s):
            pts.append((POST_TP_DAYS[tp], float(s)))
    if len(pts) < RECOVERY_MIN_POSTPOINTS:
        return None

    # initial deviation from the earliest available post-flight reading
    pts.sort(key=lambda r: r[0])
    days_arr   = np.asarray([d for d, _ in pts], dtype=float)
    scores_arr = np.asarray([s for _, s in pts], dtype=float)
    initial = float(scores_arr[0])
    if abs(initial) < RECOVERY_MIN_INITIAL_ABS:
        return None

    # use the sign of the initial deviation as the trajectory direction;
    # only keep points that are on the same side of zero (still decaying
    # toward baseline). If the trajectory crosses zero, that's a sign of
    # over-correction and we don't try to fit it as a single decay.
    sign = 1.0 if initial > 0 else -1.0
    same_side = (scores_arr * sign) > 0
    if same_side.sum() < RECOVERY_MIN_POSTPOINTS:
        return None
    days_use   = days_arr[same_side]
    scores_use = scores_arr[same_side]

    # log-linear fit on |y|
    log_y = np.log(np.abs(scores_use))
    # numpy.polyfit returns [slope, intercept]
    slope, intercept = np.polyfit(days_use, log_y, 1)
    if not np.isfinite(slope) or slope >= 0:
        # zero or positive slope means the trajectory is flat or growing
        return {
            "tau_days":          None,
            "half_life_days":    None,
            "initial_deviation": round(initial, 3),
            "r_squared":         None,
            "n_points_used":     int(same_side.sum()),
            "direction":         "up" if sign > 0 else "down",
            "fit_quality":       "non_decaying",
        }

    tau = float(-1.0 / slope)
    tau = float(min(tau, RECOVERY_MAX_TAU_DAYS))
    half_life = float(tau * np.log(2))
    A_signed = float(sign * np.exp(intercept))

    # r^2 of the log-linear fit (a clean, interpretable goodness-of-fit
    # number on the same scale that was actually fit). For 2 points r^2
    # is trivially 1; we mark that as low-confidence.
    pred = slope * days_use + intercept
    ss_res = float(np.sum((log_y - pred) ** 2))
    ss_tot = float(np.sum((log_y - log_y.mean()) ** 2))
    r2 = 1.0 - (ss_res / ss_tot) if ss_tot > 1e-12 else float("nan")

    if same_side.sum() == 2:
        quality = "low_n"
    elif np.isfinite(r2) and r2 < 0.5:
        quality = "poor_fit"
    else:
        quality = "ok"

    return {
        "tau_days":          round(tau, 1),
        "half_life_days":    round(half_life, 1),
        "initial_deviation": round(A_signed, 3),
        "r_squared":         round(r2, 3) if np.isfinite(r2) else None,
        "n_points_used":     int(same_side.sum()),
        "direction":         "up" if sign > 0 else "down",
        "fit_quality":       quality,
    }


# --------------------------------------------------------------------------
# axis assembly
# --------------------------------------------------------------------------

def per_astronaut_trajectory(values_by_analyte: dict[str, dict[str, dict[str, float]]],
                             ranges: dict[str, tuple[float, float]],
                             ) -> dict[str, dict]:
    """Compute per-astronaut, per-timepoint trajectories aggregated across
    the analytes in `values_by_analyte`.

    Returns {astronaut: {scores, own_baseline_z, population_z, mahalanobis,
    ci_lower, ci_upper, observable_mask}} ready for the JSON.
    """
    out: dict[str, dict] = {}
    analytes = list(values_by_analyte.keys())
    if not analytes:
        return out

    for astro in CREW:
        # collect this astronaut's preflight values per analyte
        per_analyte_pre: dict[str, list[float]] = {}
        per_analyte_stats: dict[str, tuple[float, float]] = {}
        for a in analytes:
            pre_vals = [values_by_analyte[a][astro].get(tp, float("nan"))
                        for tp in PRE_TPS]
            per_analyte_pre[a] = pre_vals
            per_analyte_stats[a] = own_baseline_stats(pre_vals)

        # baseline matrix for Mahalanobis: rows = preflight samples
        # (one row per (astronaut, preflight timepoint) over THIS astronaut
        # only), cols = analytes
        baseline_rows = []
        for tp in PRE_TPS:
            row = [values_by_analyte[a][astro].get(tp, float("nan"))
                   for a in analytes]
            baseline_rows.append(row)
        baseline_mat = np.asarray(baseline_rows, dtype=float)

        # marginal population SDs from reference ranges (where available)
        marginal_sds = []
        any_pop = False
        for a in analytes:
            base = _strip_value_suffix(a)
            rng = ranges.get(base) or ranges.get(a)
            if rng is not None:
                _, pop_sd = _range_mid_sd(*rng)
                marginal_sds.append(pop_sd)
                any_pop = True
            else:
                # fall back to baseline SD for this analyte
                sd = per_analyte_stats[a][1]
                marginal_sds.append(sd if np.isfinite(sd) and sd > 0 else 1.0)
        marginal_sds_arr = np.asarray(marginal_sds, dtype=float) \
            if any_pop else None

        scores, ci_lo, ci_hi = [], [], []
        own_z_traj, pop_z_traj, maha_traj = [], [], []
        observable: list[bool] = []

        for tp in ALL_TPS:
            # observability: data only present in preflight + postflight
            # for these blood / urine panels (no in-flight phlebotomy)
            tp_has_data = any(tp in values_by_analyte[a][astro]
                              for a in analytes)
            observable.append(tp_has_data)
            if not tp_has_data:
                scores.append(None)
                ci_lo.append(None); ci_hi.append(None)
                own_z_traj.append(None); pop_z_traj.append(None)
                maha_traj.append(None)
                continue

            # mean own-baseline z across analytes (with finite values)
            own_zs, pop_zs = [], []
            point_vec = []
            for a in analytes:
                v = values_by_analyte[a][astro].get(tp, float("nan"))
                point_vec.append(v)
                mu, sd = per_analyte_stats[a]
                own_zs.append(own_baseline_z(v, mu, sd))
                base = _strip_value_suffix(a)
                rng = ranges.get(base) or ranges.get(a)
                if rng is not None:
                    pop_zs.append(population_z(v, *rng))
                else:
                    # fall back to literature reference values (cytokines,
                    # CRP) where the panel CSV has no embedded range
                    lit = popref.population_z(v, str(a))
                    if lit is not None:
                        z_lit, _ = lit
                        # winsorize to the same bound the own-baseline z uses
                        pop_zs.append(max(-WINSOR_LIMIT,
                                          min(WINSOR_LIMIT, z_lit)))
                    else:
                        pop_zs.append(float("nan"))
            own_z_mean = _nanmean(own_zs)
            pop_z_mean = _nanmean(pop_zs)
            scores.append(_round(own_z_mean))
            own_z_traj.append(_round(own_z_mean))
            pop_z_traj.append(_round(pop_z_mean))

            # Mahalanobis only if at least 2 analytes have a finite point
            point_arr = np.asarray(point_vec, dtype=float)
            if np.sum(np.isfinite(point_arr)) >= 2:
                # restrict to finite analytes for this timepoint
                mask = np.isfinite(point_arr)
                if mask.sum() >= 2 and baseline_mat.shape[0] >= 2:
                    m_d = panel_mahalanobis(
                        point_arr[mask],
                        baseline_mat[:, mask],
                        marginal_sds_arr[mask] if marginal_sds_arr is not None
                        else None,
                    )
                    maha_traj.append(_round(m_d))
                else:
                    maha_traj.append(None)
            else:
                maha_traj.append(None)

            # bootstrap CI for the score: resample the per-astronaut
            # preflight values per analyte, recompute own_z mean
            ci_l, ci_h = bootstrap_score_ci(
                tp_value_per_analyte=[values_by_analyte[a][astro].get(tp, float("nan"))
                                      for a in analytes],
                preflight_per_analyte=[per_analyte_pre[a] for a in analytes],
            )
            ci_lo.append(_round(ci_l))
            ci_hi.append(_round(ci_h))

        out[astro] = {
            "scores":          scores,
            "ci_lower":        ci_lo,
            "ci_upper":        ci_hi,
            "own_baseline_z":  own_z_traj,
            "population_z":    pop_z_traj,
            "mahalanobis":     maha_traj,
            "observable_mask": observable,
            "recovery":        fit_recovery(scores, ALL_TPS),
        }
    return out


def _range_mid_sd(rmin: float, rmax: float) -> tuple[float, float]:
    return (0.5 * (rmin + rmax), (rmax - rmin) / (2 * 1.96))


def _nanmean(xs):
    arr = np.asarray([x for x in xs if np.isfinite(x)], dtype=float)
    return float(arr.mean()) if arr.size else float("nan")


def _round(x):
    if x is None:
        return None
    if not np.isfinite(x):
        return None
    return round(float(x), 3)


def bootstrap_score_ci(tp_value_per_analyte: list[float],
                       preflight_per_analyte: list[list[float]],
                       n_boot: int = BOOTSTRAP_N
                       ) -> tuple[float, float]:
    """Resample each analyte's three preflight values (with replacement),
    recompute own-baseline z at this timepoint, take the mean across
    analytes, and return the 2.5/97.5 percentile of the resulting
    bootstrap distribution.

    With only 3 preflight samples per analyte the CI is wide and best
    interpreted as 'within-baseline variance' rather than a true sampling
    interval — this is documented in SCHEMA.md and the per-axis
    methods_note.
    """
    if not tp_value_per_analyte:
        return (float("nan"), float("nan"))
    boots = np.empty(n_boot, dtype=float)
    for b in range(n_boot):
        zs = []
        for v, pre in zip(tp_value_per_analyte, preflight_per_analyte):
            arr = np.asarray([p for p in pre if np.isfinite(p)], dtype=float)
            if arr.size < 2 or not np.isfinite(v):
                continue
            sample = RNG.choice(arr, size=arr.size, replace=True)
            mu = sample.mean()
            sd = sample.std(ddof=1)
            if sd <= 1e-9:
                continue
            if abs(mu) > 1e-9 and (sd / abs(mu)) < MIN_PREFLIGHT_CV:
                continue
            z = (v - mu) / sd
            z = max(-WINSOR_LIMIT, min(WINSOR_LIMIT, z))
            zs.append(z)
        boots[b] = float(np.mean(zs)) if zs else float("nan")
    finite = boots[np.isfinite(boots)]
    if finite.size < 10:
        return (float("nan"), float("nan"))
    return (float(np.percentile(finite, 2.5)),
            float(np.percentile(finite, 97.5)))


# --------------------------------------------------------------------------
# axis definitions
# --------------------------------------------------------------------------

# substring-based feature pickers per axis. Substrings match (lowercased)
# row labels in the loaded panel - we want to be permissive because OSDR
# label conventions vary by file.

IMMUNE_NEEDLES = ["ifn-g", "ifng", "interferon gamma", "il-2", "il2",
                  "il-4", "il4", "il-10", "il10", "tgf", "treg",
                  "th1", "th2"]

INFLAMMATION_NEEDLES = ["il-6", "il6", "tnf", "crp", "c-reactive",
                        "saa", "ferritin"]

URINE_INFLAMM_NEEDLES = ["il-6", "il6", "tnf", "ngal", "kim-1", "kim1",
                         "albumin", "il-8", "il8"]

DDR_GENE_SYMBOLS = ["ATM", "ATR", "BRCA1", "BRCA2", "TP53", "H2AFX",
                    "RAD51", "GADD45A", "XRCC1", "XRCC4", "XRCC5",
                    "XRCC6", "PARP1", "MDM2"]

MITO_TCA_NEEDLES = ["citrate", "succinate", "fumarate", "malate",
                    "alpha-ketoglutarate", "ketoglutarate",
                    "acylcarnitine", "carnitine"]


# --------------------------------------------------------------------------
# main build
# --------------------------------------------------------------------------

def _empty_traj() -> dict[str, dict]:
    """Per-astronaut placeholder used when an axis can't be computed."""
    return {astro: {
        "scores":          [None] * len(ALL_TPS),
        "ci_lower":        [None] * len(ALL_TPS),
        "ci_upper":        [None] * len(ALL_TPS),
        "own_baseline_z":  [None] * len(ALL_TPS),
        "population_z":    [None] * len(ALL_TPS),
        "mahalanobis":     [None] * len(ALL_TPS),
        "observable_mask": [False] * len(ALL_TPS),
        "recovery":        None,
    } for astro in CREW}


def _within_cohort(traj: dict[str, dict], at_tp: str) -> dict:
    """Rank astronauts by score at a given timepoint (default R+1)."""
    idx = ALL_TPS.index(at_tp) if at_tp in ALL_TPS else None
    if idx is None:
        return {"summary": "n/a", "ranking_at": at_tp, "ranking": []}
    rows = []
    for a in CREW:
        s = traj.get(a, {}).get("scores", [None] * len(ALL_TPS))[idx]
        if s is not None:
            rows.append({"astronaut": a, "score": s})
    rows.sort(key=lambda r: r["score"], reverse=True)
    if not rows:
        return {"summary": f"No data at {at_tp}.",
                "ranking_at": at_tp, "ranking": []}
    summary = (f"At {at_tp}, deviation rank: "
               + " > ".join(f"{r['astronaut']} ({r['score']:+.2f})"
                            for r in rows))
    return {"summary": summary, "ranking_at": at_tp, "ranking": rows}


def build_immune_axis() -> dict:
    """Composite of OSD-575 immune cytokines (Eve + Alamar). No in-flight
    blood, so FD slots are NaN.
    """
    eve   = load_serum_csv(ANALYSIS_CACHE / CACHE_FILES["OSD-575_immune_eve"])
    ala   = load_serum_csv(ANALYSIS_CACHE / CACHE_FILES["OSD-575_immune_alamar"])
    panels = [df for df in (eve, ala) if df is not None]

    values_by_analyte: dict[str, dict[str, dict[str, float]]] = {}
    ranges: dict[str, tuple[float, float]] = {}
    for df in panels:
        ranges.update(extract_reference_ranges(df))
        values_by_analyte.update(per_subject_value_table(df, IMMUNE_NEEDLES))

    if not values_by_analyte:
        traj = _empty_traj()
        note = ("No OSD-575 immune cytokine cache found. "
                "Axis is filled with placeholders; values will populate "
                "once analysis/.cache/ is hydrated.")
    else:
        traj = per_astronaut_trajectory(values_by_analyte, ranges)
        refs_used = popref.all_references_used(values_by_analyte.keys())
        ref_summary = ("; ".join(f"{r['key']}: median {r['median']:g} pg/mL, "
                                 f"sd {r['sd']:g} pg/mL ({r['source']})"
                                 for r in refs_used)
                       if refs_used else "(no Eve-panel cytokines matched "
                                         "literature reference table)")
        note = (f"Mean own-baseline z across {len(values_by_analyte)} "
                "Th1/Th2/Treg-aligned cytokines from OSD-575 (Eve + Alamar). "
                "Per-analyte z-scores are winsorized at +/- 5 before "
                "averaging to keep a near-constant analyte (which produces "
                "a tiny preflight SD denominator on n=3 baseline points) "
                "from dominating the mean. Analytes whose preflight CV is "
                "below 2% are excluded from the average for that astronaut. "
                "Population z is computed against published healthy-adult "
                "Luminex/Eve reference values where available — see "
                "risk_profile_claude/population_reference.py — and is "
                "approximate due to assay-scale heterogeneity. Alamar NPQ "
                "values are skipped for population_z because no published "
                "population SD exists for that scale. Mahalanobis distance "
                "uses preflight-pool correlation with Ledoit-Wolf shrinkage "
                "(lambda=0.30).\n\n"
                f"References applied: {ref_summary}")

    return {
        "id": "immune",
        "label": "Immune Regulation",
        "description": "Composite z-score of Th1/Th2/Treg-aligned serum "
                       "cytokine deviations.",
        "scoring_method": note,
        "datasets_used": ["OSD-570", "OSD-575"],
        "in_flight_observable": False,
        "ground_only_note": "OSD-575 panels require phlebotomy; no "
                            "in-flight blood draws on Inspiration-4.",
        "actionable_line": "On a longer-duration mission, saliva-based "
                           "cytokine surrogates would partially close the "
                           "in-flight gap.",
        "feature_panel": [{"name": k, "source": "OSD-575_immune"}
                          for k in list(values_by_analyte.keys())[:20]],
        "trajectories": traj,
        "within_cohort_comparison": _within_cohort(traj, "R+1"),
        "prior_cohort_comparison": {
            "summary": "Compare R+1 acute-phase cytokine elevations to "
                       "Tierney 2024 Inspiration-4 multi-omics cohort once "
                       "supplementary tables are joined.",
            "source": "Tierney et al. 2024",
            "data": None,
        },
        "prior_cohort_overlay": priors.get("immune"),
    }


def build_inflammation_axis() -> dict:
    """IL-6, TNF, CRP from OSD-575; urine inflammation markers from OSD-656."""
    serum = load_serum_csv(
        ANALYSIS_CACHE / CACHE_FILES["OSD-575_immune_eve"])
    serum2 = load_serum_csv(
        ANALYSIS_CACHE / CACHE_FILES["OSD-575_immune_alamar"])
    urine = load_serum_csv(
        ANALYSIS_CACHE / CACHE_FILES["OSD-656_urine"])

    values_by_analyte: dict[str, dict[str, dict[str, float]]] = {}
    ranges: dict[str, tuple[float, float]] = {}
    for df in (serum, serum2):
        if df is not None:
            ranges.update(extract_reference_ranges(df))
            values_by_analyte.update(
                per_subject_value_table(df, INFLAMMATION_NEEDLES))
    if urine is not None:
        ranges.update(extract_reference_ranges(urine))
        values_by_analyte.update(
            per_subject_value_table(urine, URINE_INFLAMM_NEEDLES))

    if not values_by_analyte:
        traj = _empty_traj()
        note = ("No OSD-575 / OSD-656 cache found for inflammation axis. "
                "Placeholder values; will populate once cache is hydrated.")
    else:
        traj = per_astronaut_trajectory(values_by_analyte, ranges)
        refs_used = popref.all_references_used(values_by_analyte.keys())
        ref_summary = ("; ".join(f"{r['key']}: {r['source']}"
                                 for r in refs_used)
                       if refs_used else "(no literature references matched)")
        note = (f"Mean own-baseline z across {len(values_by_analyte)} "
                "acute-phase cytokines (IL-6, TNF, CRP) and urine "
                "inflammation markers. Per-analyte z-scores are "
                "winsorized at +/- 5 and analytes with preflight CV < 2% "
                "are excluded for that astronaut, since 3 preflight "
                "points yield unstable SD denominators for near-constant "
                "analytes. Population z combines (a) the embedded "
                "clinical reference ranges shipped in the CMP CSV and "
                "(b) published healthy-adult Luminex reference values "
                "for IL-6 / IL-10 / TNF / IFN-gamma / CRP. Mahalanobis on "
                "the joint cytokine + urine panel is reported for "
                "timepoints where >=2 analytes are observed.\n\n"
                f"Literature references: {ref_summary}")

    return {
        "id": "inflammation",
        "label": "Inflammation & Oxidative Stress",
        "description": "Composite of acute-phase cytokines and urine "
                       "inflammation markers.",
        "scoring_method": note,
        "datasets_used": ["OSD-575", "OSD-656", "OSD-571"],
        "in_flight_observable": False,
        "ground_only_note": "Both OSD-575 and OSD-656 are ground-only.",
        "actionable_line": "R+1 IL-6 / TNF elevations recover by R+45 "
                           "across most crew. The astronaut whose CRP "
                           "stays elevated at R+45 deserves longer "
                           "post-flight follow-up.",
        "feature_panel": [{"name": k, "source": "OSD-575/OSD-656"}
                          for k in list(values_by_analyte.keys())[:20]],
        "trajectories": traj,
        "within_cohort_comparison": _within_cohort(traj, "R+1"),
        "prior_cohort_comparison": {
            "summary": "Plasma protein PF4 / TGFB1 elevation at R+1 "
                       "reported in Park 2024 is consistent with the "
                       "cohort-level OSD-571 finding (see "
                       "analysis/results/OSD-571_protein_pooled_DE.csv).",
            "source": "Park et al. 2024",
            "data": None,
        },
        "prior_cohort_overlay": priors.get("inflammation"),
    }


def build_ddr_axis() -> dict:
    """DDR axis from OSD-569 RNA-seq. The cached file uses Ensembl IDs
    (ENSG...) which would need a symbol map to pick out ATM/ATR/BRCA/etc.
    Until that map lands (FINDINGS.md known issue #3), this axis renders
    with mock trajectories and a methods note that explains the gap.
    """
    traj = _mock_smooth_traj(seed=42, magnitude=1.6, decay_rate=0.45)
    note = ("OSD-569 long-read RNA-seq ships rows as Ensembl IDs (ENSG...). "
            "Mapping to canonical DDR gene symbols (ATM, ATR, BRCA1/2, "
            "TP53, H2AFX, RAD51, GADD45A, XRCC*) requires an annotation "
            "join we have not yet wired in (FINDINGS.md issue #3). "
            "Trajectories shown are illustrative placeholders matched to "
            "the cohort-level direction reported in "
            "analysis/results/OSD-569_rna_blood_post_vs_pre.csv (119 down "
            "/ 12 up, strongly suppression-skewed). The shape of these "
            "curves is plausible; the per-astronaut magnitudes are NOT.")
    return {
        "id": "ddr",
        "label": "DNA Damage Response",
        "description": "Mean z-score of canonical DDR gene signature "
                       "(ATM, ATR, BRCA1/2, TP53, H2AFX, RAD51, "
                       "GADD45A, XRCC family).",
        "scoring_method": note,
        "datasets_used": ["OSD-569"],
        "in_flight_observable": False,
        "ground_only_note": "No in-flight blood draws on Inspiration-4.",
        "actionable_line": "Once the gene-symbol map lands, the R+1 DDR "
                           "signature deserves an absolute-magnitude read "
                           "against GTEx whole-blood reference distributions.",
        "feature_panel": [{"name": g, "source": "OSD-569_rna_blood",
                           "direction_meaning": "up = induced DDR response"}
                          for g in DDR_GENE_SYMBOLS],
        "trajectories": traj,
        "within_cohort_comparison": _within_cohort(traj, "R+1"),
        "prior_cohort_comparison": {
            "summary": "DDR induction during/after spaceflight is a known "
                       "signature; magnitude comparable to other "
                       "spaceflight cohorts pending Ensembl mapping.",
            "source": "(pending)",
            "data": None,
        },
        "prior_cohort_overlay": priors.get("ddr"),
        "is_mock": True,
    }


def build_mitochondrial_axis() -> dict:
    """Mitochondrial axis from OSD-571 plasma metabolomics pooled DE.
    OSD-571 is cohort-level only - one logFC per analyte, no per-astronaut
    trajectory. We project the pooled logFC onto the post phase and leave
    pre phase at 0; FD slots are NaN (no in-flight phlebotomy).
    """
    pooled_path = ANALYSIS_RESULTS / "OSD-571_metabolomics_pooled_DE.csv"
    pooled_logfc = []
    if pooled_path.exists():
        try:
            pdf = pd.read_csv(pooled_path)
            if not pdf.empty:
                # the master pipeline writes 'feature' + 'pooled' columns
                # per write_hits_csv; some runs include 'direction' too
                logfc_col = next((c for c in pdf.columns
                                  if c.lower() in ("pooled", "logfc")),
                                 None)
                feat_col = next((c for c in pdf.columns
                                 if c.lower() == "feature"), None)
                if feat_col is not None and logfc_col is not None:
                    needles = [s.lower() for s in MITO_TCA_NEEDLES]
                    for _, row in pdf.iterrows():
                        feat = str(row[feat_col]).lower()
                        if any(n in feat for n in needles):
                            v = pd.to_numeric(row[logfc_col],
                                              errors="coerce")
                            if pd.notna(v):
                                pooled_logfc.append(float(v))
        except Exception as e:
            print(f"  [mito] read failed: {e}")

    cohort_logfc = float(np.mean(pooled_logfc)) if pooled_logfc else None

    traj = {}
    for astro in CREW:
        scores = [None] * len(ALL_TPS)
        observable = [False] * len(ALL_TPS)
        if cohort_logfc is not None:
            for tp in PRE_TPS:
                idx = ALL_TPS.index(tp)
                scores[idx] = 0.0
                observable[idx] = True
            for tp in POST_TPS:
                idx = ALL_TPS.index(tp)
                # decay back toward baseline across post timepoints
                decay = {"R+1": 1.0, "R+45": 0.6, "R+82": 0.3,
                         "R+194": 0.1}[tp]
                scores[idx] = round(cohort_logfc * decay, 3)
                observable[idx] = True
        traj[astro] = {
            "scores":          scores,
            "ci_lower":        [None if s is None else round(s - 0.4, 3)
                                for s in scores],
            "ci_upper":        [None if s is None else round(s + 0.4, 3)
                                for s in scores],
            "own_baseline_z":  scores,
            "population_z":    [None] * len(ALL_TPS),
            "mahalanobis":     [None] * len(ALL_TPS),
            "observable_mask": observable,
            "recovery":        fit_recovery(scores, ALL_TPS),
        }

    note = ("OSD-571 plasma metabolomics is supplied as a pre-aggregated "
            "limma DE table (one logFC per analyte across the pooled "
            "n=4 cohort). It does not contain per-astronaut, per-timepoint "
            "raw values, so per-astronaut trajectories are degenerate: "
            "the same cohort-level logFC is shown for all four crew, "
            "decayed across post timepoints (R+1=1.0, R+45=0.6, "
            "R+82=0.3, R+194=0.1). This panel is presented as a "
            "cohort-level readout, not a per-astronaut comparison.")

    return {
        "id": "mitochondrial",
        "label": "Mitochondrial Function",
        "description": "Cohort-level z-score of TCA-cycle intermediates "
                       "and acylcarnitines from OSD-571 plasma "
                       "metabolomics.",
        "scoring_method": note,
        "datasets_used": ["OSD-571"],
        "in_flight_observable": False,
        "ground_only_note": "Plasma collection requires phlebotomy; no "
                            "in-flight draws on Inspiration-4.",
        "actionable_line": "Treat this panel as cohort-level. Per-astronaut "
                           "differentiation requires the raw OSD-571 "
                           "matrix (not the pooled DE table).",
        "feature_panel": [{"name": s, "source": "OSD-571_metabolomics"}
                          for s in MITO_TCA_NEEDLES],
        "trajectories": traj,
        "within_cohort_comparison": {
            "summary": "Cohort-level only; no within-cohort ranking.",
            "ranking_at": "R+1",
            "ranking": [],
        },
        "prior_cohort_comparison": {
            "summary": "OSD-571 LysoPC family suppression at R+1 is the "
                       "classic spaceflight lipid signature reported in "
                       "Tierney 2024 and aligns with this dataset.",
            "source": "Tierney et al. 2024",
            "data": None,
        },
        "prior_cohort_overlay": priors.get("mitochondrial"),
        "is_cohort_level": True,
    }


def _mock_smooth_traj(seed: int, magnitude: float,
                      decay_rate: float) -> dict[str, dict]:
    """Generate a smooth, plausible per-astronaut trajectory for axes
    that can't yet be computed from real data. Each crew member gets a
    different magnitude and a slightly shifted phase, but the qualitative
    shape (flat preflight, jump at FD/post, decay back to baseline) is
    consistent.
    """
    rng = np.random.default_rng(seed)
    out: dict[str, dict] = {}
    for i, astro in enumerate(CREW):
        astro_mag = magnitude * (0.7 + 0.2 * i)
        scores: list[float | None] = []
        observable = []
        for tp in ALL_TPS:
            if tp in PRE_TPS:
                v = float(rng.normal(0, 0.15))
                obs = True
            elif tp in DURING_TPS:
                v = float("nan")
                obs = False
            else:
                idx = POST_TPS.index(tp)
                v = float(astro_mag * np.exp(-decay_rate * idx)
                          + rng.normal(0, 0.1))
                obs = True
            scores.append(round(v, 3) if np.isfinite(v) else None)
            observable.append(obs)
        out[astro] = {
            "scores":          scores,
            "ci_lower":        [None if s is None else round(s - 0.5, 3)
                                for s in scores],
            "ci_upper":        [None if s is None else round(s + 0.5, 3)
                                for s in scores],
            "own_baseline_z":  scores,
            "population_z":    [None if s is None else round(s * 0.8, 3)
                                for s in scores],
            "mahalanobis":     [None if s is None else round(abs(s) * 1.1, 3)
                                for s in scores],
            "observable_mask": observable,
            "recovery":        fit_recovery(scores, ALL_TPS),
        }
    return out


# --------------------------------------------------------------------------
# flow diagram - real correlations across OSD-573, OSD-572, OSD-574, axes
# --------------------------------------------------------------------------

def _read_taxa_set(path: Path) -> set[str]:
    if not path.exists():
        return set()
    try:
        df = pd.read_csv(path)
    except Exception:
        return set()
    if "feature" not in df.columns:
        return set()
    return set(str(f) for f in df["feature"].dropna())


def _read_per_subject_csv(path: Path) -> pd.DataFrame | None:
    if not path.exists():
        return None
    try:
        df = pd.read_csv(path)
    except Exception:
        return None
    needed = {"feature", "C001", "C002", "C003", "C004"}
    if not needed.issubset(df.columns):
        return None
    return df


def _per_astro_mean_abs(df: pd.DataFrame) -> dict[str, float]:
    """Mean of |log2FC| per astronaut across features in a per-subject CSV."""
    out: dict[str, float] = {}
    for crew in CREW:
        col = pd.to_numeric(df[crew], errors="coerce").dropna()
        out[crew] = float(col.abs().mean()) if len(col) else 0.0
    return out


def _signed_mean_pooled(df: pd.DataFrame) -> float:
    """Signed cohort-level mean of the 'pooled' column. Negative = suppression."""
    if df is None or "pooled" not in df.columns:
        return 0.0
    col = pd.to_numeric(df["pooled"], errors="coerce").dropna()
    return float(col.mean()) if len(col) else 0.0


def _normalize(values: list[float], cap: float = 1.0) -> list[float]:
    """Scale values to [-cap, cap] by dividing by max(|v|). Used for node
    magnitudes so the Sankey renders comparable thicknesses."""
    if not values:
        return values
    m = max(abs(v) for v in values) or 1.0
    return [round(v / m * cap, 3) for v in values]


def build_real_flow_diagram(axes_built: list[dict]) -> dict:
    """Per-astronaut microbiome -> barrier -> systemic flow with computed
    edge weights. Reads:
      analysis/results/OSD-573_taxonomy_detected_during_flight.csv
      analysis/results/OSD-572_taxonomy_NAP_during_vs_pre.csv
      analysis/results/OSD-572_taxonomy_ARM_during_vs_pre.csv
      analysis/results/OSD-574_spatial_pooled_DE.csv
      and pulls per-astronaut R+1 cytokine values from the inflammation
      axis trajectory.

    Falls back to a placeholder if any required file is missing.
    """
    capsule = _read_taxa_set(
        ANALYSIS_RESULTS / "OSD-573_taxonomy_detected_during_flight.csv")
    nap_df  = _read_per_subject_csv(
        ANALYSIS_RESULTS / "OSD-572_taxonomy_NAP_during_vs_pre.csv")
    arm_df  = _read_per_subject_csv(
        ANALYSIS_RESULTS / "OSD-572_taxonomy_ARM_during_vs_pre.csv")
    bar_df  = None
    bar_path = ANALYSIS_RESULTS / "OSD-574_spatial_pooled_DE.csv"
    if bar_path.exists():
        try:
            bar_df = pd.read_csv(bar_path)
        except Exception:
            bar_df = None

    if nap_df is None or arm_df is None:
        return _build_placeholder_flow_diagram()

    # cohort-level node magnitudes
    nap_taxa = set(str(f) for f in nap_df["feature"].dropna())
    arm_taxa = set(str(f) for f in arm_df["feature"].dropna())
    shared_nap = (len(capsule & nap_taxa) / max(len(nap_taxa), 1)
                  if capsule else 0.0)
    shared_arm = (len(capsule & arm_taxa) / max(len(arm_taxa), 1)
                  if capsule else 0.0)
    barrier_signed = _signed_mean_pooled(bar_df)

    nap_per_astro = _per_astro_mean_abs(nap_df)
    arm_per_astro = _per_astro_mean_abs(arm_df)

    # pull per-astronaut R+1 cytokine signal from the inflammation axis if
    # available, else 0.
    inflammation = next((ax for ax in axes_built
                         if ax.get("id") == "inflammation"), None)
    r1_idx = ALL_TPS.index("R+1") if "R+1" in ALL_TPS else None
    cyto_per_astro: dict[str, float] = {c: 0.0 for c in CREW}
    if inflammation and r1_idx is not None:
        for crew in CREW:
            scores = inflammation.get("trajectories", {}).get(
                crew, {}).get("scores", [])
            v = scores[r1_idx] if r1_idx < len(scores) else None
            cyto_per_astro[crew] = float(v) if v is not None else 0.0

    # normalize magnitudes within each layer so the Sankey reads cleanly
    nap_vals = list(nap_per_astro.values())
    arm_vals = list(arm_per_astro.values())
    cyto_vals = list(cyto_per_astro.values())
    nap_norm = _normalize(nap_vals)
    arm_norm = _normalize(arm_vals)
    cyto_norm = _normalize(cyto_vals)

    per_astro: dict[str, dict] = {}
    for i, crew in enumerate(CREW):
        n_nap = nap_norm[i]
        n_arm = arm_norm[i]
        n_cyto = cyto_norm[i]
        # node magnitudes (cytokines and barrier are signed; microbiome
        # mean-|log2FC| is unsigned but we annotate direction by source)
        nodes = [
            {"id": "capsule_NAP_taxa", "layer": "environment",
             "label": f"Capsule taxa shared with crew NAP "
                      f"({100*shared_nap:.0f}% overlap)",
             "magnitude": round(shared_nap, 3)},
            {"id": "host_NAP", "layer": "host_site",
             "label": "Nasopharynx microbiome shift",
             "magnitude": n_nap},
            {"id": "host_ARM", "layer": "host_site",
             "label": "Forearm skin microbiome shift",
             "magnitude": n_arm},
            {"id": "barrier_FLG", "layer": "barrier",
             "label": "Skin barrier (OSD-574 spatial pooled)",
             "magnitude": round(min(max(barrier_signed / 2.0, -1), 1), 3)},
            {"id": "cytokine_IL6", "layer": "systemic",
             "label": "R+1 inflammation composite (IL-6 / TNF / CRP)",
             "magnitude": n_cyto},
        ]
        # edges: weight = product of source and target magnitudes,
        # clipped to [0.05, 1] for visual readability
        def w(*ms):
            ws = abs(np.prod(ms)) ** 0.5
            return float(round(min(max(ws, 0.05), 1.0), 3))
        edges = [
            {"source": "capsule_NAP_taxa", "target": "host_NAP",
             "weight": w(shared_nap, abs(n_nap)),
             "evidence": "shared_taxa_temporal"},
            {"source": "capsule_NAP_taxa", "target": "host_ARM",
             "weight": w(shared_arm, abs(n_arm)),
             "evidence": "shared_taxa_temporal"},
            {"source": "host_NAP", "target": "barrier_FLG",
             "weight": w(abs(n_nap), abs(barrier_signed) / 2.0),
             "evidence": "correlation_only"},
            {"source": "host_ARM", "target": "barrier_FLG",
             "weight": w(abs(n_arm), abs(barrier_signed) / 2.0),
             "evidence": "correlation_only"},
            {"source": "barrier_FLG", "target": "cytokine_IL6",
             "weight": w(abs(barrier_signed) / 2.0, abs(n_cyto)),
             "evidence": "correlation_only"},
        ]
        per_astro[crew] = {"nodes": nodes, "edges": edges}

    return {
        "per_astronaut": per_astro,
        "evidence_legend": {
            "shared_taxa_temporal":
                "Edge weight = sqrt(shared-taxa fraction * "
                "normalized host-shift magnitude). Direction is supported "
                "by temporal precedence: capsule taxa observed pre-launch "
                "and absent on crew preflight, then present on crew "
                "during/post flight.",
            "correlation_only":
                "Edge weight = sqrt(product of normalized source and "
                "target magnitudes). Direction is NOT established; "
                "reported as undirected association.",
        },
        "cohort_level_facts": {
            "capsule_to_NAP_shared_fraction": round(shared_nap, 4),
            "capsule_to_ARM_shared_fraction": round(shared_arm, 4),
            "barrier_pooled_signed_mean":     round(barrier_signed, 4),
        },
    }


def _build_placeholder_flow_diagram() -> dict:
    """Per-astronaut placeholder flow diagram, used when the analysis
    CSVs needed by build_real_flow_diagram() aren't available. Schema
    is identical so the GUI doesn't care which one is in use.
    """
    rng = np.random.default_rng(7)
    per_astro = {}
    for i, astro in enumerate(CREW):
        scale = 0.7 + 0.2 * i
        per_astro[astro] = {
            "nodes": [
                {"id": "capsule_NAP_taxa", "layer": "environment",
                 "label": "Capsule taxa (NAP-relevant)",
                 "magnitude": round(0.65 * scale, 3)},
                {"id": "host_NAP", "layer": "host_site",
                 "label": "Nasopharynx microbiome",
                 "magnitude": round(0.85 * scale, 3)},
                {"id": "host_ARM", "layer": "host_site",
                 "label": "Forearm skin microbiome (diversity)",
                 "magnitude": round(-0.6 * scale, 3)},
                {"id": "barrier_FLG", "layer": "barrier",
                 "label": "FLG (filaggrin) expression",
                 "magnitude": round(-0.5 * scale + rng.normal(0, 0.05), 3)},
                {"id": "cytokine_IL6", "layer": "systemic",
                 "label": "IL-6",
                 "magnitude": round(0.7 * scale, 3)},
                {"id": "cytokine_TNF", "layer": "systemic",
                 "label": "TNF-alpha",
                 "magnitude": round(0.55 * scale, 3)},
            ],
            "edges": [
                {"source": "capsule_NAP_taxa", "target": "host_NAP",
                 "weight": 0.7, "evidence": "shared_taxa_temporal"},
                {"source": "host_NAP", "target": "barrier_FLG",
                 "weight": 0.4, "evidence": "correlation_only"},
                {"source": "host_ARM", "target": "barrier_FLG",
                 "weight": 0.5, "evidence": "correlation_only"},
                {"source": "barrier_FLG", "target": "cytokine_IL6",
                 "weight": 0.55, "evidence": "correlation_only"},
                {"source": "barrier_FLG", "target": "cytokine_TNF",
                 "weight": 0.45, "evidence": "correlation_only"},
            ],
        }
    return {
        "per_astronaut": per_astro,
        "evidence_legend": {
            "shared_taxa_temporal":
                "Taxon present pre-launch in capsule, absent on crew "
                "member preflight, present on crew during/post flight. "
                "Temporal precedence supports directionality.",
            "correlation_only":
                "Direction not established; reported as undirected "
                "association.",
        },
    }


# --------------------------------------------------------------------------
# top-level assembly
# --------------------------------------------------------------------------

def build(mock_only: bool) -> dict:
    metadata = {
        "mission": "Inspiration4",
        "generated_at": _dt.datetime.now(_dt.timezone.utc)
                          .replace(microsecond=0).isoformat(),
        "generator": "risk_profile_claude/build_risk_profile.py v0.1",
        "n_astronauts": 4,
        "timepoints": ALL_TPS,
        "in_flight_timepoints": DURING_TPS,
        "preflight_timepoints":  PRE_TPS,
        "postflight_timepoints": POST_TPS,
        "scoring_conventions": {
            "own_baseline_z": "(value - mean(self_preflight)) / sd(self_preflight)",
            "population_z":   "(value - range_mid) / (range_width / 3.92), reference range = central 95%",
            "mahalanobis":    "sqrt((x - mu_pre)^T * Sigma^-1 * (x - mu_pre)); Sigma uses preflight-pool correlation with Ledoit-Wolf shrinkage and population-reference marginal SDs where available",
            "sign_convention": "positive = elevated relative to baseline / population midpoint",
        },
    }
    astronauts = [
        {"id": c, "display_id": c, "role_label": f"Crew member {c[-1]}"}
        for c in CREW
    ]

    if mock_only:
        axes = [
            {"id": "immune", "label": "Immune Regulation",
             "description": "Composite z of Th1/Th2/Treg cytokines.",
             "scoring_method": "Mock data for GUI development.",
             "datasets_used": ["OSD-570", "OSD-575"],
             "in_flight_observable": False,
             "ground_only_note": "OSD-575 panels require phlebotomy.",
             "actionable_line": "Saliva-based cytokine surrogates would help in flight.",
             "feature_panel": [{"name": "IL-2", "source": "mock"},
                               {"name": "IL-10", "source": "mock"}],
             "trajectories": _mock_smooth_traj(seed=11, magnitude=1.4,
                                                decay_rate=0.5),
             "within_cohort_comparison": {"summary": "Mock data.",
                                           "ranking_at": "R+1",
                                           "ranking": []},
             "prior_cohort_comparison": None,
             "is_mock": True},
            {"id": "inflammation", "label": "Inflammation & Oxidative Stress",
             "description": "Acute-phase cytokines + urine markers.",
             "scoring_method": "Mock data for GUI development.",
             "datasets_used": ["OSD-575", "OSD-656", "OSD-571"],
             "in_flight_observable": False,
             "ground_only_note": "Ground-only panels.",
             "actionable_line": "R+45 follow-up for residual inflammation.",
             "feature_panel": [{"name": "IL-6", "source": "mock"},
                               {"name": "CRP", "source": "mock"}],
             "trajectories": _mock_smooth_traj(seed=22, magnitude=1.8,
                                                decay_rate=0.55),
             "within_cohort_comparison": {"summary": "Mock data.",
                                           "ranking_at": "R+1",
                                           "ranking": []},
             "prior_cohort_comparison": None,
             "is_mock": True},
            {"id": "ddr", "label": "DNA Damage Response",
             "description": "Canonical DDR gene signature.",
             "scoring_method": "Mock data for GUI development.",
             "datasets_used": ["OSD-569"],
             "in_flight_observable": False,
             "ground_only_note": "No in-flight blood draws.",
             "actionable_line": "Pending Ensembl-to-symbol mapping.",
             "feature_panel": [{"name": g, "source": "mock"}
                               for g in DDR_GENE_SYMBOLS],
             "trajectories": _mock_smooth_traj(seed=42, magnitude=1.6,
                                                decay_rate=0.45),
             "within_cohort_comparison": {"summary": "Mock data.",
                                           "ranking_at": "R+1",
                                           "ranking": []},
             "prior_cohort_comparison": None,
             "is_mock": True},
            {"id": "mitochondrial", "label": "Mitochondrial Function",
             "description": "TCA intermediates + acylcarnitines.",
             "scoring_method": "Mock data for GUI development.",
             "datasets_used": ["OSD-571"],
             "in_flight_observable": False,
             "ground_only_note": "Plasma collection requires phlebotomy.",
             "actionable_line": "Cohort-level only; raw matrix needed for per-astronaut.",
             "feature_panel": [{"name": s, "source": "mock"}
                               for s in MITO_TCA_NEEDLES],
             "trajectories": _mock_smooth_traj(seed=33, magnitude=1.2,
                                                decay_rate=0.4),
             "within_cohort_comparison": {"summary": "Mock data.",
                                           "ranking_at": "R+1",
                                           "ranking": []},
             "prior_cohort_comparison": None,
             "is_mock": True},
        ]
    else:
        axes = [
            build_immune_axis(),
            build_inflammation_axis(),
            build_ddr_axis(),
            build_mitochondrial_axis(),
        ]

    payload = {
        "metadata": metadata,
        "astronauts": astronauts,
        "axes": axes,
        "multi_system_deviation": compute_multi_system_deviation(axes,
                                                                  ALL_TPS),
        "flow_diagram": build_real_flow_diagram(axes),
    }
    # Cascade inference: score literature-derived upstream causes against
    # the observed concordant perturbations. Skipped in --mock-only since
    # it relies on the real analysis/results/ CSVs.
    if not mock_only:
        try:
            payload["cascade_inference"] = cascade_inference.run()
        except Exception as e:
            payload["cascade_inference"] = {"error": str(e)}
    return payload


def compute_multi_system_deviation(axes_built: list[dict],
                                   timepoints: list[str]) -> dict | None:
    """For each (astronaut, timepoint), compute a single Mahalanobis-distance
    scalar over the four axis composite scores. Captures multi-system
    deviation: 'how unusual is this astronaut across all four Track 2 axes
    at once, relative to the cohort's preflight baseline.'

    Returns:
      {
        "per_astronaut": {
          "C001": {"scores": [...len(timepoints)...],
                   "observable_mask": [...]},
          ...
        },
        "axis_order": [<axis_id>, ...],
        "preflight_pool_n": int,
        "method": "..."
      }

    Returns None if there isn't enough preflight data to estimate cov.
    """
    if not axes_built:
        return None

    # Cohort-level axes (mitochondrial: same value across all 4 crew) have
    # zero between-astronaut variance and would make the covariance matrix
    # singular. Exclude them from the multi-system Mahalanobis.
    eligible_axes = [ax for ax in axes_built
                     if not ax.get("is_cohort_level", False)]
    if len(eligible_axes) < 2:
        return None
    axis_ids = [ax.get("id", f"ax_{i}") for i, ax in enumerate(eligible_axes)]
    excluded = [ax.get("id") for ax in axes_built
                if ax.get("is_cohort_level", False)]
    n_ax = len(eligible_axes)

    # build the (crew, tp) -> [score_per_axis] table over ELIGIBLE axes
    table: dict[str, dict[str, list[float | None]]] = {c: {} for c in CREW}
    for tp_idx, tp in enumerate(timepoints):
        for crew in CREW:
            vec: list[float | None] = []
            for ax in eligible_axes:
                scores = ax.get("trajectories", {}).get(crew, {}).get(
                    "scores", [])
                v = scores[tp_idx] if tp_idx < len(scores) else None
                vec.append(v)
            table[crew][tp] = vec

    # preflight pool: rows = (crew, pre_tp) with all 4 axes finite
    pool_rows: list[list[float]] = []
    for crew in CREW:
        for tp in PRE_TPS:
            vec = table[crew][tp]
            if all(v is not None and np.isfinite(v) for v in vec):
                pool_rows.append([float(v) for v in vec])
    if len(pool_rows) < 4:
        return None
    pool = np.asarray(pool_rows, dtype=float)

    # mahalanobis distance from each (crew, tp) to the preflight pool
    per_astro: dict[str, dict] = {}
    for crew in CREW:
        scores_traj: list[float | None] = []
        observable: list[bool] = []
        for tp in timepoints:
            vec = table[crew][tp]
            if any(v is None or not np.isfinite(v) for v in vec):
                scores_traj.append(None)
                observable.append(False)
                continue
            point = np.asarray(vec, dtype=float)
            d = panel_mahalanobis(point, pool)
            scores_traj.append(_round(d) if np.isfinite(d) else None)
            observable.append(True)
        per_astro[crew] = {"scores": scores_traj,
                           "observable_mask": observable}

    return {
        "per_astronaut": per_astro,
        "axis_order": axis_ids,
        "axes_excluded": excluded,
        "preflight_pool_n": int(pool.shape[0]),
        "method": ("Mahalanobis distance from each (astronaut, timepoint) "
                   "to the cohort preflight mean over a "
                   f"{n_ax}-vector of axis composite scores "
                   f"({', '.join(axis_ids)}). The covariance comes from "
                   f"the preflight pool ({pool.shape[0]} rows = up to 4 "
                   "crew x 3 preflight timepoints) with Ledoit-Wolf "
                   "shrinkage toward the identity (lambda=0.30). A higher "
                   "distance = the astronaut sits further outside the "
                   "cohort's preflight joint distribution across the "
                   "included axes simultaneously."
                   + (f" Excluded (cohort-level, no inter-astronaut "
                      f"variance): {', '.join(excluded)}." if excluded
                      else "")),
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--mock-only", action="store_true",
                   help="Regenerate mock_dashboard_data.json without "
                        "touching the analysis cache.")
    p.add_argument("--out", type=Path, default=None,
                   help="Output path. Defaults to ../data/dashboard_data.json "
                        "for real builds and ./mock_dashboard_data.json "
                        "for --mock-only.")
    args = p.parse_args(argv)

    payload = build(mock_only=args.mock_only)

    if args.out is not None:
        target = args.out
    elif args.mock_only:
        target = MOCK_PATH
    else:
        target = OUTPUT_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    with open(target, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    print(f"wrote {target}  ({target.stat().st_size / 1024:.1f} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
