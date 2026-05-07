"""
Master orchestrator for the Inspiration-4 multi-omics analysis.

Runs every per-dataset script. For each dataset, asks the same question:

    "Did anything interesting significantly change between the
     before, during, and after spaceflight phases - in ALL FOUR
     crewmembers in the same direction?"

Two kinds of "yes":
    A. Per-subject longitudinal datasets (microbiome swabs, serum panels,
       urine, stool, blood RNA-seq / m6A / CBC, VDJ): a feature is listed
       only if all four crew (C001..C004) individually move the same way
       past the magnitude threshold.
    B. Pre-aggregated DE tables (snRNA-seq, snATAC-seq, OSD-571 panels,
       spatial transcriptomics): per-subject test is impossible because
       the data are already pooled. We list features whose group-level
       adjusted p-value < 0.05 AND |logFC| >= 1, labeled 'pooled'.

OSD-573 (Dragon-capsule swabs) is environmental and excluded from the
all-four-subjects roll-up; introduced/not-persisted feature lists are
written separately.

Output:
   analysis/results/MASTER_summary.json   - structured summary of every
                                             dataset's hits
   analysis/results/MASTER_significant_features.csv
                                           - flat table: dataset, table,
                                             feature, direction, mode,
                                             phase
   per-dataset CSVs (one per (dataset, table, [body_site,] phase))
"""

from __future__ import annotations
import glob
import json
import os
import sys
import time
from typing import Callable

import pandas as pd

# make sibling modules importable when run as a script
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import osd569_blood
import osd570_pbmc
import osd571_proteomics
import osd572_crew_swabs
import osd573_capsule
import osd574_skin
import osd575_serum
import osd630_stool
import osd656_urine

from common import ensure_results_dir, FeatureCall


DATASETS: list[tuple[str, Callable]] = [
    ("OSD-572 crew skin/oral/nasal swabs", osd572_crew_swabs.run),
    ("OSD-573 dragon-capsule swabs",        osd573_capsule.run),
    ("OSD-574 spatial skin + skin metagenomics", osd574_skin.run),
    ("OSD-575 serum panels (CMP, immune Eve, immune Alamar, cardio)",
        osd575_serum.run),
    ("OSD-630 stool metagenomics",          osd630_stool.run),
    ("OSD-656 urine multiplex",             osd656_urine.run),
    ("OSD-569 blood RNA-seq, m6A, CBC",     osd569_blood.run),
    ("OSD-570 PBMC snRNA-seq, snATAC-seq, VDJ", osd570_pbmc.run),
    ("OSD-571 plasma metabolomics, EVP, protein", osd571_proteomics.run),
]


def _flatten(label: str, dataset_result: dict) -> list[dict]:
    """Walk the nested per-dataset result tree and emit one row per
    (table, [body_site,] phase) hit list."""
    rows: list[dict] = []
    dsid = dataset_result.get("dataset", label)
    for tname, tinfo in dataset_result.get("tables", {}).items():
        if not isinstance(tinfo, dict) or "error" in tinfo:
            continue
        # case A: per-site nested ({site: {phase: [hits]}})
        if "hits" in tinfo and isinstance(tinfo.get("hits"), dict) \
                and any(isinstance(v, dict) for v in tinfo["hits"].values()):
            for site, phases in tinfo["hits"].items():
                for phase_label, hits in phases.items():
                    for h in hits:
                        rows.append({
                            "dataset": dsid,
                            "table":   tname,
                            "body_site": site,
                            "phase":   phase_label,
                            "feature": h.feature,
                            "direction": h.direction,
                            "mode":    "all_four_subjects",
                        })
            continue
        # case B: per-subject post_vs_pre / during_vs_pre flat hit lists
        for hits_key, phase_label in (("hits",         "post_vs_pre"),
                                      ("hits_during",  "during_vs_pre"),
                                      ("hits_post",    "post_vs_pre")):
            if hits_key in tinfo and isinstance(tinfo[hits_key], list):
                mode = ("all_four_subjects"
                        if tinfo.get("mode", "").startswith("per_subject")
                           or tinfo.get("mode") is None
                        else tinfo["mode"])
                for h in tinfo[hits_key]:
                    if not isinstance(h, FeatureCall):
                        continue
                    rows.append({
                        "dataset": dsid,
                        "table":   tname,
                        "body_site": "",
                        "phase":   phase_label,
                        "feature": h.feature,
                        "direction": h.direction,
                        "mode":    "all_four_subjects" if h.phase_compared
                                   != "post_vs_pre_pooled" else "pooled_DE",
                    })
    return rows


