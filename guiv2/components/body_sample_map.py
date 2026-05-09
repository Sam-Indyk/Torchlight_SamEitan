"""Anatomical body-site sample-collection map (inline SVG).

Replaces the earlier Plotly version. Renders a clean human silhouette
in SVG with markers placed at approximately-correct anatomical
positions and labels arranged in two columns flanking the body, joined
to their dots by thin leader lines. Hover (native browser tooltip via
<title>) shows the site code, anatomical name, dataset, and effect
size pulled from the OSD-572 per-site CSVs.

Numbers shown are during-vs-pre concordant shifts: features where all
four crew moved in the same direction with |log2FC| >= 1.
"""

from __future__ import annotations
from pathlib import Path

import html as _html
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from guiv2 import config
from guiv2.components._chart_about import about_chart


# ---------------------------------------------------------------------------
# layout: site -> (body x, body y, label side, label y)
#   body coords on a 0..600 x 0..1000 SVG canvas.
#   label_side ∈ {"L","R"} picks left or right column.
#   label_y is the y-coord of the label box (lets us hand-tune to avoid
#   collisions).
# ---------------------------------------------------------------------------

SITE_LAYOUT: dict[str, dict] = {
    # Head / face -------------------------------------------------------
    "NAC": {"name": "Nasal cavity",       "modality": "OSD-572 swab",
            "x":  295, "y":  108, "side": "R", "label_y":  60},
    "NAP": {"name": "Nasopharynx",        "modality": "OSD-572 swab",
            "x":  300, "y":  130, "side": "R", "label_y": 110},
    "ORC": {"name": "Oral cavity",        "modality": "OSD-572 swab",
            "x":  300, "y":  150, "side": "R", "label_y": 165},
    "EAR": {"name": "Outer ear",          "modality": "OSD-572 swab",
            "x":  350, "y":  105, "side": "R", "label_y":  20},
    # Trunk -------------------------------------------------------------
    "PIT": {"name": "Axilla (armpit)",    "modality": "OSD-572 swab",
            "x":  215, "y":  240, "side": "L", "label_y": 215},
    "UMB": {"name": "Umbilicus",          "modality": "OSD-572 swab",
            "x":  300, "y":  385, "side": "R", "label_y": 360},
    "GLU": {"name": "Gluteal",            "modality": "OSD-572 swab",
            "x":  330, "y":  470, "side": "R", "label_y": 455},
    # Limbs -------------------------------------------------------------
    "ARM": {"name": "Volar forearm",      "modality": "OSD-572 swab",
            "x":  160, "y":  395, "side": "L", "label_y": 380},
    "WEB": {"name": "Toe web (lateral)",  "modality": "OSD-572 swab",
            "x":  265, "y":  945, "side": "L", "label_y": 855},
    "TZO": {"name": "Toe-web zone",       "modality": "OSD-572 swab",
            "x":  335, "y":  945, "side": "R", "label_y": 855},
}

# Systemic / non-skin collections — drawn as small diamonds outside the body
SYSTEMIC_SITES = [
    {"id": "BLOOD", "name": "Antecubital vein (blood)",
     "datasets": ["OSD-569 RNA + CBC", "OSD-571 plasma", "OSD-575 serum"],
     "x": 460, "y": 245, "side": "R", "label_y": 270},
    {"id": "URINE", "name": "Urine sample",
     "datasets": ["OSD-656 urine inflammation"],
     "x": 460, "y": 350, "side": "R", "label_y": 510},
    {"id": "STOOL", "name": "Stool sample",
     "datasets": ["OSD-630 stool metagenomics"],
     "x": 460, "y": 410, "side": "R", "label_y": 575},
    {"id": "DEL",  "name": "Deltoid skin biopsy",
     "datasets": ["OSD-574 spatial transcriptomics"],
     "x": 145,  "y": 235, "side": "L", "label_y": 145},
    {"id": "CAB",  "name": "Capsule surfaces",
     "datasets": ["OSD-573 cabin metagenomics"],
     "x": 540, "y": 600, "side": "R", "label_y": 645},
]


# ---------------------------------------------------------------------------
# rendering
# ---------------------------------------------------------------------------

