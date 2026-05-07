"""
OSD-630: Stool metagenomics (4 tables - the dataset highlighted as
"under-analyzed in the published literature" in the project README).

Same structure as the OSD-572 crew swabs (KEGG / taxonomy / pathway /
gene-family) but stool samples come from a single body compartment, so
columns are  C00X_TIMEPOINT  with no body-site suffix.

Phases tested: during_vs_pre and post_vs_pre.
"""

from __future__ import annotations
import os
import pandas as pd

from common import (
    drop_uninformative, find_concordant_changes,
    parse_sample, phase_of, ensure_results_dir, write_hits_csv,
)

URLS = {
    "kegg":     "https://osdr.nasa.gov/geode-py/ws/studies/OSD-630/download?source=datamanager&file=GLDS-599_GMetagenomics_Combined-gene-level-KO-function-coverages-CPM_GLmetagenomics.tsv",
    "taxonomy": "https://osdr.nasa.gov/geode-py/ws/studies/OSD-630/download?source=datamanager&file=GLDS-599_GMetagenomics_Combined-gene-level-taxonomy-coverages-CPM_GLmetagenomics.tsv",
    "pathway":  "https://osdr.nasa.gov/geode-py/ws/studies/OSD-630/download?source=datamanager&file=GLDS-599_GMetagenomics_Pathway-abundances-cpm_GLmetagenomics.tsv",
    "genefam":  "https://osdr.nasa.gov/geode-py/ws/studies/OSD-630/download?source=datamanager&file=GLDS-599_GMetagenomics_Gene-families-cpm_GLmetagenomics.tsv",
}


def _is_crew_column(col: str) -> bool:
    crew, tp = parse_sample(str(col))
    return crew is not None and phase_of(tp) is not None


def _load(url: str) -> pd.DataFrame:
    df = pd.read_csv(url, index_col=0, sep="\t", low_memory=False)
    df = df[[c for c in df.columns if _is_crew_column(c)]]
    df = drop_uninformative(df, axis="index")
    return df


def run() -> dict:
    out = {"dataset": "OSD-630", "tables": {}}
    results_dir = ensure_results_dir()
    for name, url in URLS.items():
        print(f"  [OSD-630] {name}: downloading...", flush=True)
        try:
            df = _load(url)
        except Exception as e:
            print(f"  [OSD-630] {name}: ERROR {e}", flush=True)
            out["tables"][name] = {"error": str(e)}
            continue
        print(f"  [OSD-630] {name}: {df.shape[0]} features x "
              f"{df.shape[1]} crew samples - running tests...", flush=True)
        during_hits = find_concordant_changes(df, phase_a="during",
                                              phase_b="pre")
        post_hits   = find_concordant_changes(df, phase_a="post",
                                              phase_b="pre")
        write_hits_csv(during_hits, os.path.join(
            results_dir, f"OSD-630_{name}_during_vs_pre.csv"))
        write_hits_csv(post_hits, os.path.join(
            results_dir, f"OSD-630_{name}_post_vs_pre.csv"))
        out["tables"][name] = {
            "n_features": int(df.shape[0]),
            "during_vs_pre_significant_all_4": len(during_hits),
            "post_vs_pre_significant_all_4":   len(post_hits),
            "hits_during": during_hits,
            "hits_post":   post_hits,
        }
    return out


if __name__ == "__main__":
    import json
    res = run()
    for name, t in res["tables"].items():
        if "error" in t:
            print(f"OSD-630 {name}: ERROR {t['error']}")
            continue
        print(f"OSD-630 {name}: features={t['n_features']} "
              f"during_all_4={t['during_vs_pre_significant_all_4']} "
              f"post_all_4={t['post_vs_pre_significant_all_4']}")
