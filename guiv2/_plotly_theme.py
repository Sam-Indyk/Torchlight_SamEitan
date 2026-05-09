"""Shared Plotly theme to keep charts readable on the navy + ice page.

The page background is a soft white -> ice-tint gradient. Plotly's
default white-paper plus default dark axis labels can render as a heavy
gray block against that background. Apply this theme to every figure so
the chart paper blends in and the ink is mission-navy.
"""
from __future__ import annotations

from guiv2 import config


def apply_clean_theme(fig, *, transparent: bool = True) -> None:
    """Mutate `fig` in place with the clean theme.

    transparent=True: make paper + plot transparent so the page gradient
                      shows through. Ideal for line/bar/scatter.
    transparent=False: white paper + transparent plot. Use when a hard
                       white frame helps (e.g., Sankey).
    """
    paper = "rgba(0,0,0,0)" if transparent else "#ffffff"
    fig.update_layout(
        paper_bgcolor=paper,
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="'Segoe UI', system-ui, sans-serif",
                  color=config.COLOR_PRIMARY, size=12),
        title_font=dict(color=config.COLOR_PRIMARY, size=14),
        legend=dict(font=dict(color=config.COLOR_PRIMARY, size=11),
                    bgcolor="rgba(255,255,255,0.85)",
                    bordercolor="rgba(95,177,196,0.40)",
                    borderwidth=1),
    )
    fig.update_xaxes(
        gridcolor="rgba(95,177,196,0.20)",
        zerolinecolor="rgba(95,177,196,0.45)",
        linecolor="rgba(10,31,68,0.35)",
        tickcolor="rgba(10,31,68,0.45)",
        title_font=dict(color=config.COLOR_PRIMARY, size=12),
        tickfont=dict(color=config.COLOR_PRIMARY),
    )
    fig.update_yaxes(
        gridcolor="rgba(95,177,196,0.20)",
        zerolinecolor="rgba(95,177,196,0.45)",
        linecolor="rgba(10,31,68,0.35)",
        tickcolor="rgba(10,31,68,0.45)",
        title_font=dict(color=config.COLOR_PRIMARY, size=12),
        tickfont=dict(color=config.COLOR_PRIMARY),
    )
