"""Visual config. Edit this file to change colors, layout, or page-level copy.

Anything that should be changeable without touching component code lives here.
"""

PAGE_TITLE = "Inspiration4 Multi-Omics Dashboard"
PAGE_ICON = "🧬"
LAYOUT = "wide"

# Color palette. Used for direction badges, heatmap scale, and accents.
COLOR_UP = "#d94545"
COLOR_DOWN = "#3471c4"
COLOR_NEUTRAL = "#9aa3ad"
COLOR_ACCENT = "#5fb1c4"
COLOR_BG_BANNER = "#fff8e1"
COLOR_TEXT_BANNER = "#5c4400"

# Heatmap colorscale (Plotly named scale or list of [stop, color]).
HEATMAP_COLORSCALE = "RdBu_r"

# How many decimals to show for log2FC.
LOG2FC_DECIMALS = 2

# Default top-N if a manifest view doesn't override it.
DEFAULT_TOP_N = 25

# Path to the manifest, relative to repo root.
MANIFEST_PATH = "gui/manifest.json"
