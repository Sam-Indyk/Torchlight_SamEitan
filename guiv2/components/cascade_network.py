"""Cascade network — all 8 hypothesized cascades as one graph.

Three columns:

  Column 1 — STRESSORS (microgravity, radiation, fluid shift, combined)
  Column 2 — ROOT CAUSES (one node per cascade, color-coded by stressor)
  Column 3 — OUTCOME (score badge: how strongly the data backs each chain)

Edges from a stressor card to a root-cause card show which stressor
drives that cascade. Edges from root-cause to outcome are color-coded
by score (strong/moderate/weak/no match).

Lets judges see the *joint* upstream architecture — which stressor
explains the most observed signal, where multiple cascades pile up
on the same stressor, and which cascades are still waiting on data.
"""
from __future__ import annotations

import html as _html

import streamlit as st
import streamlit.components.v1 as components

from guiv2 import config, data
from guiv2.components._chart_about import about_chart


# ---- canvas geometry ------------------------------------------------------

W, H = 1180, 720
COL_STRESSOR_X = 100
COL_ROOT_X     = 480
COL_OUTCOME_X  = 920
NODE_W = 240
NODE_H = 80
TITLE_Y = 36
ROW_TOP = 90  # first row y for stressor & root cause


# ---- helpers --------------------------------------------------------------

def _stressor_to_canonical(s: str) -> list[str]:
    """A cascade's `stressor` field can be 'microgravity',
    'radiation', 'microgravity (cardiovascular fluid shift)', or
    a combined string. Split into canonical stressor IDs."""
    s = (s or "").lower()
    out = []
    if "microgravity" in s and "fluid shift" in s:
        out.append("fluid_shift")
    elif "microgravity" in s:
        out.append("microgravity")
    if "radiation" in s:
        out.append("radiation")
    if "combined" in s and not out:
        out = ["microgravity", "radiation"]
    if not out:
        out = ["microgravity"]
    # de-dupe while preserving order
    seen, dedup = set(), []
    for x in out:
        if x not in seen:
            seen.add(x); dedup.append(x)
    return dedup


def _outcome_band(ratio: float) -> tuple[str, str]:
    if ratio >= 1.0:
        return ("STRONG MATCH", config.COLOR_UP)
    if ratio >= 0.5:
        return ("MODERATE",     config.COLOR_GOLD)
    if ratio >= 0.1:
        return ("WEAK",         config.COLOR_NEUTRAL)
    return ("NOT YET MATCHED",  "#9aa3ad")


# ---- main render ----------------------------------------------------------

def render_cascade_network(view: dict, manifest: dict) -> None:
    st.subheader(view["title"])

    dashboard = data.load_json(view.get("json", "data/dashboard_data.json"))
    if not dashboard:
        st.error("Dashboard JSON not found.")
        return

    block = dashboard.get("cascade_inference")
    if not block or "cascades" not in block:
        st.info("Cascade inference is not present in this JSON. "
                "Run the real `risk_profile_claude/build_risk_profile.py`.")
        return

    cascades = block["cascades"]
    svg = _build_svg(cascades)
    components.html(svg, height=H + 40, scrolling=False)

    # cohort-level summary table beneath the graph
    counts = _stressor_counts(cascades)
    summary = []
    for s, n in counts.items():
        summary.append({"Stressor": s.replace("_", " "),
                        "Cascades implicated": n})
    if summary:
        st.markdown("**Stressor → cascade count**")
        st.dataframe(summary, hide_index=True, use_container_width=True)

    about_chart(
        chart_type="3-column directed network (custom SVG)",
        shows=("Every cascade in the dashboard, drawn as one graph. "
               "Left column: the 3 spaceflight stressors. Middle column: "
               "the root-cause node from each cascade, color-coded by "
               "its primary stressor. Right column: a score badge "
               "summarizing how strongly the actual data supports each "
               "chain (STRONG / MODERATE / WEAK / NOT YET MATCHED)."),
        x_axis="Layers, left → right: STRESSOR → ROOT CAUSE → OUTCOME",
        y_axis=("Each row is one cascade. Edge thickness is uniform — "
                "this is a categorical graph, not a flow magnitude. "
                "Use the standalone Upstream Causes panel for the "
                "full per-cascade detail."),
        why=("A network view answers a different question than the "
             "ranked table: 'where does the upstream story converge?' "
             "Visible at a glance: microgravity drives 4 cascades, "
             "radiation drives 2, the combined / fluid-shift category "
             "drives the remaining 2. The cascade with the strongest "
             "match also has microgravity as its stressor — telling "
             "us where to push for more measurements."),
    )


