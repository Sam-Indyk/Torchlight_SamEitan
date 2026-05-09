"""guiv2 — Streamlit entry point.

Run from repo root:
    streamlit run guiv2/app.py

guiv2 is the unified hackathon submission. It integrates:
  - Track 2 risk-profile panels (per-astronaut trajectories, four axes)
    consuming data/dashboard_data.json produced by
    risk_profile_claude/build_risk_profile.py
  - Microbiome and systemic molecular-perturbation panels (CSV-driven)
    consuming analysis/results/ directly, adapted from gui/ (Eitan's
    Streamlit scaffold).
  - The signature microbiome → barrier → immune flow diagram.
  - A top-of-page honesty banner that surfaces null findings and n=4
    methodological caveats up front.

Adding or reordering panels = edit guiv2/manifest.json. No code change.
"""

import sys
from pathlib import Path

# Make repo root importable so `guiv2.foo` works regardless of launch cwd.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st

from guiv2 import config, data
from guiv2.components import RENDERERS
from guiv2.components.honesty_banner import render_honesty_banner


def main() -> None:
    st.set_page_config(
        page_title=config.PAGE_TITLE,
        page_icon=config.PAGE_ICON,
        layout=config.LAYOUT,
    )

    # Optional global stylesheet
    css_path = Path(__file__).resolve().parent / "assets" / "styles.css"
    if css_path.exists():
        st.markdown(f"<style>{css_path.read_text()}</style>",
                    unsafe_allow_html=True)

    manifest = data.load_manifest(config.MANIFEST_PATH)
    meta = manifest["metadata"]

    st.title(config.PAGE_TITLE)
    st.caption(
        f"{config.PAGE_SUBTITLE} · {meta['mission']} · "
        f"n = {len(meta['crew'])} crew · "
        f"per-subject filter: {meta['filter_criteria']['per_subject_concordance']}, "
        f"|log2FC| ≥ {meta['filter_criteria']['per_subject_log2fc_threshold']}"
    )

    render_honesty_banner(meta.get("honesty_notes", []))

    panel_labels = [p["label"] for p in manifest["panels"]]
    tabs = st.tabs(panel_labels)
    for tab, panel in zip(tabs, manifest["panels"]):
        with tab:
            if panel.get("intro_md"):
                st.markdown(panel["intro_md"])
                st.divider()
            for view in panel["views"]:
                renderer = RENDERERS.get(view["type"])
                if renderer is None:
                    st.warning(f"No renderer for view type: `{view['type']}`. "
                               "Add it to guiv2/components/ and register in "
                               "guiv2/components/__init__.py.")
                    continue
                renderer(view, manifest)
                st.divider()


if __name__ == "__main__":
    main()
