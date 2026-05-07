"""
OSD-570: PBMC profiling.

  snrnaseq  : single-nucleus RNA-seq DIFFERENTIAL EXPRESSION table
              (already pooled across subjects). Columns: p_val,
              avg_log2FC, pct.1, pct.2, p_val_adj, Cell Type.
              Use the pre-aggregated padj filter; per-subject test
              not possible.

  snatacseq : single-nucleus ATAC-seq DIFFERENTIAL ACCESSIBILITY table
              with the same shape (regions x DE stats). Pooled.

  vdj       : T-cell / B-cell V(D)J clonotype table - long format with
              one row per clonotype contig. Has crewID and timepoint
              columns. We pivot ClonalPool size (an integer per crew x
              timepoint x clonotype-grouping) to a wide matrix and run
              the per-subject test on the per-group totals.

For snRNA / snATAC the "all four crew significantly changed" framing
doesn't fit (data already pooled), so we report features with
adjusted p < 0.05 and |log2FC| >= 1 and label them as pooled hits.
"""

from __future__ import annotations
import os
import pandas as pd

from common import (
    find_de_significant, find_concordant_changes,
    parse_sample, phase_of, ensure_results_dir, write_hits_csv,
    PADJ_THRESHOLD, LOG2FC_THRESHOLD,
)

SNRNA_URL  = "https://osdr.nasa.gov/geode-py/ws/studies/OSD-570/download?source=datamanager&file=GLDS-562_snRNA-Seq_PBMC_Gene_Expression_snRNA-seq_Processed_Data.xlsx"
SNATAC_URL = "https://osdr.nasa.gov/geode-py/ws/studies/OSD-570/download?source=datamanager&file=GLDS-562_snATAC-Seq_PBMC_Chromatin_Accessibility_snATAC-seq_Processed_Data.xlsx"
VDJ_URL    = "https://osdr.nasa.gov/geode-py/ws/studies/OSD-570/download?source=datamanager&file=GLDS-562_scRNA-Seq_VDJ_Results.xlsx"


def _load_snrna() -> pd.DataFrame:
    return pd.read_excel(SNRNA_URL,
                         skiprows=[0, 1, 2, 3, 4, 5, 6], index_col=0)


def _load_snatac() -> pd.DataFrame:
    return pd.read_excel(SNATAC_URL,
                         skiprows=[0, 1, 2, 3, 4, 5, 6], index_col=0)


def _load_vdj() -> pd.DataFrame:
    return pd.read_excel(VDJ_URL, skiprows=[0, 1, 2], index_col=0)


def _vdj_to_wide(vdj: pd.DataFrame) -> pd.DataFrame:
    """Per-clonotype-Grouping x sample matrix of total ClonalPool size.

    Grouping (e.g. 'TCR_C1_3') already encodes crew+timepoint, but the
    crewID and timepoint columns are present and authoritative. We build
    sample names of the form  C00X_pbmc_TIMEPOINT  so the standard
    parse_sample pipeline picks them up.
    """
    if "crewID" not in vdj.columns or "timepoint" not in vdj.columns:
        raise KeyError("VDJ table missing crewID or timepoint")
    df = vdj.copy()
    df["sample"] = (df["crewID"].astype(str) + "_pbmc_"
                    + df["timepoint"].astype(str))
    if "ClonalPool" in df.columns:
        df["ClonalPool"] = pd.to_numeric(df["ClonalPool"], errors="coerce")
    grouping = df["Grouping"] if "Grouping" in df.columns else df.index
    wide = (df.assign(grouping=grouping)
              .pivot_table(index="grouping", columns="sample",
                           values="ClonalPool", aggfunc="sum",
                           fill_value=0))
    return wide


def run() -> dict:
    out = {"dataset": "OSD-570", "tables": {}}
    results_dir = ensure_results_dir()

    # snRNA-seq DE
    try:
        snrna = _load_snrna()
        hits = find_de_significant(snrna, padj_col="p_val_adj",
                                   lfc_col="avg_log2FC",
                                   padj_threshold=PADJ_THRESHOLD,
                                   lfc_threshold=LOG2FC_THRESHOLD)
        write_hits_csv(hits, os.path.join(
            results_dir, "OSD-570_snrnaseq_pooled_DE.csv"))
        out["tables"]["snrnaseq"] = {
            "mode": "pre_aggregated_DE",
            "n_features": int(snrna.shape[0]),
            "n_significant_pooled": len(hits),
            "hits": hits,
        }
    except Exception as e:
        out["tables"]["snrnaseq"] = {"error": str(e)}

    # snATAC-seq DE
    try:
        snatac = _load_snatac()
        hits = find_de_significant(snatac, padj_col="p_val_adj",
                                   lfc_col="avg_log2FC",
                                   padj_threshold=PADJ_THRESHOLD,
                                   lfc_threshold=LOG2FC_THRESHOLD)
        write_hits_csv(hits, os.path.join(
            results_dir, "OSD-570_snatacseq_pooled_DE.csv"))
        out["tables"]["snatacseq"] = {
            "mode": "pre_aggregated_DE",
            "n_features": int(snatac.shape[0]),
            "n_significant_pooled": len(hits),
            "hits": hits,
        }
    except Exception as e:
        out["tables"]["snatacseq"] = {"error": str(e)}

    # VDJ - per-subject if structure allows
    try:
        vdj  = _load_vdj()
        wide = _vdj_to_wide(vdj)
        # restrict to columns we can place
        keep = [c for c in wide.columns
                if parse_sample(str(c))[0] is not None
                and phase_of(parse_sample(str(c))[1]) is not None]
        wide = wide[keep]
        hits = find_concordant_changes(wide, phase_a="post", phase_b="pre")
        write_hits_csv(hits, os.path.join(
            results_dir, "OSD-570_vdj_post_vs_pre.csv"))
        out["tables"]["vdj"] = {
            "mode": "per_subject_clonotype_grouping",
            "n_features": int(wide.shape[0]),
            "n_significant_all_4": len(hits),
            "hits": hits,
        }
    except Exception as e:
        out["tables"]["vdj"] = {"error": str(e)}
    return out


if __name__ == "__main__":
    res = run()
    for name, t in res["tables"].items():
        if "error" in t:
            print(f"OSD-570 {name}: ERROR {t['error']}")
        else:
            print(f"OSD-570 {name}: {t}")
