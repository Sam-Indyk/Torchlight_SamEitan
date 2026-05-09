"""Visual config for guiv2.

Edit this file to change colors, layout, page-level copy, or paths.
Anything that should be changeable without touching component code lives here.
"""

PAGE_TITLE = "Inspiration4 — Microbiome–Immune–Barrier Axis Integrator"
PAGE_SUBTITLE = "Track 2 · Individualized Risk Profile"
PAGE_ICON = "🚀"
LAYOUT = "wide"

# Path to the manifest, relative to repo root.
MANIFEST_PATH = "guiv2/manifest.json"

# --- color palette ----------------------------------------------------------
# Keep accents readable on both light + dark Streamlit themes.

COLOR_UP        = "#d94545"   # elevated relative to baseline
COLOR_DOWN      = "#3471c4"   # suppressed relative to baseline
COLOR_NEUTRAL   = "#9aa3ad"
COLOR_ACCENT    = "#5fb1c4"
COLOR_BG_BANNER = "#fff8e1"
COLOR_TEXT_BANNER = "#5c4400"

# Per-astronaut crew colors used in the trajectory charts. Distinguishable
# in monochrome and color-vision-deficient palettes.
CREW_COLORS = {
    "C001": "#1f77b4",
    "C002": "#d62728",
    "C003": "#2ca02c",
    "C004": "#9467bd",
}

# CI band opacity (0-1).
CI_BAND_ALPHA = 0.18

# Heatmap colorscale (Plotly named scale or list of [stop, color]).
HEATMAP_COLORSCALE = "RdBu_r"

# Sankey layer colors (environment → host_site → barrier → systemic).
SANKEY_LAYER_COLORS = {
    "environment": "#7d8d96",
    "host_site":   "#5fb1c4",
    "barrier":     "#d4a052",
    "systemic":    "#a5536b",
}

# Edge-evidence colors. Strong-evidence edges are saturated; correlation-only
# edges are dimmed to communicate uncertainty visually.
SANKEY_EDGE_COLORS = {
    "shared_taxa_temporal": "rgba(95, 177, 196, 0.7)",
    "correlation_only":     "rgba(154, 163, 173, 0.45)",
}

# Numeric formatting.
LOG2FC_DECIMALS = 2
SCORE_DECIMALS = 2
DEFAULT_TOP_N = 25

# Risk-overview small-multiple grid layout (rows x cols).
RISK_OVERVIEW_GRID = (2, 2)
