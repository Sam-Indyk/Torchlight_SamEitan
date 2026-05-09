"""Anatomical body-site sample-collection map.

Shows where each OSD-572 microbiome swab was taken, plus the systemic-fluid
collection sites (blood, urine, stool, plasma). Marker color encodes effect
magnitude (mean per-astronaut log2FC at during-vs-pre, where available);
hover shows the body site code, full name, dataset, and effect size.

Layout: a stylized human silhouette drawn with Plotly shapes plus
annotated markers at approximately-correct anatomical positions. Not
medically precise — communicative.
"""

from __future__ import annotations
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from guiv2 import config, data


# OSD-572 body-site codes -> (display name, x, y on a stylized 100x100 canvas
# where 50,90 is head and 50,5 is feet).
SITE_LAYOUT: dict[str, dict] = {
    "NAC": {"name": "Nasal cavity",     "x": 50, "y": 92, "side": "L",
            "modality": "OSD-572 swab"},
    "NAP": {"name": "Nasopharynx",      "x": 50, "y": 88, "side": "L",
            "modality": "OSD-572 swab"},
    "ORC": {"name": "Oral cavity",      "x": 50, "y": 84, "side": "L",
            "modality": "OSD-572 swab"},
    "EAR": {"name": "Outer ear",        "x": 64, "y": 90, "side": "L",
            "modality": "OSD-572 swab"},
    "PIT": {"name": "Axilla (armpit)",  "x": 28, "y": 70, "side": "L",
            "modality": "OSD-572 swab"},
    "ARM": {"name": "Volar forearm",    "x": 19, "y": 55, "side": "L",
            "modality": "OSD-572 swab"},
    "UMB": {"name": "Umbilicus (belly)","x": 50, "y": 60, "side": "L",
            "modality": "OSD-572 swab"},
    "GLU": {"name": "Gluteal",          "x": 56, "y": 50, "side": "L",
            "modality": "OSD-572 swab"},
    "WEB": {"name": "Toe web (lateral)","x": 38, "y": 8,  "side": "L",
            "modality": "OSD-572 swab"},
    "TZO": {"name": "Toe-web zone",     "x": 62, "y": 8,  "side": "L",
            "modality": "OSD-572 swab"},
}

# Systemic / non-skin collections
SYSTEMIC_SITES = [
    {"name": "Antecubital vein (blood draw)", "x": 78, "y": 60,
     "datasets": ["OSD-569 RNA-seq + CBC", "OSD-571 plasma proteome / metabolome",
                  "OSD-575 serum panels"], "color": config.COLOR_UP},
    {"name": "Stool sample",                  "x": 62, "y": 35,
     "datasets": ["OSD-630 stool metagenomics"], "color": "#7d8d96"},
    {"name": "Urine sample",                  "x": 50, "y": 38,
     "datasets": ["OSD-656 urine inflammation"], "color": "#d4a052"},
    {"name": "Deltoid skin biopsy",           "x": 78, "y": 73,
     "datasets": ["OSD-574 spatial transcriptomics"], "color": "#a5536b"},
    {"name": "Capsule surfaces",              "x": 95, "y": 55,
     "datasets": ["OSD-573 cabin metagenomics (3,585 taxa)"],
     "color": config.COLOR_NEUTRAL},
]


def render_body_sample_map(view: dict, manifest: dict) -> None:
    st.subheader(view["title"])
    st.markdown(view.get("intro_md") or
        "Where each sample was collected, layered with the magnitude of the "
        "during-vs-pre microbiome shift in all four crew. Marker size scales "
        "with the number of features that shifted concordantly at that body "
        "site; color encodes whether shifts trend up (red) or are mixed.")

    # ---- pull effect-size per body site from analysis/results/ -----------
    repo_root = Path(__file__).resolve().parent.parent.parent
    results = repo_root / "analysis" / "results"
    site_effects: dict[str, dict] = {}
    for code in SITE_LAYOUT:
        path = results / f"OSD-572_taxonomy_{code}_during_vs_pre.csv"
        if not path.exists():
            continue
        try:
            df = pd.read_csv(path)
        except Exception:
            continue
        if df.empty:
            site_effects[code] = {"n": 0, "mean_abs": 0.0, "frac_up": 0.0}
            continue
        crew_cols = [c for c in ("C001", "C002", "C003", "C004") if c in df.columns]
        if not crew_cols:
            continue
        mean_abs = float(df[crew_cols].abs().mean().mean())
        if "direction" in df.columns:
            frac_up = float((df["direction"] == "up").mean())
        else:
            frac_up = 0.5
        site_effects[code] = {
            "n":        int(len(df)),
            "mean_abs": mean_abs,
            "frac_up":  frac_up,
        }

    fig = _make_body_figure(site_effects)
    st.plotly_chart(fig, use_container_width=True)

    # ---- companion table -------------------------------------------------
    table = []
    for code, layout in SITE_LAYOUT.items():
        eff = site_effects.get(code, {})
        n = eff.get("n", 0)
        mean_abs = eff.get("mean_abs", 0.0)
        frac_up = eff.get("frac_up", 0.0)
        table.append({
            "Site code": code,
            "Anatomical site": layout["name"],
            "Concordant features (n)": n,
            "Mean |log2FC|":           f"{mean_abs:.2f}" if n else "—",
            "% trending UP":           f"{100*frac_up:.0f}%" if n else "—",
        })
    st.markdown("**OSD-572 microbiome swab body sites** (sorted by features per site)")
    table.sort(key=lambda r: r["Concordant features (n)"], reverse=True)
    st.dataframe(table, hide_index=True, use_container_width=True)

    st.caption(
        "Numbers above are *during-vs-pre* concordant shifts: features where "
        "all four crew moved in the same direction with |log2FC| ≥ 1. The "
        "axillary (PIT), forearm (ARM), and nasopharynx (NAP) sites carry "
        "the strongest signal; the nasal cavity (NAC) is unusually conserved."
    )


