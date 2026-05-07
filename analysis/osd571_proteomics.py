"""
OSD-571: Plasma metabolomics + proteomics + extracellular-vesicle proteomics.

All three tables are PRE-AGGREGATED limma-style DE tables - they only
have summary statistics across subjects, NOT per-subject longitudinal
measurements:

    columns: logFC, AveExpr, t, P.Value, adj.P.Val, B

So the "all four crew significantly changed" framing does not directly
apply: the data have already been collapsed to a single t-test per
analyte. We instead report features with adj.P.Val < 0.05 and
|logFC| >= 1 as the list of "tests that significantly changed" (these
are the features whose group-level shift survived correction over the
pooled n=4 cohort).
"""

from __future__ import annotations
import os
import pandas as pd

from common import (
    find_de_significant, ensure_results_dir, write_hits_csv,
    PADJ_THRESHOLD, LOG2FC_THRESHOLD,
)

URLS = {
    "metabolomics": "https://osdr.nasa.gov/geode-py/ws/studies/OSD-571/download?source=datamanager&file=GLDS-563_metabolomics_Plasma_Metabolomics_Processed_Data.xlsx",
    "evp":          "https://osdr.nasa.gov/geode-py/ws/studies/OSD-571/download?source=datamanager&file=GLDS-563_proteomics_EVP_Proteomics_Processed_Data.xlsx",
    "protein":      "https://osdr.nasa.gov/geode-py/ws/studies/OSD-571/download?source=datamanager&file=GLDS-563_proteomics_Plasma_Proteomics_Processed_Data.xlsx",
}


def _load(url: str) -> pd.DataFrame:
    return pd.read_excel(url, skiprows=[0, 1, 2, 3, 4, 5], index_col=0)


def run() -> dict:
    out = {"dataset": "OSD-571", "tables": {}}
    results_dir = ensure_results_dir()
    for name, url in URLS.items():
        try:
            df = _load(url)
        except Exception as e:
            out["tables"][name] = {"error": str(e)}
            continue
        hits = find_de_significant(df, padj_col="adj.P.Val",
                                   lfc_col="logFC",
                                   padj_threshold=PADJ_THRESHOLD,
                                   lfc_threshold=LOG2FC_THRESHOLD)
        write_hits_csv(hits, os.path.join(
            results_dir, f"OSD-571_{name}_pooled_DE.csv"))
        out["tables"][name] = {
            "mode": "pre_aggregated_DE",
            "n_features": int(df.shape[0]),
            "n_significant_pooled": len(hits),
            "hits": hits,
        }
    return out


if __name__ == "__main__":
    res = run()
    for name, t in res["tables"].items():
        if "error" in t:
            print(f"OSD-571 {name}: ERROR {t['error']}")
        else:
            print(f"OSD-571 {name}: features={t['n_features']} "
                  f"significant_pooled={t['n_significant_pooled']}")