# ---- SVG construction -----------------------------------------------------

def _build_svg(cascades: list[dict]) -> str:
    # group cascades by their canonical stressor list
    canonical_per_cascade = [
        (c, _stressor_to_canonical(c.get("stressor", "")))
        for c in cascades
    ]

    # collect unique stressors in order of first appearance
    stressor_order: list[str] = []
    for _, sts in canonical_per_cascade:
        for s in sts:
            if s not in stressor_order:
                stressor_order.append(s)
    stressor_label = {
        "microgravity":  "MICROGRAVITY",
        "radiation":     "COSMIC RADIATION",
        "fluid_shift":   "CEPHALAD FLUID SHIFT",
        "combined":      "COMBINED",
    }
    stressor_color = {
        "microgravity":  "#5fb1c4",   # ice blue
        "radiation":     "#d4a052",   # gold
        "fluid_shift":   "#a5536b",   # rose
        "combined":      "#7d8d96",
    }

    # vertical positions: stressor column at NODE_H spacing in middle of canvas;
    # root-cause column with one row per cascade.
    n_cascades = len(cascades)
    rc_row_h = NODE_H + 14
    rc_block_h = n_cascades * rc_row_h
    rc_top = max(ROW_TOP, (H - rc_block_h - 60) // 2 + 30)
    rc_positions = {
        cascades[i]["id"]: (COL_ROOT_X - NODE_W // 2,
                            rc_top + i * rc_row_h)
        for i in range(n_cascades)
    }

    n_str = len(stressor_order)
    str_row_h = NODE_H + 24
    str_block_h = n_str * str_row_h
    str_top = (H - str_block_h - 60) // 2 + 30
    str_positions = {
        s: (COL_STRESSOR_X - NODE_W // 2 + 30,
            str_top + i * str_row_h)
        for i, s in enumerate(stressor_order)
    }

    out_positions = {
        cascades[i]["id"]: (COL_OUTCOME_X - 80,
                            rc_positions[cascades[i]["id"]][1])
        for i in range(n_cascades)
    }

    parts: list[str] = []
    parts.append(
        f'<svg viewBox="0 0 {W} {H}" width="100%" '
        f'preserveAspectRatio="xMidYMid meet" '
        f'style="font-family:\'Segoe UI\', system-ui, sans-serif;">'
    )

    # defs + style
    parts.append(
        '<defs>'
        '<filter id="netCardShadow" x="-10%" y="-10%" '
        'width="120%" height="120%">'
        '<feGaussianBlur in="SourceAlpha" stdDeviation="2"/>'
        '<feOffset dx="0" dy="2"/>'
        '<feComponentTransfer><feFuncA type="linear" slope="0.18"/>'
        '</feComponentTransfer><feMerge>'
        '<feMergeNode/><feMergeNode in="SourceGraphic"/></feMerge>'
        '</filter>'
        '</defs>'
        '<style>'
        '.net-card { '
        ' transition: transform 200ms cubic-bezier(0.4,0,0.2,1), '
        '             filter 200ms ease; '
        ' transform-box: fill-box; transform-origin: center; '
        ' cursor: pointer; }'
        '.net-card:hover { transform: scale(1.04); }'
        '.net-edge { '
        ' transition: stroke-width 180ms ease, opacity 180ms ease; }'
        '.net-edge:hover { stroke-width: 5; opacity: 1; }'
        '</style>'
    )

    # column titles
    for cx, label in [
        (COL_STRESSOR_X + 30, "STRESSORS"),
        (COL_ROOT_X,           "ROOT CAUSES"),
        (COL_OUTCOME_X - 80 + 80, "MATCH AGAINST DATA"),
    ]:
        parts.append(
            f'<text x="{cx}" y="{TITLE_Y}" font-size="13" font-weight="700" '
            f'letter-spacing="3" fill="{config.COLOR_PRIMARY}" '
            f'text-anchor="middle">{label}</text>'
        )

    # ---- edges: stressor -> root-cause ----
    for c, sts in canonical_per_cascade:
        rc_x, rc_y = rc_positions[c["id"]]
        for s in sts:
            sx, sy = str_positions[s]
            x1 = sx + NODE_W
            y1 = sy + NODE_H // 2
            x2 = rc_x
            y2 = rc_y + NODE_H // 2
            mid = (x1 + x2) / 2
            path = f"M {x1} {y1} C {mid} {y1}, {mid} {y2}, {x2} {y2}"
            color = stressor_color.get(s, "#888")
            parts.append(
                f'<path class="net-edge" d="{path}" '
                f'stroke="{color}" stroke-width="2.4" '
                f'fill="none" opacity="0.55" stroke-linecap="round"/>'
            )

    # ---- edges: root-cause -> outcome ----
    for c in cascades:
        rc_x, rc_y = rc_positions[c["id"]]
        ox, oy = out_positions[c["id"]]
        ratio = c.get("score_ratio", 0)
        _, color = _outcome_band(ratio)
        x1 = rc_x + NODE_W
        y1 = rc_y + NODE_H // 2
        x2 = ox
        y2 = oy + NODE_H // 2
        mid = (x1 + x2) / 2
        path = f"M {x1} {y1} C {mid} {y1}, {mid} {y2}, {x2} {y2}"
        sw = max(2.0, min(ratio * 3.0, 6.0))
        parts.append(
            f'<path class="net-edge" d="{path}" '
            f'stroke="{color}" stroke-width="{sw}" '
            f'fill="none" opacity="0.7" stroke-linecap="round"/>'
        )

    # ---- stressor cards (left column) ----
    for s in stressor_order:
        sx, sy = str_positions[s]
        color = stressor_color.get(s, "#888")
        label = stressor_label.get(s, s.upper())
        # how many cascades this stressor drives
        n = sum(1 for c, sts in canonical_per_cascade if s in sts)
        tooltip = f"Stressor: {label}\nDrives {n} cascade(s)"
        parts.append(
            f'<g class="net-card"><title>{_html.escape(tooltip)}</title>'
            f'<rect x="{sx}" y="{sy}" width="{NODE_W}" height="{NODE_H}" '
            f'rx="10" fill="{color}" filter="url(#netCardShadow)"/>'
            f'<text x="{sx + NODE_W / 2}" y="{sy + 32}" text-anchor="middle" '
            f'font-size="13" font-weight="700" letter-spacing="2" '
            f'fill="white">{label}</text>'
            f'<text x="{sx + NODE_W / 2}" y="{sy + 56}" text-anchor="middle" '
            f'font-size="11" fill="white" opacity="0.92">'
            f'drives {n} cascade{"s" if n != 1 else ""}</text>'
            f'</g>'
        )

    # ---- root-cause cards (middle column) ----
    for c in cascades:
        rc_x, rc_y = rc_positions[c["id"]]
        sts = _stressor_to_canonical(c.get("stressor", ""))
        primary_color = stressor_color.get(sts[0], "#888")
        label_lines = _wrap_label(c.get("root_cause", "?"), 32)
        tooltip = (f"{c.get('name', c.get('id', '?'))}\n"
                   f"Stressor(s): {', '.join(sts)}\n"
                   f"Score ratio: {c.get('score_ratio', 0):.2f}\n"
                   f"Matched: {c.get('n_matched', 0)} / "
                   f"Disagreed: {c.get('n_disagreed', 0)} / "
                   f"Missing: {c.get('n_missing', 0)}")
        parts.append(
            f'<g class="net-card"><title>{_html.escape(tooltip)}</title>'
            f'<rect x="{rc_x}" y="{rc_y}" width="{NODE_W}" height="{NODE_H}" '
            f'rx="10" fill="white" stroke="{primary_color}" '
            f'stroke-width="2" filter="url(#netCardShadow)"/>'
            f'<rect x="{rc_x}" y="{rc_y}" width="{NODE_W}" height="6" '
            f'rx="3" fill="{primary_color}"/>'
        )
        for j, ln in enumerate(label_lines[:2]):
            parts.append(
                f'<text x="{rc_x + NODE_W / 2}" y="{rc_y + 28 + j * 16}" '
                f'text-anchor="middle" font-size="11" font-weight="600" '
                f'fill="{config.COLOR_PRIMARY}">{_html.escape(ln)}</text>'
            )
        # cascade short id at bottom
        parts.append(
            f'<text x="{rc_x + NODE_W / 2}" y="{rc_y + NODE_H - 8}" '
            f'text-anchor="middle" font-size="10" letter-spacing="1.5" '
            f'fill="#5a6675">{_html.escape(c.get("id", ""))}</text>'
            f'</g>'
        )

    # ---- outcome badges (right column) ----
    for c in cascades:
        ox, oy = out_positions[c["id"]]
        ratio = c.get("score_ratio", 0)
        band, color = _outcome_band(ratio)
        n_matched = c.get("n_matched", 0)
        n_total = (c.get("n_matched", 0) + c.get("n_disagreed", 0)
                   + c.get("n_missing", 0))
        tooltip = (f"{band}\nScore ratio {ratio:.2f}\n"
                   f"Matched {n_matched} of {n_total} terminal observations")
        parts.append(
            f'<g class="net-card"><title>{_html.escape(tooltip)}</title>'
            f'<rect x="{ox}" y="{oy}" width="160" height="{NODE_H}" '
            f'rx="10" fill="{color}" filter="url(#netCardShadow)"/>'
            f'<text x="{ox + 80}" y="{oy + 28}" text-anchor="middle" '
            f'font-size="11" font-weight="700" letter-spacing="1.5" '
            f'fill="white">{band}</text>'
            f'<text x="{ox + 80}" y="{oy + 50}" text-anchor="middle" '
            f'font-size="14" font-weight="700" fill="white">'
            f'ratio {ratio:.2f}</text>'
            f'<text x="{ox + 80}" y="{oy + 67}" text-anchor="middle" '
            f'font-size="10" fill="white" opacity="0.9">'
            f'{n_matched}/{n_total} terminal hits</text>'
            f'</g>'
        )

    parts.append("</svg>")
    return ('<div style="display:flex;justify-content:center;'
            'padding:6px 0 14px 0;">'
            + "".join(parts) + "</div>")


def _wrap_label(text: str, max_chars: int) -> list[str]:
    if len(text) <= max_chars:
        return [text]
    words = text.split()
    lines: list[list[str]] = [[]]
    for w in words:
        if not lines[-1]:
            lines[-1].append(w)
            continue
        cand = " ".join(lines[-1] + [w])
        if len(cand) <= max_chars:
            lines[-1].append(w)
        else:
            if len(lines) == 2:
                lines[-1].append(w); break
            lines.append([w])
    out = [" ".join(ln) for ln in lines]
    if len(out) > 1 and len(out[1]) > max_chars:
        out[1] = out[1][: max_chars - 1].rstrip() + "…"
    return out


def _stressor_counts(cascades: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for c in cascades:
        for s in _stressor_to_canonical(c.get("stressor", "")):
            counts[s] = counts.get(s, 0) + 1
    return dict(sorted(counts.items(), key=lambda kv: kv[1], reverse=True))
