"""
OSD-569: Blood RNA-seq (long-read) + m6A modification + CBC.

Three sub-tables:

  rna_blood : long-read direct RNA-seq gene expression. After header
              flattening, columns are  C00X_TIMEPOINT  (TIMEPOINTS:
              L-92, L-44, L-3, R+1 only - no in-flight). The file ALSO
              ships pre-computed DESeq2_log2FC / DESeq2_p-value /
              DESeq2_adjusted-p-value / pipeline-transcriptome-de_*
              columns; we drop those before doing the per-subject test.

  m6A       : direct-RNA m6A modification fractions per transcript
              position. Same C00X_TIMEPOINT layout. Has annotation
              columns (transcript_position, gene_ENSEMBL, gene_position)
              that must be dropped before the per-subject test.

  cbc       : long-format clinical CBC. Each row is one ANALYTE x
              SUBJECT_ID x TEST_DATE measurement. We pivot to a wide
              ANALYTE x sample matrix and drop the RANGE_MIN/RANGE_MAX
              accessory columns.

For all three: only post-vs-pre is meaningful (no in-flight blood draws).
"""

from __future__ import annotations
import os
import pandas as pd

from common import (
    drop_uninformative, find_concordant_changes,
    parse_sample, phase_of, ensure_results_dir, write_hits_csv,
)

RNA_URL = "https://osdr.nasa.gov/geode-py/ws/studies/OSD-569/download?source=datamanager&file=GLDS-561_long-readRNAseq_Direct_RNA_seq_Gene_Expression_Processed.xlsx"
M6A_URL = "https://osdr.nasa.gov/geode-py/ws/studies/OSD-569/download?source=datamanager&file=GLDS-561_directm6Aseq_Direct_RNA_seq_m6A_Processed_Data.xlsx"
CBC_URL = "https://osdr.nasa.gov/geode-py/ws/studies/OSD-569/download?source=datamanager&file=LSDS-7_Complete_Blood_Count_CBC.upload_SUBMITTED.csv"


def _is_crew_column(col: str) -> bool:
    crew, tp = parse_sample(str(col))
    return crew is not None and phase_of(tp) is not None


def _load_rna() -> pd.DataFrame:
    df = pd.read_excel(RNA_URL,
                       skiprows=[0, 1, 2, 3, 4, 5, 6, 9],
                       header=[0, 1], index_col=0)
    df.columns = [f"{a}_{b}".strip("_") for a, b in df.columns]
    # de-dupe columns: C004 sometimes appears twice; pandas suffixes ".1".
    # Strip the suffix and average duplicates (a defensible choice for
    # technical replicates).
    df.columns = [c.rsplit(".", 1)[0] if c.endswith((".1", ".2")) else c
                  for c in df.columns]
    # average any duplicate columns produced by Excel double-headers
    df = df.apply(pd.to_numeric, errors="coerce")
    df = df.T.groupby(level=0).mean().T
    df = df[[c for c in df.columns if _is_crew_column(c)]]
    return df


def _load_m6a() -> pd.DataFrame:
    df = pd.read_excel(M6A_URL,
                       skiprows=[0, 1, 2, 3, 4, 5, 6, 7],
                       header=[0, 1], index_col=0)
    df.columns = [f"{a}_{b}".strip("_") for a, b in df.columns]
    # drop annotation columns - keep only the C00X_TIMEPOINT measurement
    # columns
    df = df[[c for c in df.columns if _is_crew_column(c)]]
    return df


def _load_cbc() -> pd.DataFrame:
    """CBC arrives in long format - pivot to wide (rows=analytes,
    cols=C00X_serum_TIMEPOINT) so the standard machinery works."""
    raw = pd.read_csv(CBC_URL, index_col=0)
    # standardize: SUBJECT_ID like 'C001', TEST_DATE like 'L-92'
    raw = raw.reset_index().rename(columns={"index": "ANALYTE"})
    raw["sample"] = (raw["SUBJECT_ID"].astype(str) + "_blood_"
                     + raw["TEST_DATE"].astype(str))
    raw["VALUE"] = pd.to_numeric(raw["VALUE"], errors="coerce")
    wide = raw.pivot_table(index="ANALYTE", columns="sample",
                           values="VALUE", aggfunc="mean")
    return wide


def run() -> dict:
    out = {"dataset": "OSD-569", "tables": {}}
    results_dir = ensure_results_dir()

    for name, loader in (("rna_blood", _load_rna),
                         ("m6A",       _load_m6a),
                         ("cbc",       _load_cbc)):
        try:
            df = loader()
        except Exception as e:
            out["tables"][name] = {"error": str(e)}
            continue
        df = drop_uninformative(df, axis="index")
        hits = find_concordant_changes(df, phase_a="post", phase_b="pre")
        write_hits_csv(hits, os.path.join(
            results_dir, f"OSD-569_{name}_post_vs_pre.csv"))
        out["tables"][name] = {
            "n_features": int(df.shape[0]),
            "n_significant_all_4": len(hits),
            "hits": hits,
        }
    return out


if __name__ == "__main__":
    res = run()
    for name, t in res["tables"].items():
        if "error" in t:
            print(f"OSD-569 {name}: ERROR {t['error']}")
            continue
        print(f"OSD-569 {name}: features={t['n_features']} "
              f"significant_all_4={t['n_significant_all_4']}")