def _summary_only(dataset_result: dict) -> dict:
    """Strip the FeatureCall objects out so the summary JSON is small."""
    out = {k: v for k, v in dataset_result.items() if k != "tables"}
    out["tables"] = {}
    for tname, tinfo in dataset_result.get("tables", {}).items():
        if not isinstance(tinfo, dict):
            out["tables"][tname] = tinfo
            continue
        slim = {k: v for k, v in tinfo.items()
                if k not in ("hits", "hits_during", "hits_post")}
        # for nested per-site: collapse counts only
        if "per_site" in tinfo:
            slim["per_site"] = tinfo["per_site"]
        out["tables"][tname] = slim
    return out


def _clear_previous_results(results_dir: str) -> int:
    """Delete prior outputs so stale per-dataset CSVs from earlier runs
    don't pile up alongside the current run's files. Only touches files
    we own (OSD-* and MASTER_*) - anything else the user dropped in this
    directory is left alone."""
    patterns = ("OSD-*.csv", "MASTER_*.csv", "MASTER_*.json")
    removed = 0
    for pat in patterns:
        for path in glob.glob(os.path.join(results_dir, pat)):
            try:
                os.remove(path)
                removed += 1
            except OSError:
                pass
    return removed


def run_all() -> dict:
    results_dir = ensure_results_dir()
    n_cleared = _clear_previous_results(results_dir)
    if n_cleared:
        print(f"[master] cleared {n_cleared} stale output file(s) from "
              f"{results_dir}", flush=True)
    overall = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "criteria": {
            "per_subject_log2fc_threshold": 1.0,
            "per_subject_concordance":      "all 4 crew, same direction",
            "pooled_DE_padj_threshold":     0.05,
            "pooled_DE_log2fc_threshold":   1.0,
        },
        "datasets": {},
    }
    flat_rows: list[dict] = []

    for label, runner in DATASETS:
        print(f"[master] running {label} ...", flush=True)
        try:
            res = runner()
        except Exception as e:
            print(f"[master] FAILED {label}: {e}", flush=True)
            overall["datasets"][label] = {"error": str(e)}
            continue
        overall["datasets"][label] = _summary_only(res)
        flat_rows.extend(_flatten(label, res))
        print(f"[master]  -> {label}: "
              f"{sum(1 for r in flat_rows if r['dataset'] == res.get('dataset', label))}"
              f" significant features so far",
              flush=True)

    # write outputs
    summary_path = os.path.join(results_dir, "MASTER_summary.json")
    with open(summary_path, "w") as f:
        json.dump(overall, f, indent=2, default=str)
    flat_path = os.path.join(results_dir, "MASTER_significant_features.csv")
    if flat_rows:
        pd.DataFrame(flat_rows).to_csv(flat_path, index=False)
    else:
        pd.DataFrame(columns=["dataset", "table", "body_site", "phase",
                              "feature", "direction", "mode"]
                     ).to_csv(flat_path, index=False)
    overall["_summary_json"]   = summary_path
    overall["_flat_csv"]       = flat_path
    overall["_total_features"] = len(flat_rows)
    return overall


if __name__ == "__main__":
    res = run_all()
    print("\n========== MASTER REPORT ==========")
    print(f"Total significantly-changed features collected: "
          f"{res['_total_features']}")
    print(f"Per-dataset summary  : {res['_summary_json']}")
    print(f"Flat feature listing : {res['_flat_csv']}")
    print()
    print("Per-dataset significant-feature counts:")
    for label, info in res["datasets"].items():
        if "error" in info:
            print(f"  {label}: ERROR {info['error']}")
            continue
        for tname, t in info.get("tables", {}).items():
            if not isinstance(t, dict) or "error" in t:
                continue
            keys = [k for k in t.keys()
                    if k.startswith("n_significant")
                    or k.endswith("_significant_all_4")]
            if keys:
                summary = ", ".join(f"{k}={t[k]}" for k in keys)
                print(f"  {label} | {tname}: {summary}")
            elif "per_site" in t:
                print(f"  {label} | {tname} (per body site):")
                for site, phases in t["per_site"].items():
                    pieces = ", ".join(f"{p}={n}" for p, n in phases.items())
                    print(f"      {site}: {pieces}")
