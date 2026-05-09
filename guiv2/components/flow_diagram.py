"""Per-astronaut microbiome → barrier → systemic flow (inline SVG).

Replaces the Plotly Sankey, which crammed long node labels into narrow
columns and hid every magnitude behind hover. Same data
(`dashboard_data.json["flow_diagram"]`), same four layers
(environment → host site → barrier → systemic), but laid out as a
custom SVG with:

  - Column headers at the top spelling out each layer
  - Each node as a rounded card with its label and signed magnitude
    visible inline (red if positive, blue if suppressed)
  - Curved edges between cards with thickness scaled to edge weight
    and the weight value labeled at the edge midpoint
  - A clear colour key below the chart for layer color, edge weight,
    and node magnitude direction
  - Native browser tooltips on every node and edge

This is the signature visual called out in README.md.
"""

from __future__ import annotations

import html as _html

import streamlit as st
import streamlit.components.v1 as components

from guiv2 import config, data
from guiv2.components._chart_about import about_chart


# ---------------------------------------------------------------------------
# layout knobs
# ---------------------------------------------------------------------------

LAYERS = ["environment", "host_site", "barrier", "systemic"]
LAYER_LABEL = {
    "environment": "ENVIRONMENT",
    "host_site":   "HOST SITE",
    "barrier":     "BARRIER",
    "systemic":    "SYSTEMIC",
}
LAYER_SUB = {
    "environment": "what's on the capsule",
    "host_site":   "what's on the crew",
    "barrier":     "skin barrier response",
    "systemic":    "blood-borne signal",
}

# canvas
W, H = 1180, 720
HEADER_TOP = 30
NODE_TOP = 110         # where the first node row starts
NODE_W, NODE_H = 230, 92

# four equally-spaced column centers
COL_X = {l: int((i + 0.5) * W / len(LAYERS)) for i, l in enumerate(LAYERS)}


# ---------------------------------------------------------------------------
# rendering
# ---------------------------------------------------------------------------

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

    cohort = flow.get("cohort_level_facts", {}) or {}

    st.markdown(
        f"<div style='background:{config.COLOR_BG_BANNER};"
        f"color:{config.COLOR_PRIMARY};padding:12px 16px;border-radius:8px;"
        f"border-left:4px solid {config.COLOR_ICE};margin-bottom:14px;'>"
        f"<strong>What this chart measures.</strong> For each astronaut, "
        f"a four-step chain from the cabin environment to the systemic "
        f"inflammation signal at R+1. Each step shows a single node value "
        f"(signed deviation, in own-baseline z-units for cytokines and "
        f"normalized magnitude for microbiome / barrier). Edge thickness "
        f"is the computed coupling between adjacent nodes; the number "
        f"on each edge is that coupling weight."
        f"</div>",
        unsafe_allow_html=True,
    )

    # cohort-level facts as a one-liner above the per-astronaut tabs
    facts = []
    if "capsule_to_NAP_shared_fraction" in cohort:
        facts.append(
            f"**Capsule→crew NAP overlap:** "
            f"{100*cohort['capsule_to_NAP_shared_fraction']:.0f}%"
        )
    if "capsule_to_ARM_shared_fraction" in cohort:
        facts.append(
            f"**Capsule→crew ARM overlap:** "
            f"{100*cohort['capsule_to_ARM_shared_fraction']:.0f}%"
        )
    if "barrier_pooled_signed_mean" in cohort:
        facts.append(
            f"**Barrier pooled mean log2FC:** "
            f"{cohort['barrier_pooled_signed_mean']:+.2f}"
        )
    if facts:
        st.markdown(" · ".join(facts))

    crew_names = data.crew_display_names(manifest)
    astro_ids = [c for c in data.crew_columns(manifest) if c in per_astro]
    tab_labels = [crew_names.get(a, a) for a in astro_ids]
    tabs = st.tabs(tab_labels)
    for tab, astro_id in zip(tabs, astro_ids):
        with tab:
            svg = _build_svg(per_astro[astro_id])
            components.html(svg, height=H + 60, scrolling=False)

    # legend
    st.markdown(_legend_html(flow.get("evidence_legend", {})),
                unsafe_allow_html=True)

    about_chart(
        chart_type="Custom SVG flow diagram (4 columns, labeled cards, curved edges)",
        shows=("How spaceflight signal moves from the cabin environment "
               "(OSD-573 capsule taxa) through the astronaut's body-site "
               "microbiome (OSD-572 NAP/ARM swabs) through the skin "
               "barrier transcriptomic response (OSD-574 spatial pooled) "
               "to the systemic R+1 inflammation composite (IL-6/TNF/CRP "
               "from OSD-575). Per astronaut, in tabs."),
        x_axis="Four columns left → right: ENVIRONMENT → HOST SITE → "
               "BARRIER → SYSTEMIC. Read each row as one biological step.",
        y_axis=("Each card shows its signed magnitude inline. For "
                "microbiome cards (host site) magnitude = normalized "
                "mean |log2FC|, 0 to 1, scale within layer. For barrier, "
                "magnitude = signed mean log2FC mapped into [-1, 1] "
                "(negative = suppressed). For systemic cytokines, "
                "magnitude = R+1 own-baseline z-score (SDs from "
                "preflight). Edge thickness scales with edge weight; "
                "the number labeled on each edge is the weight value."),
        why=("Custom SVG beats Plotly Sankey here because the graph is "
             "small (5 nodes, 5 edges per astronaut) and the labels are "
             "long. Sankey crammed magnitudes into hover tooltips and "
             "couldn't show layer headers cleanly. Inline cards with "
             "visible magnitudes and labeled edges make the chain "
             "readable at a glance."),
    )


