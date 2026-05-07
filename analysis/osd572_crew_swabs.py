"""
OSD-572: Oral / nasal / skin microbial swabs from the crew.

Four matrices, all wide-format with columns like  C00X_TIMEPOINT_BODYSITE
(or  C00X_TIMEPOINT_BODYSITE_Abundance-CPM  for pathway / gene-family files):

    KEGG orthology coverage   (microbial molecular function)
    Taxonomy coverage         (taxon abundance, CPM)
    Pathway abundance         (pathway activity, CPM)
    Gene-family abundance     (gene-family CPM)

Body sites: ARM, EAR (post-auricular), GLU (gluteal), NAC (nasal cavity),
NAP (nasopharynx), ORC (oral cavity), PIT (axillary), TZO (toe-web zone),
UMB (umbilicus), WEB (toe web).

Per-body-site analysis: for each (feature, body site), check whether the
feature significantly changes between phases for ALL FOUR crewmembers in
the same direction. We do per-body-site so that signal at one anatomical
location is not diluted by noise at another.

Phases tested: during_vs_pre and post_vs_pre.
"""

from __future__ import annotations
import os
import re

import pandas as pd

from common import (
    CREW, drop_uninformative, find_concordant_changes,
    parse_sample, phase_of, ensure_results_dir, write_hits_csv,
)

URLS = {
    "kegg":     "https://osdr.nasa.gov/geode-py/ws/studies/OSD-572/download?source=datamanager&file=GLDS-564_GMetagenomics_Combined-gene-level-KO-function-coverages_GLmetagenomics.tsv",
    "taxonomy": "https://osdr.nasa.gov/geode-py/ws/studies/OSD-572/download?source=datamanager&file=GLDS-564_GMetagenomics_Combined-gene-level-taxonomy-coverages-CPM_GLmetagenomics.tsv",
    "pathway":  "https://osdr.nasa.gov/geode-py/ws/studies/OSD-572/download?source=datamanager&file=GLDS-564_GMetagenomics_Pathway-abundances-cpm_GLmetagenomics.tsv",
    "genefam":  "https://osdr.nasa.gov/geode-py/ws/studies/OSD-572/download?source=datamanager&file=GLDS-564_GMetagenomics_Gene-families-cpm_GLmetagenomics.tsv",
}

BODY_SITES = ("ARM", "EAR", "GLU", "NAC", "NAP",
              "ORC", "PIT", "TZO", "UMB", "WEB")

_SITE_RE = re.compile(r"_(ARM|EAR|GLU|NAC|NAP|ORC|PIT|TZO|UMB|WEB)\b")


def _site_of(col: str) -> str | None:
    m = _SITE_RE.search(col)
    return m.group(1) if m else None


def _columns_for_site(df: pd.DataFrame, site: str) -> list[str]:
    return [c for c in df.columns if _site_of(str(c)) == site]


def _is_crew_column(col: str) -> bool:
    crew, tp = parse_sample(str(col))
    return crew is not None and phase_of(tp) is not None


def _load(name: str, url: str) -> pd.DataFrame:
    df = pd.read_csv(url, index_col=0, sep="\t")
    # keep only crew columns we can place on the timeline
    df = df[[c for c in df.columns if _is_crew_column(c)]]
    # drop reference-range / unnamed style rows (none expected here, but
    # paranoia is cheap)
    df = drop_uninformative(df, axis="index")
    return df


def run() -> dict:
    out: dict = {"dataset": "OSD-572", "tables": {}}
    results_dir = ensure_results_dir()
    for name, url in URLS.items():
        try:
            df = _load(name, url)
        except Exception as e:
            out["tables"][name] = {"error": str(e)}
            continue
        per_site_hits: dict[str, dict] = {}
        for site in BODY_SITES:
            cols = _columns_for_site(df, site)
            if not cols:
                continue
            site_df = df[cols]
            during_hits = find_concordant_changes(site_df,
                                                  phase_a="during",
                                                  phase_b="pre")
            post_hits   = find_concordant_changes(site_df,
                                                  phase_a="post",
                                                  phase_b="pre")
            per_site_hits[site] = {
                "during_vs_pre": during_hits,
                "post_vs_pre":   post_hits,
            }
            for phase_label, hits in per_site_hits[site].items():
                write_hits_csv(
                    hits,
                    os.path.join(results_dir,
                                 f"OSD-572_{name}_{site}_{phase_label}.csv"))
        out["tables"][name] = {
            "n_features": int(df.shape[0]),
            "per_site": {s: {p: len(h) for p, h in v.items()}
                         for s, v in per_site_hits.items()},
            "hits": per_site_hits,
        }
    return out


if __name__ == "__main__":
    import json, sys
    res = run()
    summary = {k: v for k, v in res.items() if k != "tables"}
    summary["tables"] = {
        name: {"n_features": t.get("n_features"),
               "per_site":   t.get("per_site")}
        for name, t in res["tables"].items()
    }
    json.dump(summary, sys.stdout, indent=2)