def _make_body_figure(site_effects: dict[str, dict]) -> go.Figure:
    fig = go.Figure()

    # Stylized human silhouette: a few rounded rectangles + a head
    body_color = "rgba(95,177,196,0.18)"
    body_outline = "rgba(10,31,68,0.55)"
    # head
    fig.add_shape(type="circle", x0=44, y0=82, x1=56, y1=96,
                  line=dict(color=body_outline, width=1.4),
                  fillcolor=body_color)
    # neck
    fig.add_shape(type="rect", x0=47.5, y0=80, x1=52.5, y1=84,
                  line=dict(color=body_outline, width=0),
                  fillcolor=body_color)
    # torso
    fig.add_shape(type="path",
                  path=("M 38 80 Q 50 78 62 80 L 64 50 Q 60 42 50 42 "
                        "Q 40 42 36 50 Z"),
                  line=dict(color=body_outline, width=1.4),
                  fillcolor=body_color)
    # left arm
    fig.add_shape(type="path",
                  path="M 38 78 Q 27 70 22 55 Q 19 50 17 45 Q 18 44 21 46 Q 26 60 32 70 L 36 78 Z",
                  line=dict(color=body_outline, width=1.2),
                  fillcolor=body_color)
    # right arm
    fig.add_shape(type="path",
                  path="M 62 78 Q 73 70 78 55 Q 81 50 83 45 Q 82 44 79 46 Q 74 60 68 70 L 64 78 Z",
                  line=dict(color=body_outline, width=1.2),
                  fillcolor=body_color)
    # legs (left)
    fig.add_shape(type="path",
                  path="M 40 42 L 38 12 L 36 8 L 42 8 L 44 12 L 46 42 Z",
                  line=dict(color=body_outline, width=1.2),
                  fillcolor=body_color)
    # legs (right)
    fig.add_shape(type="path",
                  path="M 54 42 L 56 12 L 58 8 L 64 8 L 62 12 L 60 42 Z",
                  line=dict(color=body_outline, width=1.2),
                  fillcolor=body_color)

    # OSD-572 swab markers
    xs, ys, texts, hover, sizes, colors = [], [], [], [], [], []
    for code, layout in SITE_LAYOUT.items():
        eff = site_effects.get(code, {})
        n = eff.get("n", 0)
        mean_abs = eff.get("mean_abs", 0.0)
        frac_up = eff.get("frac_up", 0.5)
        # marker size scales with n_features; min 10, cap 40
        size = 10 + min(30, n / 12)
        # color: warm if mostly up, cool if mostly down, gold if mixed
        if n == 0:
            c = config.COLOR_NEUTRAL
        elif frac_up >= 0.65:
            c = config.COLOR_UP
        elif frac_up <= 0.35:
            c = config.COLOR_DOWN
        else:
            c = config.COLOR_GOLD
        xs.append(layout["x"]); ys.append(layout["y"])
        texts.append(code)
        hover.append(
            f"<b>{code} — {layout['name']}</b><br>"
            f"{layout['modality']}<br>"
            f"Concordant features (during vs pre): {n}<br>"
            f"Mean |log2FC|: {mean_abs:.2f}<br>"
            f"% trending up: {100*frac_up:.0f}%"
        )
        sizes.append(size); colors.append(c)
    fig.add_trace(go.Scatter(
        x=xs, y=ys, mode="markers+text",
        text=texts, textposition="middle center",
        textfont=dict(size=9, color="white", family="Arial Black"),
        marker=dict(size=sizes, color=colors,
                    line=dict(color=config.COLOR_PRIMARY, width=1.5),
                    opacity=0.92),
        hovertext=hover, hoverinfo="text",
        name="OSD-572 swabs", showlegend=True,
    ))

    # Systemic markers (non-skin)
    sxs, sys, stexts, shover = [], [], [], []
    for s in SYSTEMIC_SITES:
        sxs.append(s["x"]); sys.append(s["y"])
        stexts.append(s["name"].split()[0])
        ds = "<br>".join(f"• {d}" for d in s["datasets"])
        shover.append(f"<b>{s['name']}</b><br>{ds}")
    fig.add_trace(go.Scatter(
        x=sxs, y=sys, mode="markers",
        marker=dict(size=15, color=config.COLOR_PRIMARY,
                    symbol="diamond",
                    line=dict(color="white", width=1.5)),
        hovertext=shover, hoverinfo="text",
        name="Systemic / environmental",
    ))

    fig.update_layout(
        height=620,
        margin=dict(l=10, r=10, t=10, b=10),
        xaxis=dict(range=[5, 100], visible=False, scaleanchor="y",
                   scaleratio=1),
        yaxis=dict(range=[0, 100], visible=False),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        legend=dict(orientation="h", yanchor="bottom", y=-0.04,
                    xanchor="center", x=0.5,
                    bgcolor="rgba(255,255,255,0.85)"),
    )
    return fig