def render_body_sample_map(view: dict, manifest: dict) -> None:
    st.subheader(view["title"])
    st.markdown(view.get("intro_md") or
        "Where each sample was collected. Marker color encodes the direction "
        "of the during-vs-pre microbiome shift; size scales with the number "
        "of features that all four crew moved together at that body site. "
        "Hover any dot for the per-site numbers."
    )

    site_effects = _load_site_effects()
    svg = _build_svg(site_effects)
    # Streamlit's markdown sanitizer strips <svg> while keeping the inner
    # <text> nodes, which would render as a wall of mashed-together labels.
    # Use components.html so the SVG is iframed and rendered intact.
    components.html(svg, height=1340, scrolling=False)

    # ---- companion table -------------------------------------------------
    rows = []
    for code, layout in SITE_LAYOUT.items():
        eff = site_effects.get(code, {})
        n = eff.get("n", 0)
        rows.append({
            "Site code": code,
            "Anatomical site": layout["name"],
            "Concordant features (n)": n,
            "Mean |log2FC|":           f"{eff.get('mean_abs', 0):.2f}" if n else "—",
            "% trending UP":           f"{100*eff.get('frac_up', 0):.0f}%" if n else "—",
        })
    rows.sort(key=lambda r: r["Concordant features (n)"], reverse=True)
    st.markdown("**OSD-572 microbiome swab body sites** (sorted by signal "
                "strength)")
    st.dataframe(rows, hide_index=True, use_container_width=True)

    st.caption(
        "Axillary (PIT), forearm (ARM), and nasopharynx (NAP) carry the "
        "strongest concordant signal during flight. The nasal cavity (NAC) "
        "is unusually conserved — Tierney et al. note the same."
    )

    about_chart(
        chart_type="Annotated anatomical illustration (inline SVG)",
        shows=("Where each Inspiration-4 sample was collected, layered "
               "with the magnitude of the during-vs-pre microbiome shift "
               "across all four crew. Hover any dot for the per-site "
               "numbers. Diamonds outside the body silhouette mark "
               "systemic / environmental collections (blood, urine, "
               "stool, deltoid biopsy, capsule surfaces)."),
        x_axis="Anatomical position (illustrative, not to scale)",
        y_axis=("Marker size scales with the number of features that "
                "shifted concordantly in all 4 crew at |log2FC| ≥ 1; "
                "marker color encodes direction (red = trending UP, "
                "blue = DOWN, gold = mixed, gray = no signal at the "
                "4-of-4 bar). Companion table below has exact n, "
                "mean |log2FC|, and % trending up per site."),
        why=("A literal body diagram is the most compact way to "
             "communicate which body sites carry signal — judges can "
             "pattern-match against anatomy at a glance instead of "
             "decoding site codes (NAP vs ARM vs PIT) from a table. "
             "The companion table preserves the precise numbers."),
    )


# ---------------------------------------------------------------------------
# data
# ---------------------------------------------------------------------------

def _load_site_effects() -> dict[str, dict]:
    repo_root = Path(__file__).resolve().parent.parent.parent
    results = repo_root / "analysis" / "results"
    out: dict[str, dict] = {}
    for code in SITE_LAYOUT:
        path = results / f"OSD-572_taxonomy_{code}_during_vs_pre.csv"
        if not path.exists():
            continue
        try:
            df = pd.read_csv(path)
        except Exception:
            continue
        if df.empty:
            out[code] = {"n": 0, "mean_abs": 0.0, "frac_up": 0.0}
            continue
        crew_cols = [c for c in ("C001", "C002", "C003", "C004")
                     if c in df.columns]
        if not crew_cols:
            continue
        mean_abs = float(df[crew_cols].abs().mean().mean())
        frac_up = (float((df["direction"] == "up").mean())
                   if "direction" in df.columns else 0.5)
        out[code] = {"n": int(len(df)), "mean_abs": mean_abs,
                     "frac_up": frac_up}
    return out


# ---------------------------------------------------------------------------
# SVG builder
# ---------------------------------------------------------------------------

def _site_color(eff: dict) -> str:
    n = eff.get("n", 0)
    if n == 0:
        return "#cbd5dd"
    f = eff.get("frac_up", 0.5)
    if f >= 0.6:
        return config.COLOR_UP
    if f <= 0.4:
        return config.COLOR_DOWN
    return config.COLOR_GOLD


