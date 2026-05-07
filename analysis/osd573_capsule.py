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
    df = pd.read_csv(url, index_col=0, sep="\t", low_memory=False)
    df = drop_uninformative(df, axis="index")
    return df


def run() -> dict:
    out = {"dataset": "OSD-573",
           "note": "environmental capsule swabs - not subject-stratified;"
                   " excluded from per-subject 'all four crew' test",
           "tables": {}}
    results_dir = ensure_results_dir()
    for name, url in URLS.items():
        print(f"  [OSD-573] {name}: downloading...", flush=True)
        try:
            df = _load(url)
        except Exception as e:
            print(f"  [OSD-573] {name}: ERROR {e}", flush=True)
            out["tables"][name] = {"error": str(e)}
            continue
        bins = {phase: [c for c in df.columns if _bin(str(c)) == phase]
                for phase in ("pre", "during", "post")}
        unknown_cols = [str(c) for c in df.columns if _bin(str(c)) == "unknown"]
        n_per_phase = {p: len(cols) for p, cols in bins.items()}

        # only compute means for phases that actually have columns - the
        # previous code defaulted missing phases to 0.0 across the board,
        # which made "introduced" and "not persisted" collapse to the
        # same 'during > 0' filter and produced byte-identical lists.
        means: dict[str, pd.Series] = {}
        for p, cols in bins.items():
            if cols:
                means[p] = (df[cols].apply(pd.to_numeric, errors="coerce")
                                    .mean(axis=1))

        result = {
            "n_features": int(df.shape[0]),
            "samples_per_phase": n_per_phase,
            "n_unclassified_columns": len(unknown_cols),
            "first_5_unclassified_columns": unknown_cols[:5],
            "first_10_columns_seen": [str(c) for c in df.columns[:10]],
        }

        # introduced-during-flight: requires both pre and during columns
        if "pre" in means and "during" in means:
            introduced = means["during"][
                (means["pre"] <= 0) & (means["during"] > 0)
            ].index.tolist()
            pd.Series(introduced, name="feature").to_csv(
                os.path.join(results_dir,
                             f"OSD-573_{name}_introduced_during_flight.csv"),
                index=False)
            result["n_introduced_during_flight"] = len(introduced)
            result["introduced"] = introduced[:50]
        else:
            result["n_introduced_during_flight"] = None
            result["introduced_skipped_reason"] = (
                f"missing phase columns - have {sorted(means.keys())}")

        # not-persisted-post-flight: requires both during and post columns
        if "during" in means and "post" in means:
            not_persisted = means["post"][
                (means["during"] > 0) & (means["post"] <= 0)
            ].index.tolist()
            pd.Series(not_persisted, name="feature").to_csv(
                os.path.join(results_dir,
                             f"OSD-573_{name}_not_persisted_post_flight.csv"),
                index=False)
            result["n_not_persisted_post_flight"] = len(not_persisted)
            result["not_persisted"] = not_persisted[:50]
        else:
            result["n_not_persisted_post_flight"] = None
            result["not_persisted_skipped_reason"] = (
                f"missing phase columns - have {sorted(means.keys())}")

        # always emit a "during-flight detected" list when we have during
        # columns - the most concrete capsule-only finding regardless of
        # whether pre/post are available
        if "during" in means:
            during_only = means["during"][means["during"] > 0].index.tolist()
            pd.Series(during_only, name="feature").to_csv(
                os.path.join(results_dir,
                             f"OSD-573_{name}_detected_during_flight.csv"),
                index=False)
            result["n_detected_during_flight"] = len(during_only)

        out["tables"][name] = result
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
