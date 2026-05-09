"""Data Sources & Provenance panel.

Renders a card grid documenting every dataset and external reference the
dashboard pulls from. Two sections:

  1. INTERNAL: the nine OSDR datasets the analysis pipeline already ingests
     (per analysis/results/ and the OSDR cache).
  2. EXTERNAL / PUBLISHED: the literature-derived population reference values
     and prior-cohort overlays added in the risk-profile layer
     (risk_profile_claude/population_reference.py and published_priors.py).

This is what judges open when they want to know what's *real* and what's
*calibrated* in the dashboard.
"""

from __future__ import annotations

import streamlit as st

from guiv2 import config, data
from risk_profile_claude.population_reference import EVE_REFS  # type: ignore
from risk_profile_claude.published_priors import PRIORS         # type: ignore


# ---- internal datasets table ----------------------------------------------

INTERNAL_DATASETS: list[dict] = [
    {"id": "OSD-572", "name": "Crew skin / oral / nasal swabs",
     "modality": "Metagenomics (taxonomy + KEGG + pathway + gene-family)",
     "role": "Per-astronaut microbiome shifts at 10 body sites",
     "phases": "Pre / In-flight (FD2-FD3) / Post"},
    {"id": "OSD-573", "name": "Capsule cabin swabs",
     "modality": "Metagenomics",
     "role": "Environmental microbiome source pool (3,585 taxa during flight)",
     "phases": "Pre / In-flight / Post"},
    {"id": "OSD-574", "name": "Spatial skin transcriptomics",
     "modality": "10x Visium spatial, deltoid biopsy",
     "role": "Skin barrier-gene expression (DES, TAGLN, ACTA2, GSN, etc.)",
     "phases": "Pre / Post (ground-only)"},
    {"id": "OSD-569", "name": "Whole-blood transcriptomics + CBC",
     "modality": "Long-read direct-RNA seq + m6A + standard CBC",
     "role": "DDR gene signature, post-transcriptional regulation, hematology",
     "phases": "Pre / Post (ground-only)"},
    {"id": "OSD-570", "name": "PBMC immune profiling",
     "modality": "snRNA-seq + snATAC-seq + V(D)J",
     "role": "Immune-cell composition; ribosomal-protein suppression signal",
     "phases": "Pre / Post (ground-only)"},
    {"id": "OSD-571", "name": "Plasma metabolomics + proteomics + EVP",
     "modality": "Pre-aggregated limma DE tables",
     "role": "Mitochondrial readout (TCA, acylcarnitines); lipid signature",
     "phases": "Pre / Post (cohort pooled)"},
    {"id": "OSD-575", "name": "Serum CMP + cytokines + cardio",
     "modality": "Quest CMP + Eve Luminex + Alamar Olink",
     "role": "Inflammation (IL-6/TNF/CRP), Th1/Th2/Treg cytokines",
     "phases": "Pre / Post (ground-only)"},
    {"id": "OSD-630", "name": "Stool metagenomics",
     "modality": "Shotgun metagenomics",
     "role": "Gut microbiome shifts (no concordant signal at 4-of-4 bar)",
     "phases": "Pre / Post (ground-only)"},
    {"id": "OSD-656", "name": "Urine inflammation panel",
     "modality": "Alamar multiplex",
     "role": "Renal/systemic inflammation markers",
     "phases": "Pre / Post (ground-only)"},
]