def _site_radius(eff: dict) -> float:
    n = eff.get("n", 0)
    return 6 + min(11, n / 32)   # cap at 17px


def _build_svg(site_effects: dict[str, dict]) -> str:
    """Return a complete <div><svg>...</svg></div> markdown-safe string."""
    body_paths = _body_silhouette_paths()
    site_markers, site_labels = [], []
    for code, layout in SITE_LAYOUT.items():
        eff = site_effects.get(code, {})
        marker, label = _marker_and_label(code, layout, eff)
        site_markers.append(marker)
        site_labels.append(label)

    sys_markers, sys_labels = [], []
    for s in SYSTEMIC_SITES:
        marker, label = _systemic_marker_and_label(s)
        sys_markers.append(marker)
        sys_labels.append(label)

    # legend — placed at bottom of SVG
    legend = _build_legend()

    return f"""
<div style="display:flex; justify-content:center; padding:6px 0 14px 0;">
<svg viewBox="0 0 760 1010" width="100%" preserveAspectRatio="xMidYMid meet"
     style="max-width:1000px; font-family: 'Segoe UI', system-ui, sans-serif;">
  <defs>
    <linearGradient id="bodyGrad" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%"  stop-color="#eef5f8"/>
      <stop offset="100%" stop-color="#bdd9e0"/>
    </linearGradient>
    <filter id="softShadow" x="-30%" y="-30%" width="160%" height="160%">
      <feGaussianBlur in="SourceGraphic" stdDeviation="2"/>
    </filter>
    <filter id="markerGlow" x="-60%" y="-60%" width="220%" height="220%">
      <feGaussianBlur in="SourceGraphic" stdDeviation="3.2"/>
      <feMerge><feMergeNode/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>
  </defs>
  <style>
    .site-group {{ cursor: pointer; }}
    .site-circle {{
      transition: transform 180ms cubic-bezier(0.4,0,0.2,1),
                  filter 180ms cubic-bezier(0.4,0,0.2,1);
      transform-box: fill-box;
      transform-origin: center;
    }}
    .site-group:hover .site-circle {{
      transform: scale(1.35);
      filter: url(#markerGlow);
    }}
    .leader-line {{
      transition: opacity 180ms ease, stroke-width 180ms ease;
      opacity: 0.55;
    }}
    .site-group:hover .leader-line {{
      opacity: 1;
      stroke-width: 2.2;
    }}
    .label-card {{
      transition: transform 180ms cubic-bezier(0.4,0,0.2,1),
                  filter 180ms ease;
      transform-box: fill-box;
      transform-origin: center;
    }}
    .site-group:hover .label-card {{
      transform: translateY(-2px);
      filter: drop-shadow(0 4px 8px rgba(10,31,68,0.14));
    }}
    .systemic-diamond {{
      transition: transform 180ms cubic-bezier(0.4,0,0.2,1);
      transform-box: fill-box;
      transform-origin: center;
    }}
    .systemic-group:hover .systemic-diamond {{
      transform: scale(1.3);
    }}
  </style>

  <!-- body silhouette -->
  <g fill="url(#bodyGrad)" stroke="#5fb1c4" stroke-width="2.4"
     stroke-linejoin="round" stroke-linecap="round">
    {body_paths}
  </g>

  <!-- ground shadow -->
  <ellipse cx="300" cy="985" rx="90" ry="6"
           fill="rgba(10,31,68,0.10)" filter="url(#softShadow)"/>

  <!-- systemic markers (drawn first, behind site markers if overlap) -->
  {''.join(sys_markers)}
  {''.join(sys_labels)}

  <!-- OSD-572 site markers + labels -->
  {''.join(site_markers)}
  {''.join(site_labels)}

  <!-- legend -->
  {legend}
</svg>
</div>
"""


# ---------------------------------------------------------------------------
# body silhouette — multiple smooth shapes layered into one
# ---------------------------------------------------------------------------

