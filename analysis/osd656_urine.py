"""
OSD-656: Urine multiplex immune (Alamar) panel.

The CSV is laid out the OPPOSITE way from the serum panels: rows are sample
names of the form  C00X_urine_TIMEPOINT  and columns are analytes.
After load, we transpose so that rows=analytes / columns=samples to match
the rest of the pipeline.

Important variable filtering:
  * 'Unnamed: 2' header artifact - drop.
  * Each analyte appears as both *_concentration_npq AND
    *_percent_normalized_value. Concentrations are the primary measurement;
    the percent column is a derived rescale of the concentration against a
    pooled-normal pool, so we drop the _percent_normalized_value siblings
    to avoid double-counting.

Phases tested: post_vs_pre (no in-flight urine).
"""

from __future__ import annotations
import os
import pandas as pd

from common import (
    drop_uninformative, find_concordant_changes,
    ensure_results_dir, write_hits_csv,
)

URL = "https://osdr.nasa.gov/geode-py/ws/studies/OSD-656/download?source=datamanager&file=LSDS-64_Multiplex_urine.immune.AlamarPanel_TRANSFORMED.csv"


def _load(url: str) -> pd.DataFrame:
    df = pd.read_csv(url, index_col=0)
    # rows here are samples; columns are analytes - transpose
    df = df.transpose()
    df = drop_uninformative(df, axis="index")
    return df


def run() -> dict:
    out = {"dataset": "OSD-656", "tables": {}}
    results_dir = ensure_results_dir()
    try:
        df = _load(URL)
    except Exception as e:
        out["tables"]["urine"] = {"error": str(e)}
        return out
    hits = find_concordant_changes(df, phase_a="post", phase_b="pre")
    write_hits_csv(hits, os.path.join(
        results_dir, "OSD-656_urine_post_vs_pre.csv"))
    out["tables"]["urine"] = {
        "n_features": int(df.shape[0]),
        "n_significant_all_4": len(hits),
        "hits": hits,
    }
    return out


if __name__ == "__main__":
    import json
    res = run()
    summary = res["tables"]["urine"]
    print(f"OSD-656 urine: n_features={summary.get('n_features')} "
          f"significant_in_all_4={summary.get('n_significant_all_4')}")
