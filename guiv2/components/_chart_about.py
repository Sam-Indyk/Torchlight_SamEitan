"""Shared 'About this chart' helper.

A consistent expander placed beneath each main visualization that
spells out: what the chart is showing, what units the axes use, and
why this chart type was chosen. Helps judges read the dashboard cold
without having to ask questions.

Use:
    from guiv2.components._chart_about import about_chart
    about_chart(chart_type="line",
                shows="..",
                x_axis="..",
                y_axis="..",
                why="..")
"""

from __future__ import annotations

import streamlit as st


def about_chart(*, chart_type: str,
                shows: str,
                x_axis: str = "",
                y_axis: str = "",
                why: str = "") -> None:
    """Render an inline "About this chart" expander."""
    body = []
    body.append(f"**Chart type.** {chart_type}.")
    body.append(f"**What it shows.** {shows}")
    if x_axis:
        body.append(f"**X-axis.** {x_axis}")
    if y_axis:
        body.append(f"**Y-axis.** {y_axis}")
    if why:
        body.append(f"**Why this chart.** {why}")
    with st.expander("ⓘ About this chart"):
        st.markdown("  \n".join(body))