def _body_silhouette_paths() -> str:
    return (
        # head
        '<ellipse cx="300" cy="100" rx="55" ry="68"/>'
        # neck
        '<path d="M 275 160 Q 275 178, 285 192 L 315 192 Q 325 178, 325 160 Z"/>'
        # chest+abdomen
        '<path d="'
        'M 240 195 '
        'Q 270 185, 300 185 Q 330 185, 360 195 '
        'L 405 220 '
        'Q 412 250, 414 290 '
        'Q 414 330, 408 370 '
        'Q 402 415, 395 460 '
        'L 388 495 '
        'L 212 495 '
        'L 205 460 '
        'Q 198 415, 192 370 '
        'Q 186 330, 186 290 '
        'Q 188 250, 195 220 Z'
        '"/>'
        # left arm
        '<path d="'
        'M 195 220 '
        'Q 175 232, 165 268 '
        'Q 155 305, 148 348 '
        'Q 142 388, 138 420 '
        'Q 134 450, 130 480 '
        'L 142 488 '
        'Q 152 462, 162 432 '
        'Q 172 398, 182 360 '
        'Q 192 318, 200 282 '
        'Q 208 250, 215 230 Z'
        '"/>'
        # right arm
        '<path d="'
        'M 405 220 '
        'Q 425 232, 435 268 '
        'Q 445 305, 452 348 '
        'Q 458 388, 462 420 '
        'Q 466 450, 470 480 '
        'L 458 488 '
        'Q 448 462, 438 432 '
        'Q 428 398, 418 360 '
        'Q 408 318, 400 282 '
        'Q 392 250, 385 230 Z'
        '"/>'
        # left leg
        '<path d="'
        'M 220 495 '
        'Q 215 600, 220 700 '
        'Q 225 800, 240 880 '
        'L 254 950 '
        'L 286 950 '
        'L 290 880 '
        'Q 295 790, 295 695 '
        'Q 295 595, 290 510 '
        'L 285 495 Z'
        '"/>'
        # right leg
        '<path d="'
        'M 380 495 '
        'Q 385 600, 380 700 '
        'Q 375 800, 360 880 '
        'L 346 950 '
        'L 314 950 '
        'L 310 880 '
        'Q 305 790, 305 695 '
        'Q 305 595, 310 510 '
        'L 315 495 Z'
        '"/>'
        # left foot
        '<ellipse cx="270" cy="958" rx="20" ry="9"/>'
        # right foot
        '<ellipse cx="330" cy="958" rx="20" ry="9"/>'
    )


# ---------------------------------------------------------------------------
# markers & labels
# ---------------------------------------------------------------------------

def _marker_and_label(code: str, layout: dict, eff: dict) -> tuple[str, str]:
    color = _site_color(eff)
    r = _site_radius(eff)
    n = eff.get("n", 0)
    mean_abs = eff.get("mean_abs", 0.0)
    frac_up = eff.get("frac_up", 0.5)

    cx, cy = layout["x"], layout["y"]
    lx_box = 50 if layout["side"] == "L" else 600
    lx_text = lx_box + 10
    ly = layout["label_y"]
    line_to_x = lx_box + 100 if layout["side"] == "L" else lx_box
    line_to_y = ly + 24

    tooltip = (f"{code} – {layout['name']}\n"
               f"{layout['modality']}\n"
               f"n={n} concordant features\n"
               f"mean |log2FC|={mean_abs:.2f}\n"
               f"% trending up={100*frac_up:.0f}%")

    sub_text = (f"n={n} · |log2FC|={mean_abs:.2f}"
                if n else "no concordant signal")

    # Single group so CSS :hover cascades to leader line, marker circle,
    # AND the label card together.
    marker_block = (
        f'<g class="site-group"><title>{_html.escape(tooltip)}</title>'
        # leader line
        f'<line class="leader-line" x1="{cx}" y1="{cy}" '
        f'x2="{line_to_x}" y2="{line_to_y}" '
        f'stroke="{color}" stroke-width="1.2" stroke-dasharray="3 3"/>'
        # halo + marker dot
        f'<circle cx="{cx}" cy="{cy}" r="{r + 2}" '
        f'fill="rgba(255,255,255,0.85)" stroke="none"/>'
        f'<circle class="site-circle" cx="{cx}" cy="{cy}" r="{r}" '
        f'fill="{color}" stroke="{config.COLOR_PRIMARY}" '
        f'stroke-width="1.4"/>'
        # label card
        f'<g class="label-card">'
        f'<rect x="{lx_box}" y="{ly}" width="100" height="48" rx="6" '
        f'fill="white" stroke="{color}" stroke-width="1.6"/>'
        f'<text x="{lx_text}" y="{ly + 17}" '
        f'font-size="14" font-weight="700" '
        f'fill="{config.COLOR_PRIMARY}">{code}</text>'
        f'<text x="{lx_text}" y="{ly + 31}" font-size="10" '
        f'fill="#5a6675">{_html.escape(layout["name"])}</text>'
        f'<text x="{lx_text}" y="{ly + 43}" font-size="10" '
        f'fill="{color}" font-weight="600">{sub_text}</text>'
        f'</g>'
        f'</g>'
    )
    # Returned as (marker_block, "") since we now emit as one group.
    return marker_block, ""


