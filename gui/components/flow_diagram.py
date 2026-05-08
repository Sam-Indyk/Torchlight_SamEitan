"""Capsule → crew → barrier flow diagram. Placeholder until CSV-driven design lands."""

import streamlit as st


def render_flow_diagram(view: dict, manifest: dict) -> None:
    st.subheader(view["title"])
    st.info(
        "Flow diagram component is scaffolded but not yet wired to data. "
        "Will render a three-column Sankey: capsule taxa (OSD-573) → crew "
        "body sites (OSD-572) → skin barrier transcriptomics (OSD-574)."
    )
    st.caption(f"Sources: {view.get('sources', {})}")
