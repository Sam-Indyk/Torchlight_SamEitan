"""Streamlit entry point. Run from repo root:

    streamlit run gui/app.py
"""

import sys
from pathlib import Path

# Make the repo root importable so `gui.foo` works whether you launch from
# the repo root or `gui/`.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st

from gui import config, data
from gui.components import RENDERERS
from gui.components.honesty_banner import render_honesty_banner


def main() -> None:
    st.set_page_config(
        page_title=config.PAGE_TITLE,
        page_icon=config.PAGE_ICON,
        layout=config.LAYOUT,
    )

    manifest = data.load_manifest(config.MANIFEST_PATH)
    meta = manifest["metadata"]

    st.title(config.PAGE_TITLE)
    st.caption(
        f"{meta['mission']} · n = {len(meta['crew'])} crew · "
        f"filter: {meta['filter_criteria']['per_subject_concordance']}, "
        f"|log2FC| ≥ {meta['filter_criteria']['per_subject_log2fc_threshold']}"
    )

    render_honesty_banner(meta.get("honesty_notes", []))

    panel_labels = [p["label"] for p in manifest["panels"]]
    tabs = st.tabs(panel_labels)
    for tab, panel in zip(tabs, manifest["panels"]):
        with tab:
            if panel.get("intro_md"):
                st.markdown(panel["intro_md"])
            for view in panel["views"]:
                renderer = RENDERERS.get(view["type"])
                if renderer is None:
                    st.warning(f"No renderer for view type: {view['type']}")
                    continue
                renderer(view, manifest)
                st.divider()


if __name__ == "__main__":
    main()
