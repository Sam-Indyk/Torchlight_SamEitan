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

# --- color palette: Mission navy + ice -------------------------------------

COLOR_PRIMARY    = "#0a1f44"   # deep mission navy (header, primary text)
COLOR_PRIMARY_2  = "#1a3970"   # navy 2 (gradient, hover)
COLOR_ICE        = "#5fb1c4"   # ice blue (accents, lines)
COLOR_ICE_2      = "#9bd1de"   # ice blue light (subtle backgrounds)
COLOR_GOLD       = "#d4a052"   # warm accent (highlights, ranking #1)

COLOR_UP         = "#d94545"   # elevated relative to baseline
COLOR_DOWN       = "#3471c4"   # suppressed relative to baseline
COLOR_NEUTRAL    = "#9aa3ad"
COLOR_ACCENT     = COLOR_ICE
COLOR_BG_BANNER  = "#f3f7fa"   # very light ice — banner background
COLOR_TEXT_BANNER = COLOR_PRIMARY

# Per-astronaut crew colors. Distinguishable in monochrome and color-vision-
# deficient palettes; tuned to read against the navy/ice theme.
CREW_COLORS = {
    "C001": "#1f77b4",   # blue
    "C002": "#d62728",   # red
    "C003": "#2ca02c",   # green
    "C004": "#9467bd",   # purple
}

CREW_DISPLAY_LABEL = {  # short label used inside avatar circles
    "C001": "C1",
    "C002": "C2",
    "C003": "C3",
    "C004": "C4",
}

# Roles per OSDR pseudonymous IDs. Public Inspiration-4 mission documentation
# describes 4 mission roles; OSDR doesn't tie them to specific subject IDs,
# so we list the role set without claiming a specific C001<->role mapping.
CREW_ROLES_NOTE = ("OSDR pseudonymizes Inspiration-4 crew as C001-C004. "
                   "The mission roles were Mission Commander, Pilot, "
                   "Medical Officer, and Mission Specialist; OSDR does not "
                   "publish which subject ID corresponds to which role.")

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
