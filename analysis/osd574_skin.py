"""
OSD-574: Spatial transcriptomics of skin biopsy + skin metagenomics
(KEGG / taxonomy / pathway / gene-family).

  spatial : pre-aggregated DESeq2 DE table for skin spatial
            transcriptomics. Columns: baseMean, log2FoldChange, lfcSE,
            stat, pvalue, padj. Pooled - so we use the DE filter.

  skin metagenomics (4 files): wide format C00X_TIMEPOINT_BODYSITE
            with body-site codes. Same machinery as OSD-572.

For the metagenomics tables, we test during_vs_pre and post_vs_pre
per body site.
"""

from __future__ import annotations
import os
import re
import pandas as pd

from common import (
    drop_uninformative, find_concordant_changes, find_de_significant,
    parse_sample, phase_of, ensure_results_dir, write_hits_csv,
    PADJ_THRESHOLD, LOG2FC_THRESHOLD,
)

SPATIAL_URL = "https://osdr.nasa.gov/geode-py/ws/studies/OSD-570/download?source=datamanager&file=GLDS-566_SpatialTranscriptomics_Skin_Biopsy_Spatially_Resolved_Transcriptomics_Processed_Data.xlsx"

METAGEN_URLS = {
    "kegg":     "https://osdr.nasa.gov/geode-py/ws/studies/OSD-574/download?source=datamanager&file=GLDS-566_GMetagenomics_Combined-gene-level-KO-function-coverages-CPM_GLmetagenomics.tsv",
    "taxonomy": "https://osdr.nasa.gov/geode-py/ws/studies/OSD-574/download?source=datamanager&file=GLDS-566_GMetagenomics_Combined-gene-level-taxonomy-coverages-CPM_GLmetagenomics.tsv",
    "pathway":  "https://osdr.nasa.gov/geode-py/ws/studies/OSD-574/download?source=datamanager&file=GLDS-566_GMetagenomics_Pathway-abundances-cpm_GLmetagenomics.tsv",
    "genefam":  "https://osdr.nasa.gov/geode-py/ws/studies/OSD-574/download?source=datamanager&file=GLDS-566_GMetagenomics_Gene-families-cpm_GLmetagenomics.tsv",
}

# lookahead for non-alphanumeric (treats '_' as a separator) - the '\b'
# form misses 'C001_FD2_ARM_Abundance-CPM'-style columns.
_SITE_RE = re.compile(
    r"_(ARM|EAR|GLU|NAC|NAP|ORC|PIT|TZO|UMB|WEB)(?![A-Za-z0-9])")


def _load_spatial() -> pd.DataFrame:
    return pd.read_excel(SPATIAL_URL,
                         skiprows=[0, 1, 2, 3, 4, 5, 6], index_col=0)


def _load_metagen(url: str) -> pd.DataFrame:
    df = pd.read_csv(url, index_col=0, sep="\t", low_memory=False)
    df = df[[c for c in df.columns
             if parse_sample(str(c))[0] is not None
             and phase_of(parse_sample(str(c))[1]) is not None]]
    df = drop_uninformative(df, axis="index")
    return df


def run() -> dict:
    out = {"dataset": "OSD-574", "tables": {}}
    results_dir = ensure_results_dir()

    # spatial DE
    try:
        sp = _load_spatial()
        hits = find_de_significant(sp, padj_col="padj",
                                   lfc_col="log2FoldChange",
                                   padj_threshold=PADJ_THRESHOLD,
                                   lfc_threshold=LOG2FC_THRESHOLD)
        write_hits_csv(hits, os.path.join(
            results_dir, "OSD-574_spatial_pooled_DE.csv"))
        out["tables"]["spatial"] = {
            "mode": "pre_aggregated_DE",
            "n_features": int(sp.shape[0]),
            "n_significant_pooled": len(hits),
            "hits": hits,
        }
    except Exception as e:
        out["tables"]["spatial"] = {"error": str(e)}

    # skin metagenomics (per body site)
    for name, url in METAGEN_URLS.items():
        print(f"  [OSD-574] skin_{name}: downloading...", flush=True)
        try:
            df = _load_metagen(url)
        except Exception as e:
            print(f"  [OSD-574] skin_{name}: ERROR {e}", flush=True)
            out["tables"][f"skin_{name}"] = {"error": str(e)}
            continue
        print(f"  [OSD-574] skin_{name}: {df.shape[0]} features x "
              f"{df.shape[1]} crew samples", flush=True)
        site_of = {c: (m.group(1) if (m := _SITE_RE.search(str(c)))
                       else None) for c in df.columns}
        sites = sorted({s for s in site_of.values() if s})
        per_site = {}
        for site in sites:
            cols = [c for c, s in site_of.items() if s == site]
            if not cols:
                continue
            sub = df[cols]
            during = find_concordant_changes(sub, "during", "pre")
            post   = find_concordant_changes(sub, "post",   "pre")
            per_site[site] = {"during_vs_pre": during, "post_vs_pre": post}
            for label, hits in per_site[site].items():
                write_hits_csv(hits, os.path.join(
                    results_dir, f"OSD-574_skin_{name}_{site}_{label}.csv"))
        out["tables"][f"skin_{name}"] = {
            "n_features": int(df.shape[0]),
            "per_site": {s: {p: len(h) for p, h in v.items()}
                         for s, v in per_site.items()},
            "hits": per_site,
        }
    return out


if __name__ == "__main__":
    res = run()
    for name, t in res["tables"].items():
        if "error" in t:
            print(f"OSD-574 {name}: ERROR {t['error']}")
        else:
            print(f"OSD-574 {name}: { {k: t[k] for k in t if k != 'hits'} }")