# ---------------------------------------------------------------------------
# SVG construction
# ---------------------------------------------------------------------------

def _build_svg(graph: dict) -> str:
    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])
    if not nodes or not edges:
        return "<div>(no graph data)</div>"

    # group nodes by layer
    by_layer: dict[str, list[dict]] = {l: [] for l in LAYERS}
    for n in nodes:
        l = n.get("layer", "systemic")
        by_layer.setdefault(l, []).append(n)

    # vertical positions: spread within the column
    available_h = H - NODE_TOP - 50  # leave room at bottom
    positions: dict[str, tuple[int, int]] = {}
    for layer in LAYERS:
        ns = by_layer.get(layer, [])
        n_count = len(ns)
        if n_count == 0:
            continue
        cx = COL_X[layer]
        # distribute n_count cards centered vertically
        total_used = n_count * NODE_H + (n_count - 1) * 24
        start_y = NODE_TOP + (available_h - total_used) // 2
        for i, node in enumerate(ns):
            y = start_y + i * (NODE_H + 24)
            x = cx - NODE_W // 2
            positions[node["id"]] = (x, y)

    parts: list[str] = []
    parts.append(
        f'<svg viewBox="0 0 {W} {H}" width="100%" '
        f'preserveAspectRatio="xMidYMid meet" '
        f'style="font-family:\'Segoe UI\', system-ui, sans-serif;">'
    )

    # ---- defs + style
    parts.append(
        '<defs>'
        '<filter id="cardShadow" x="-10%" y="-10%" width="120%" height="120%">'
        '<feGaussianBlur in="SourceAlpha" stdDeviation="2"/>'
        '<feOffset dx="0" dy="2" result="off"/>'
        '<feComponentTransfer><feFuncA type="linear" slope="0.18"/>'
        '</feComponentTransfer><feMerge>'
        '<feMergeNode/><feMergeNode in="SourceGraphic"/></feMerge>'
        '</filter>'
        '<filter id="cardShadowHover" x="-15%" y="-15%" width="130%" height="130%">'
        '<feGaussianBlur in="SourceAlpha" stdDeviation="4"/>'
        '<feOffset dx="0" dy="4" result="off"/>'
        '<feComponentTransfer><feFuncA type="linear" slope="0.30"/>'
        '</feComponentTransfer><feMerge>'
        '<feMergeNode/><feMergeNode in="SourceGraphic"/></feMerge>'
        '</filter>'
        '</defs>'
        '<style>'
        '.flow-card { '
        ' transition: transform 200ms cubic-bezier(0.4,0,0.2,1), '
        '             filter 200ms ease; '
        ' transform-box: fill-box; transform-origin: center; '
        ' cursor: pointer; }'
        '.flow-card:hover { transform: translateY(-3px) scale(1.03); '
        '                   filter: url(#cardShadowHover); }'
        '.flow-edge { '
        ' transition: stroke 180ms ease, stroke-width 180ms ease, '
        '             opacity 180ms ease; }'
        '.flow-edge-group:hover .flow-edge { '
        ' opacity: 1 !important; stroke-width: 8; }'
        '.flow-edge-label { '
        ' transition: transform 180ms ease, filter 180ms ease; '
        ' transform-box: fill-box; transform-origin: center; '
        ' cursor: pointer; }'
        '.flow-edge-group:hover .flow-edge-label { '
        ' transform: scale(1.18); '
        ' filter: drop-shadow(0 2px 4px rgba(10,31,68,0.18)); }'
        '.col-divider { '
        ' transition: opacity 200ms ease; opacity: 0.65; }'
        '.col-divider:hover { opacity: 1; }'
        '</style>'
    )

    # ---- column headers
    for layer in LAYERS:
        cx = COL_X[layer]
        layer_color = config.SANKEY_LAYER_COLORS.get(layer, "#888")
        parts.append(
            f'<text x="{cx}" y="{HEADER_TOP + 8}" text-anchor="middle" '
            f'font-size="13" font-weight="700" letter-spacing="3" '
            f'fill="{layer_color}">{LAYER_LABEL[layer]}</text>'
        )
        parts.append(
            f'<text x="{cx}" y="{HEADER_TOP + 28}" text-anchor="middle" '
            f'font-size="11" fill="#5a6675" font-style="italic">'
            f'{LAYER_SUB[layer]}</text>'
        )
        # subtle column divider
        parts.append(
            f'<line class="col-divider" '
            f'x1="{cx + W // (2*len(LAYERS))}" y1="{HEADER_TOP + 40}" '
            f'x2="{cx + W // (2*len(LAYERS))}" y2="{H - 30}" '
            f'stroke="#e6ecf2" stroke-width="1" stroke-dasharray="3 4"/>'
        )

    # ---- edges (drawn behind nodes)
    for e in edges:
        s_pos = positions.get(e["source"])
        t_pos = positions.get(e["target"])
        if s_pos is None or t_pos is None:
            continue
        sx = s_pos[0] + NODE_W
        sy = s_pos[1] + NODE_H // 2
        tx = t_pos[0]
        ty = t_pos[1] + NODE_H // 2
        weight = float(e.get("weight", 0))
        evidence = e.get("evidence", "correlation_only")
        edge_color = config.SANKEY_EDGE_COLORS.get(
            evidence, "rgba(154,163,173,0.4)")
        stroke_w = max(2.0, min(weight * 14.0, 18.0))

        # cubic bezier with horizontal handles for smooth flow
        midx = (sx + tx) / 2
        path = (f"M {sx} {sy} "
                f"C {midx} {sy}, {midx} {ty}, {tx} {ty}")
        tooltip = (f"{e['source']} → {e['target']}\n"
                   f"weight: {weight:.2f}\n"
                   f"evidence: {evidence}")
        parts.append(
            f'<g class="flow-edge-group">'
            f'<title>{_html.escape(tooltip)}</title>'
            f'<path class="flow-edge" d="{path}" stroke="{edge_color}" '
            f'stroke-width="{stroke_w}" '
            f'fill="none" stroke-linecap="round"/>'
            # weight label at the path midpoint
            f'<g class="flow-edge-label">'
            f'<rect x="{midx - 18}" y="{(sy + ty) / 2 - 11}" '
            f'width="36" height="20" rx="4" fill="white" '
            f'stroke="{config.COLOR_ICE}" stroke-width="1"/>'
            f'<text x="{midx}" y="{(sy + ty) / 2 + 4}" '
            f'text-anchor="middle" font-size="11" font-weight="600" '
            f'fill="{config.COLOR_PRIMARY}">{weight:.2f}</text>'
            f'</g>'
            f'</g>'
        )

    # ---- nodes on top
    for node in nodes:
        pos = positions.get(node["id"])
        if pos is None:
            continue
        x, y = pos
        layer = node.get("layer", "systemic")
        layer_color = config.SANKEY_LAYER_COLORS.get(layer, "#888")
        label = node.get("label", node["id"])
        magnitude = float(node.get("magnitude", 0.0))
        mag_color = (config.COLOR_UP if magnitude > 0.05
                     else (config.COLOR_DOWN if magnitude < -0.05
                           else config.COLOR_NEUTRAL))
        mag_str = f"{magnitude:+.2f}"
        # readable label: split long text into two lines if needed
        label_lines = _wrap_label(label, max_chars=26)

        tooltip = f"{layer.upper()}\n{label}\nmagnitude: {mag_str}"
        parts.append(
            f'<g class="flow-card"><title>{_html.escape(tooltip)}</title>'
            # card body
            f'<rect x="{x}" y="{y}" width="{NODE_W}" height="{NODE_H}" '
            f'rx="10" fill="white" stroke="{layer_color}" stroke-width="2" '
            f'filter="url(#cardShadow)"/>'
            # top color stripe
            f'<rect x="{x}" y="{y}" width="{NODE_W}" height="6" '
            f'rx="3" fill="{layer_color}"/>'
        )
        # label lines
        for i, ln in enumerate(label_lines[:2]):
            parts.append(
                f'<text x="{x + NODE_W / 2}" y="{y + 28 + i * 16}" '
                f'text-anchor="middle" font-size="12" font-weight="600" '
                f'fill="{config.COLOR_PRIMARY}">{_html.escape(ln)}</text>'
            )
        # magnitude pill
        parts.append(
            f'<rect x="{x + NODE_W / 2 - 32}" y="{y + NODE_H - 26}" '
            f'width="64" height="20" rx="10" fill="{mag_color}"/>'
            f'<text x="{x + NODE_W / 2}" y="{y + NODE_H - 11}" '
            f'text-anchor="middle" font-size="12" font-weight="700" '
            f'fill="white">{mag_str}</text>'
            f'</g>'
        )

    parts.append("</svg>")
    return "".join(parts)


