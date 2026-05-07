"""
OSD-575: Serum panels (4 separate tables).

    metabolic_blood : Quest comprehensive metabolic panel (CMP) - the
                      *_value_* rows are measurements; *_range_min_* and
                      *_range_max_* rows are constant clinical reference
                      bounds and are dropped.
    immune_eve      : EvePanel multiplex cytokine concentrations
                      (picogram/mL). The *_percent rows are pooled-normal
                      rescalings of the same concentrations -> drop.
    immune_alamar   : Alamar multiplex immune panel.
    cardio_eve      : EvePanel cardiovascular markers.

All four are loaded with .transpose(), so columns end up as sample names
of the form  C00X_serum_TIMEPOINT  with timepoints
L-92, L-44, L-3, R+1, R+45, R+82, R+194  (NO in-flight blood draws).

Test: post-vs-pre concordant change across all four crew. Pre = L-92/L-44/L-3,
Post = R+1/R+45/R+82/R+194.
"""

from __future__ import annotations
import os
import pandas as pd

from common import (
    drop_uninformative, find_concordant_changes,
    ensure_results_dir, write_hits_csv,
)

URLS = {
    "metabolic":     "https://osdr.nasa.gov/geode-py/ws/studies/OSD-575/download?source=datamanager&file=LSDS-8_Comprehensive_Metabolic_Panel_CMP_TRANSFORMED.csv",
    "immune_eve":    "https://osdr.nasa.gov/geode-py/ws/studies/OSD-575/download?source=datamanager&file=LSDS-8_Multiplex_serum_immune_EvePanel_TRANSFORMED.csv",
    "immune_alamar": "https://osdr.nasa.gov/geode-py/ws/studies/OSD-575/download?source=datamanager&file=LSDS-8_Multiplex_serum.immune.AlamarPanel_TRANSFORMED.csv",
    "cardio_eve":    "https://osdr.nasa.gov/geode-py/ws/studies/OSD-575/download?source=datamanager&file=LSDS-8_Multiplex_serum_cardiovascular_EvePanel_TRANSFORMED.csv",
}


def _load(url: str) -> pd.DataFrame:
    df = pd.read_csv(url, index_col=0).transpose()
    # rows are now analytes; drop reference ranges + percent siblings
    df = drop_uninformative(df, axis="index")
    return df


def run() -> dict:
    out = {"dataset": "OSD-575", "tables": {}}
    results_dir = ensure_results_dir()
    for name, url in URLS.items():
        try:
            df = _load(url)
        except Exception as e:
            out["tables"][name] = {"error": str(e)}
            continue
        hits = find_concordant_changes(df, phase_a="post", phase_b="pre")
        write_hits_csv(hits, os.path.join(
            results_dir, f"OSD-575_{name}_post_vs_pre.csv"))
        out["tables"][name] = {
            "n_features": int(df.shape[0]),
            "n_significant_all_4": len(hits),
            "hits": hits,
        }
    return out


if __name__ == "__main__":
    import json, sys
    res = run()
    print(json.dumps({k: (v if k != "tables"
                          else {n: {kk: t[kk]
                                    for kk in ("n_features",
                                               "n_significant_all_4")
                                    if kk in t}
                                for n, t in v.items()})
                      for k, v in res.items()},
                     indent=2))
