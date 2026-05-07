"""
OSD-573: Dragon-capsule environmental swabs (4 metagenomics tables).

These are NOT per-crewmember samples - the columns are 'Communal_*'
(e.g. Communal_AllFlight_H20, Communal_L-92_H20). The "all four crew
significantly changed" framing therefore does NOT apply, and we cannot
run the per-subject test.

Instead, for each table we report:
   * the list of taxa / KO functions / pathways / gene families with
     non-zero abundance only in flight (i.e. "introduced during the
     mission") and
   * those that drop to zero post-flight ("did not persist"),
which is the most directly interesting "interesting change occurred"
question that the capsule data alone can answer.

We DO NOT include this dataset in the master list of "tests
significantly changed in all four subjects" - it's labeled
'environmental, not subject-stratified' in the master report.
"""

from __future__ import annotations
import os
import pandas as pd

from common import drop_uninformative, ensure_results_dir

URLS = {
    "kegg":     "https://osdr.nasa.gov/geode-py/ws/studies/OSD-573/download?source=datamanager&file=GLDS-565_GMetagenomics_Combined-gene-level-KO-function-coverages-CPM_GLmetagenomics.tsv",
    "taxonomy": "https://osdr.nasa.gov/geode-py/ws/studies/OSD-573/download?source=datamanager&file=GLDS-565_GMetagenomics_Combined-gene-level-taxonomy-coverages-CPM_GLmetagenomics.tsv",
    "pathway":  "https://osdr.nasa.gov/geode-py/ws/studies/OSD-573/download?source=datamanager&file=GLDS-565_GMetagenomics_Pathway-abundances-cpm_GLmetagenomics.tsv",
    "genefam":  "https://osdr.nasa.gov/geode-py/ws/studies/OSD-573/download?source=datamanager&file=GLDS-565_GMetagenomics_Gene-families-cpm_GLmetagenomics.tsv",
}


def _bin(col: str) -> str:
    """pre / during / post / unknown for capsule columns based on
    their L-/AllFlight/R+ tokens."""
    s = col
    if "AllFlight" in s or "_FD" in s or "_F+" in s: return "during"
    if "L-" in s:                                    return "pre"
    if "R+" in s:                                    return "post"
    return "unknown"


def _load(url: str) -> pd.DataFrame:
    df = pd.read_csv(url, index_col=0, sep="\t")
    df = drop_uninformative(df, axis="index")
    return df


def run() -> dict:
    out = {"dataset": "OSD-573",
           "note": "environmental capsule swabs - not subject-stratified;"
                   " excluded from per-subject 'all four crew' test",
           "tables": {}}
    results_dir = ensure_results_dir()
    for name, url in URLS.items():
        try:
            df = _load(url)
        except Exception as e:
            out["tables"][name] = {"error": str(e)}
            continue
        bins = {phase: [c for c in df.columns if _bin(str(c)) == phase]
                for phase in ("pre", "during", "post")}
        means = {p: df[cols].apply(pd.to_numeric,
                                   errors="coerce").mean(axis=1)
                 if cols else pd.Series(0.0, index=df.index)
                 for p, cols in bins.items()}
        introduced = means["during"][(means["pre"] <= 0)
                                     & (means["during"] > 0)].index.tolist()
        not_persisted = means["post"][(means["during"] > 0)
                                      & (means["post"] <= 0)].index.tolist()
        # write CSVs for traceability
        pd.Series(introduced, name="feature").to_csv(
            os.path.join(results_dir,
                         f"OSD-573_{name}_introduced_during_flight.csv"),
            index=False)
        pd.Series(not_persisted, name="feature").to_csv(
            os.path.join(results_dir,
                         f"OSD-573_{name}_not_persisted_post_flight.csv"),
            index=False)
        out["tables"][name] = {
            "n_features": int(df.shape[0]),
            "n_introduced_during_flight": len(introduced),
            "n_not_persisted_post_flight": len(not_persisted),
            "introduced": introduced[:50],   # truncate for memory
            "not_persisted": not_persisted[:50],
        }
    return out


if __name__ == "__main__":
    res = run()
    for name, t in res["tables"].items():
        if "error" in t:
            print(f"OSD-573 {name}: ERROR {t['error']}")
        else:
            print(f"OSD-573 {name}: features={t['n_features']} "
                  f"introduced={t['n_introduced_during_flight']} "
                  f"not_persisted={t['n_not_persisted_post_flight']}")
