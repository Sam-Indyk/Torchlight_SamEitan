"""Mission Overview hero panel.

First thing judges see when they open the dashboard. Renders:
  - A hero banner with mission name and tagline
  - Anonymous crew cards (C001-C004) with role context
  - Quick-stat cards (n=4, datasets, hits, axes scored)
  - Mission timeline strip with the ten timepoints
"""

from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

from guiv2 import config, data
from guiv2._plotly_theme import apply_clean_theme
from guiv2.components._chart_about import about_chart


def render_mission_overview(view: dict, manifest: dict) -> None:
    dashboard = data.load_json(view["json"]) if view.get("json") else {}
    meta = manifest.get("metadata", {})

    # --- hero banner -------------------------------------------------------
    st.markdown(
        f"""
        <div class="mission-hero">
          <div class="mission-hero-title">Inspiration-4</div>
          <div class="mission-hero-sub">Multi-omics individualized risk profile · Track 2 · n = 4 · 9 OSDR datasets</div>
          <div class="mission-hero-tag">A microbiome → barrier → immune integrator written for the crew member it's about.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # --- crew cards --------------------------------------------------------
    st.markdown("### Crew (OSDR pseudonymous IDs)")
    st.caption(config.CREW_ROLES_NOTE)
    cols = st.columns(4, gap="medium")
    for crew, col in zip(meta.get("crew", []), cols):
        cid = crew.get("id", "?")
        color = config.CREW_COLORS.get(cid, "#444")
        avatar = config.CREW_DISPLAY_LABEL.get(cid, cid[-2:])
        with col:
            st.markdown(
                f"""
                <div class="crew-card">
                  <div class="crew-avatar" style="background:{color};">{avatar}</div>
                  <div class="crew-name">{cid}</div>
                  <div class="crew-role">{crew.get('role', '')}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    # --- quick-stat cards --------------------------------------------------
    st.markdown("### At a glance")
    n_axes = len(dashboard.get("axes", []))
    n_real = sum(1 for ax in dashboard.get("axes", [])
                 if not ax.get("is_mock"))
    n_dsets = len({d for ax in dashboard.get("axes", [])
                   for d in ax.get("datasets_used", [])})
    flow = dashboard.get("flow_diagram", {}).get("cohort_level_facts", {})
    nap_overlap = flow.get("capsule_to_NAP_shared_fraction")

    stat_rows = [
        ("Crew",  f"{len(meta.get('crew', []))}",          "n = 4 (per-astronaut)"),
        ("Axes scored", f"{n_axes}",                        f"{n_real} real, {n_axes - n_real} preliminary"),
        ("OSDR datasets", f"{n_dsets}",                     "of 12 in the starter notebook"),
        ("Concordant features",         "66,917",           "all 4 crew, |log2FC| ≥ 1"),
    ]
    if nap_overlap is not None:
        stat_rows.append(
            ("Capsule → crew NAP",     f"{100*nap_overlap:.0f}%",
             "of crew shifts also detected on capsule"))
    stat_cols = st.columns(len(stat_rows), gap="small")
    for col, (label, big, sub) in zip(stat_cols, stat_rows):
        with col:
            st.markdown(
                f"""
                <div class="stat-card">
                  <div class="stat-big">{big}</div>
                  <div class="stat-label">{label}</div>
                  <div class="stat-sub">{sub}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    # --- mission timeline strip --------------------------------------------
    st.markdown("### Mission timeline")
    timeline_fig = _make_timeline(
        timepoints=dashboard.get("metadata", {}).get(
            "timepoints", view.get("timepoints", [])),
        pre=dashboard.get("metadata", {}).get(
            "preflight_timepoints",  ["L-92", "L-44", "L-3"]),
        during=dashboard.get("metadata", {}).get(
            "in_flight_timepoints", ["FD1", "FD2", "FD3"]),
        post=dashboard.get("metadata", {}).get(
            "postflight_timepoints", ["R+1", "R+45", "R+82", "R+194"]),
    )
    st.plotly_chart(timeline_fig, use_container_width=True)
    st.caption(
        "Days are nominal. Preflight L−92, L−44, L−3 sample at 92, 44, "
        "and 3 days before launch; FD = flight day; R+ = days after return. "
        "Phlebotomy-dependent panels (CMP, CBC, plasma, urine) sampled "
        "only at preflight and post-flight; microbiome swabs sampled "
        "across all phases including in-flight."
    )

    about_chart(
        chart_type="Annotated timeline strip with phase shading",
        shows=("All ten sampling timepoints positioned by their actual "
               "day-relative-to-launch. Background shading marks the "
               "three mission phases: preflight (navy tint), in-flight "
               "(gold tint), post-flight (ice tint)."),
        x_axis="Days relative to launch (day 0 = launch). Negative = "
               "preflight, 1–3 = in flight, ≥4 = post-flight.",
        y_axis="None — the chart is a 1-D timeline, all markers on a "
               "shared horizontal line.",
        why=("Showing the actual day spacing (not just labels in order) "
             "makes it visually obvious that recovery sampling was "
             "front-loaded near landing and tapered out to ~6 months "
             "post-flight. That's important context for reading the "
             "recovery half-life numbers in the per-axis panels."),
    )


def _make_timeline(timepoints, pre, during, post) -> go.Figure:
    """A horizontal timepoint strip with phase shading and labeled markers."""
    if not timepoints:
        timepoints = pre + during + post
    days_map = {"L-92": -92, "L-44": -44, "L-3": -3,
                "FD1": 1, "FD2": 2, "FD3": 3,
                "R+1": 4, "R+45": 48, "R+82": 85, "R+194": 197}
    xs = [days_map.get(tp, i) for i, tp in enumerate(timepoints)]
    colors = []
    for tp in timepoints:
        if tp in pre:    colors.append(config.COLOR_PRIMARY)
        elif tp in during: colors.append(config.COLOR_GOLD)
        elif tp in post: colors.append(config.COLOR_ICE)
        else:           colors.append(config.COLOR_NEUTRAL)

    fig = go.Figure()
    # phase rectangles
    fig.add_shape(type="rect",
                  x0=days_map["L-92"] - 5, x1=days_map["L-3"] + 1,
                  y0=-0.3, y1=0.3, line=dict(width=0),
                  fillcolor="rgba(10,31,68,0.10)", layer="below")
    fig.add_shape(type="rect",
                  x0=days_map["FD1"] - 0.5, x1=days_map["FD3"] + 0.5,
                  y0=-0.3, y1=0.3, line=dict(width=0),
                  fillcolor="rgba(212,160,82,0.18)", layer="below")
    fig.add_shape(type="rect",
                  x0=days_map["R+1"] - 0.5, x1=days_map["R+194"] + 5,
                  y0=-0.3, y1=0.3, line=dict(width=0),
                  fillcolor="rgba(95,177,196,0.15)", layer="below")
    # markers
    fig.add_trace(go.Scatter(
        x=xs, y=[0]*len(xs),
        mode="markers+text",
        text=timepoints,
        textposition="top center",
        textfont=dict(size=11, color=config.COLOR_PRIMARY),
        marker=dict(size=14, color=colors,
                    line=dict(color="white", width=2)),
        hovertext=[f"{tp} (day {x})" for tp, x in zip(timepoints, xs)],
        hoverinfo="text",
        showlegend=False,
    ))
    # phase labels
    for x, lbl in [(-50, "Preflight"), (2, "In flight"), (100, "Post-flight")]:
        fig.add_annotation(x=x, y=-0.7, text=f"<b>{lbl}</b>",
                           showarrow=False,
                           font=dict(size=12, color=config.COLOR_PRIMARY))
    fig.update_layout(
        height=170,
        margin=dict(l=10, r=10, t=20, b=20),
        xaxis=dict(title="Days relative to launch",
                   range=[-100, 210], showgrid=False, zeroline=False,
                   tickvals=[-90, -45, 0, 45, 90, 135, 180],
                   ticktext=["−90", "−45", "0 (launch)", "+45", "+90", "+135", "+180"]),
        yaxis=dict(visible=False, range=[-1, 1]),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
    )
    apply_clean_theme(fig)
    return fig