def render_data_provenance(view: dict, manifest: dict) -> None:
    st.subheader(view["title"])

    # ---- internal -------------------------------------------------------
    st.markdown("### OSDR datasets (internal)")
    st.caption(
        "Read directly from `analysis/.cache/` (raw OSDR downloads) and "
        "`analysis/results/` (per-dataset DE CSVs produced by "
        "`analysis/master.py`). The dashboard never recomputes these — "
        "if a number looks wrong, the partner's pipeline is the source of "
        "truth, not the GUI."
    )
    cols = st.columns(3, gap="medium")
    for i, ds in enumerate(INTERNAL_DATASETS):
        with cols[i % 3]:
            st.markdown(
                f"""
                <div class="provenance-card provenance-internal">
                  <div class="prov-id">{ds['id']}</div>
                  <div class="prov-name">{ds['name']}</div>
                  <div class="prov-row"><span>Modality:</span> {ds['modality']}</div>
                  <div class="prov-row"><span>Used for:</span> {ds['role']}</div>
                  <div class="prov-row"><span>Phases:</span> {ds['phases']}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    st.divider()

    # ---- external population reference ----------------------------------
    st.markdown("### Population reference values (external literature)")
    st.caption(
        "Hardcoded in [`risk_profile_claude/population_reference.py`]"
        "(../risk_profile_claude/population_reference.py). "
        "Used to populate the `population_z` channel — \"how many SDs is "
        "this astronaut outside the healthy-adult range?\" — for cytokines "
        "whose CSV does not embed a clinical reference range. Calibrated "
        "to the Eve / Luminex pg/mL scale; the methods note in each axis "
        "panel reports which references applied."
    )
    pop_rows = []
    for key, entry in EVE_REFS.items():
        pop_rows.append({
            "Analyte (substring match)": key.upper().replace("_", "-"),
            "Healthy median (pg/mL)":   f"{entry['median']:g}",
            "SD (pg/mL)":               f"{entry['sd']:g}",
            "Source":                    entry["source"],
            "Notes":                     entry.get("notes", ""),
        })
    st.dataframe(pop_rows, hide_index=True, use_container_width=True)

    st.divider()

    # ---- external prior-cohort overlays --------------------------------
    st.markdown("### Prior-cohort R+1 overlays (Tierney 2024 / Park 2024)")
    st.caption(
        "Hardcoded in [`risk_profile_claude/published_priors.py`]"
        "(../risk_profile_claude/published_priors.py). "
        "Drawn as a dashed reference line on each axis trajectory chart. "
        "Marked `is_approximate=True` because magnitudes are converted "
        "from the reported fold-changes rather than lifted from "
        "supplementary tables verbatim. Replacing any of these with a "
        "verbatim number is a one-line edit in that file."
    )
    prior_rows = []
    for axis_id, entry in PRIORS.items():
        prior_rows.append({
            "Axis":                axis_id,
            "Reference TP":        entry.get("tp", "R+1"),
            "Estimated R+1 z":    f"{entry.get('r1_score_estimate', 0):+.1f}",
            "Source":              entry.get("source", ""),
            "Approximate?":        "yes" if entry.get("is_approximate") else "no",
        })
    st.dataframe(prior_rows, hide_index=True, use_container_width=True)

    st.divider()

    # ---- how-the-pipeline-flows ----------------------------------------
    st.markdown("### How the data flows through the dashboard")
    st.markdown(
        """
        ```
         OSDR endpoints  ─── analysis/master.py ───►  analysis/.cache/*.csv,xlsx,tsv
                                                       │
                                                       ▼
                                                analysis/results/*.csv
                                                       │
                            ┌──────────────────────────┴──────────────────┐
                            ▼                                              ▼
                     risk_profile_claude/                       guiv2/components/
                     build_risk_profile.py                      per_subject_table.py
                     (computes own-baseline z,                  pooled_table.py
                      population z, Mahalanobis,
                      recovery τ, multi-system                  (read CSVs directly,
                      Mahalanobis, real flow                     no recompute)
                      diagram correlations)
                            │
                            ▼
                  data/dashboard_data.json
                  (single contract for risk panels;
                   schema in risk_profile_claude/SCHEMA.md)
                            │
                            ▼
                guiv2/components/risk_axis_panel.py,
                                 risk_overview.py,
                                 multi_system_panel.py,
                                 report_card.py,
                                 flow_diagram.py
        ```
        """
    )
    st.caption(
        "Eitan's CSV-driven Streamlit scaffold (gui/) and Claude's "
        "JSON-driven scoring layer (risk_profile_claude/) coexist in "
        "guiv2 — each panel pulls from whichever source is appropriate. "
        "The molecular-perturbation tabs read CSVs directly; the risk-"
        "profile tabs read the precomputed JSON."
    )