def _systemic_marker_and_label(s: dict) -> tuple[str, str]:
    cx, cy = s["x"], s["y"]
    lx_box = 50 if s["side"] == "L" else 600
    lx_text = lx_box + 10
    ly = s["label_y"]
    line_to_x = lx_box + 100 if s["side"] == "L" else lx_box
    line_to_y = ly + 22

    tooltip = (f"{s['name']}\n"
               + "\n".join("  " + d for d in s["datasets"]))

    # Diamond marker
    d = 8
    diamond = (f'M {cx} {cy - d} L {cx + d} {cy} '
               f'L {cx} {cy + d} L {cx - d} {cy} Z')

    color = config.COLOR_PRIMARY

    short = s["name"]
    ds_short = " · ".join(d.split()[0] for d in s["datasets"])

    block = (
        f'<g class="systemic-group"><title>{_html.escape(tooltip)}</title>'
        f'<line class="leader-line" x1="{cx}" y1="{cy}" '
        f'x2="{line_to_x}" y2="{line_to_y}" '
        f'stroke="{color}" stroke-width="1.0" stroke-dasharray="2 3" '
        f'opacity="0.5"/>'
        f'<path class="systemic-diamond" d="{diamond}" '
        f'fill="{color}" stroke="white" stroke-width="1.4"/>'
        f'<g class="label-card">'
        f'<rect x="{lx_box}" y="{ly}" width="100" height="44" rx="6" '
        f'fill="#f3f7fa" stroke="{color}" stroke-width="1.4"/>'
        f'<text x="{lx_text}" y="{ly + 16}" font-size="11" '
        f'font-weight="700" fill="{config.COLOR_PRIMARY}">'
        f'{_html.escape(short)}</text>'
        f'<text x="{lx_text}" y="{ly + 32}" font-size="9" '
        f'fill="#5a6675">{_html.escape(ds_short)}</text>'
        f'</g>'
        f'</g>'
    )
    return block, ""


def _build_legend() -> str:
    """Small legend strip at the bottom of the SVG canvas."""
    items = [
        ("Microbiome swab UP",   config.COLOR_UP,    "circle"),
        ("Microbiome swab DOWN", config.COLOR_DOWN,  "circle"),
        ("Mixed direction",      config.COLOR_GOLD,  "circle"),
        ("Systemic / environmental", config.COLOR_PRIMARY, "diamond"),
    ]
    parts = ['<g transform="translate(80, 985)">']
    x = 0
    for label, color, shape in items:
        if shape == "circle":
            parts.append(
                f'<circle cx="{x + 8}" cy="0" r="7" fill="{color}" '
                f'stroke="{config.COLOR_PRIMARY}" stroke-width="1.2"/>'
            )
        else:
            parts.append(
                f'<path d="M {x + 8} -7 L {x + 15} 0 L {x + 8} 7 '
                f'L {x + 1} 0 Z" fill="{color}" stroke="white" '
                f'stroke-width="1.2"/>'
            )
        parts.append(
            f'<text x="{x + 22}" y="4" font-size="11" '
            f'fill="{config.COLOR_PRIMARY}">{label}</text>'
        )
        x += 22 + 9 * len(label)
    parts.append('</g>')
    return "".join(parts)
