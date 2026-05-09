"""Per-astronaut microbiome → barrier → systemic flow diagram.

Renders the `flow_diagram` block of dashboard_data.json as a Sankey diagram
with one tab per astronaut. Edge colors encode evidence type:
  - shared_taxa_temporal: directional, supported by temporal precedence
  - correlation_only:     undirected association

This is the signature visual called out in README.md ("microbiome → barrier
→ immune flow diagram embedded in the immune and inflammation panels").
"""

from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

from guiv2 import config, data
from guiv2._plotly_theme import apply_clean_theme
from guiv2.components._chart_about import about_chart


def render_flow_diagram(view: dict, manifest: dict) -> None:
    st.subheader(view["title"])

    dashboard = data.load_json(view["json"])
    if not dashboard or "flow_diagram" not in dashboard:
        st.info("Flow-diagram block not present in the risk-profile JSON. "
                "Run risk_profile_claude/build_risk_profile.py to populate.")
        return

    flow = dashboard["flow_diagram"]
    per_astro = flow.get("per_astronaut", {})
    if not per_astro:
        st.info("No per-astronaut flow data available.")
        return

    crew_names = data.crew_display_names(manifest)
    astro_ids = [c for c in data.crew_columns(manifest) if c in per_astro]

    tab_labels = [crew_names.get(a, a) for a in astro_ids]
    tabs = st.tabs(tab_labels)
    for tab, astro_id in zip(tabs, astro_ids):
        with tab:
            _render_one_sankey(per_astro[astro_id], flow.get("evidence_legend", {}))

    about_chart(
        chart_type="Sankey diagram (4 layers: environment → host site → "
                   "barrier → systemic), one per astronaut",
        shows=("How spaceflight perturbations flow through the body for "
               "each crew member: from microbes detected on capsule "
               "surfaces (OSD-573), to the astronaut's body-site "
               "microbiome shifts (OSD-572 NAP/ARM), to the skin "
               "barrier transcriptomic response (OSD-574 FLG/CLDN/HAS), "
               "to the systemic R+1 inflammation composite (IL-6/TNF/CRP "
               "from OSD-575). Edge thickness = computed weight; edge "
               "color = evidence type."),
        x_axis="Layers, left → right: environment → host site → barrier → systemic",
        y_axis=("Each node's relative magnitude is encoded by node "
                "color/position. Edge weight = √(product of normalized "
                "source and target magnitudes), unitless and clipped to "
                "[0.05, 1] for visual readability. The capsule→host "
                "edges include the actual shared-taxa fraction (96% NAP, "
                "87% ARM) as part of the weight."),
        why=("A Sankey is the natural fit when you have a directional "
             "chain with thickness-encoded magnitudes at each step. The "
             "four-layer left-to-right reading mirrors the README's "
             "biological story (capsule → barrier → immune). The same "
             "data as a network diagram would lose the layer ordering."),
    )


def _render_one_sankey(graph: dict, legend: dict) -> None:
    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])
    if not nodes or not edges:
        st.info("Empty graph for this astronaut.")
        return

    # Sankey requires integer node indices; build a label/color/x-position
    # list and a name→index map.
    node_ids = [n["id"] for n in nodes]
    id_to_idx = {nid: i for i, nid in enumerate(node_ids)}
    node_labels = [n.get("label", n["id"]) for n in nodes]

    # color by layer
    node_colors = [config.SANKEY_LAYER_COLORS.get(n.get("layer"), "#888")
                   for n in nodes]

    # column positions: derive from layer order so the diagram reads
    # left → right as environment, host_site, barrier, systemic
    layer_x = {"environment": 0.05, "host_site": 0.35,
               "barrier": 0.65, "systemic": 0.95}
    node_x = [layer_x.get(n.get("layer"), None) for n in nodes]
    has_x = all(x is not None for x in node_x)

    # build edges; skip any that reference unknown nodes
    sources, targets, values, link_colors, link_hovers = [], [], [], [], []
    for e in edges:
        s_idx = id_to_idx.get(e["source"])
        t_idx = id_to_idx.get(e["target"])
        if s_idx is None or t_idx is None:
            continue
        sources.append(s_idx)
        targets.append(t_idx)
        values.append(max(float(e.get("weight", 0.0)), 0.01))
        ev = e.get("evidence", "correlation_only")
        link_colors.append(
            config.SANKEY_EDGE_COLORS.get(ev, "rgba(154,163,173,0.4)"))
        link_hovers.append(
            f"{node_labels[s_idx]} → {node_labels[t_idx]}<br>"
            f"weight: {e.get('weight', 0.0):.2f}<br>"
            f"evidence: {ev}")

    fig = go.Figure(go.Sankey(
        arrangement="snap",
        node=dict(
            pad=18, thickness=18,
            line=dict(color="white", width=0.5),
            label=node_labels,
            color=node_colors,
            x=node_x if has_x else None,
            customdata=[f"magnitude: {n.get('magnitude', 0.0):+.2f}"
                        for n in nodes],
            hovertemplate="<b>%{label}</b><br>%{customdata}<extra></extra>",
        ),
        link=dict(
            source=sources, target=targets, value=values,
            color=link_colors,
            customdata=link_hovers,
            hovertemplate="%{customdata}<extra></extra>",
        ),
    ))
    fig.update_layout(
        height=460,
        margin=dict(l=10, r=10, t=10, b=10),
        font=dict(size=12),
    )
    apply_clean_theme(fig, transparent=False)
    st.plotly_chart(fig, use_container_width=True)

    if legend:
        with st.expander("Evidence legend"):
            for k, v in legend.items():
                st.markdown(f"- **`{k}`** — {v}")