def _wrap_label(text: str, *, max_chars: int) -> list[str]:
    """Greedy two-line wrap on word boundaries. Truncates long lines with …."""
    if len(text) <= max_chars:
        return [text]
    words = text.split()
    lines: list[list[str]] = [[]]
    for w in words:
        if not lines[-1]:
            lines[-1].append(w)
            continue
        candidate = " ".join(lines[-1] + [w])
        if len(candidate) <= max_chars:
            lines[-1].append(w)
        else:
            if len(lines) == 2:
                lines[-1].append(w)
                break
            lines.append([w])
    out = [" ".join(ln) for ln in lines]
    if len(out) > 1 and len(out[1]) > max_chars:
        out[1] = out[1][: max_chars - 1].rstrip() + "…"
    return out


# ---------------------------------------------------------------------------
# legend
# ---------------------------------------------------------------------------

def _legend_html(evidence_legend: dict) -> str:
    swatch = lambda color, shape="circle": (
        f'<span style="display:inline-block;width:12px;height:12px;'
        f'border-radius:{"50%" if shape=="circle" else "0"};'
        f'background:{color};vertical-align:middle;margin-right:6px;'
        f'border:1px solid rgba(10,31,68,0.2);"></span>'
    )
    lines: list[str] = []
    lines.append('<div style="display:flex;flex-wrap:wrap;gap:18px;'
                 'padding:10px 0;font-size:0.9rem;color:#14233e;">')
    # layer colors
    for layer in LAYERS:
        color = config.SANKEY_LAYER_COLORS.get(layer, "#888")
        lines.append(
            f'<div>{swatch(color, "rect")}<strong>{LAYER_LABEL[layer]}</strong> '
            f'– {LAYER_SUB[layer]}</div>'
        )
    lines.append("</div>")

    # magnitude direction key
    lines.append(
        '<div style="font-size:0.85rem;color:#5a6675;'
        'padding:6px 0 0 0;">'
        f'{swatch(config.COLOR_UP)}<strong style="color:#14233e;">positive</strong> '
        '= elevated relative to baseline · '
        f'{swatch(config.COLOR_DOWN)}<strong style="color:#14233e;">negative</strong> '
        '= suppressed relative to baseline · '
        '<strong>edge thickness</strong> scales with edge weight (number '
        'on each edge is the weight value, unitless)'
        '</div>'
    )

    if evidence_legend:
        lines.append('<div style="font-size:0.83rem;color:#5a6675;'
                     'padding:8px 0 0 0;">')
        for k, v in evidence_legend.items():
            lines.append(f'<div style="margin-top:3px;">'
                         f'<code style="background:#f3f7fa;padding:1px 5px;'
                         f'border-radius:3px;">{k}</code> — {v}</div>')
        lines.append("</div>")
    return "".join(lines)
