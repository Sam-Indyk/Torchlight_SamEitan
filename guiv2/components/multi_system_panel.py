"""Multi-system deviation panel.

Renders the cross-axis Mahalanobis trajectory from
dashboard_data.json["multi_system_deviation"]. One scalar per astronaut
per timepoint that combines the four Track 2 axis composite scores into
a single 'how unusual is this astronaut across all four systems' number.

The README explicitly reserves the right to "create a single number risk
factor for ease of viewing and comparison between astronauts." This is
that number — but it's reported alongside (not in place of) the four
per-axis trajectories.
"""
from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

from guiv2 import config, data
from guiv2._plotly_theme import apply_clean_theme
from guiv2.components._chart_about import about_chart


def render_multi_system_panel(view: dict, manifest: dict) -> None:
    st.subheader(view["title"])

    dashboard = data.load_json(view["json"])
    if not dashboard:
        st.error(f"Could not load risk-profile JSON at `{view['json']}`. "
                 "Run risk_profile_claude/build_risk_profile.py first.")
        return

    msd = dashboard.get("multi_system_deviation")
    if not msd or not msd.get("per_astronaut"):
        st.info("Multi-system deviation not present in the risk-profile JSON. "
                "Re-run risk_profile_claude/build_risk_profile.py.")
        return

    timepoints = dashboard["metadata"]["timepoints"]
    crew_names = data.crew_display_names(manifest)

    # ---- explanation -----------------------------------------------------
    st.markdown(
        "**A single risk number per astronaut.** Mahalanobis distance from "
        "this astronaut's four-axis composite scores at each timepoint to "
        "the cohort's preflight joint distribution. Higher = farther outside "
        "the preflight envelope across multiple systems at once. Useful as "
        "an at-a-glance ranking, but read it alongside the per-axis panels — "
        "a high multi-system score doesn't tell you *which* axis is driving "
        "it."
    )

    # ---- trajectory chart ------------------------------------------------
    fig = go.Figure()
    for crew_id, traj in msd["per_astronaut"].items():
        ys = traj.get("scores", [None] * len(timepoints))
        color = config.CREW_COLORS.get(crew_id, "#444")
        fig.add_trace(go.Scatter(
            x=timepoints, y=ys,
            mode="lines+markers",
            name=crew_names.get(crew_id, crew_id),
            line=dict(color=color, width=2.5, shape="spline",
                      smoothing=0.6),
            marker=dict(size=8, color=color,
                        line=dict(color="white", width=1.5)),
            connectgaps=False,
            hovertemplate=(f"<b>{crew_names.get(crew_id, crew_id)}</b>"
                           "<br>%{x}: %{y:.2f} (Mahalanobis)<extra></extra>"),
            hoverlabel=dict(bgcolor=color, font=dict(color="white",
                                                     size=12)),
        ))

    # phase separators
    pre = dashboard["metadata"].get("preflight_timepoints", [])
    during = dashboard["metadata"].get("in_flight_timepoints", [])
    if pre and during:
        fig.add_vline(x=(timepoints.index(pre[-1]) + 0.5),
                      line_dash="dot", line_color="#aaa")
    if during:
        fig.add_vline(x=(timepoints.index(during[-1]) + 0.5),
                      line_dash="dot", line_color="#aaa")

    fig.update_layout(
        height=380,
        margin=dict(l=10, r=10, t=20, b=40),
        xaxis=dict(title="Mission timepoint (preflight L–, in-flight FD, post-flight R+)"),
        yaxis=dict(title="Multi-system Mahalanobis distance "
                         "(unitless · higher = farther outside preflight envelope)",
                   zeroline=False),
        legend=dict(orientation="h", yanchor="bottom", y=1.02,
                    xanchor="right", x=1),
        hovermode="x unified",
    )
    apply_clean_theme(fig)
    st.plotly_chart(fig, use_container_width=True)

    about_chart(
        chart_type="Trajectory line chart of multivariate Mahalanobis "
                   "distance, one line per astronaut",
        shows=("A single number per (astronaut, timepoint) that captures "
               "deviation across multiple Track 2 axes simultaneously. "
               "Computed as Mahalanobis distance from the cohort's "
               "preflight joint distribution over the per-axis composite "
               "score vector. Cohort-level axes (mitochondrial, where all "
               "four crew share the same trajectory) are excluded from "
               "the score because they have zero between-astronaut "
               "variance and would make the covariance singular."),
        x_axis="Mission timepoint (10 visits)",
        y_axis=("Mahalanobis distance, unitless and ≥ 0. Preflight "
                "values cluster at ~1–2 by construction. R+1 values "
                "in this cohort run 13–22, reflecting that all four "
                "crew sit far outside the preflight envelope on multiple "
                "systems at once."),
        why=("A line chart trades the per-axis detail of the small-"
             "multiples view for cohort-wide ranking. Useful as the "
             "single number the README explicitly reserves the right "
             "to compute for cross-astronaut comparison — but read "
             "alongside the per-axis panels, since one scalar can't "
             "tell you *which* axis is driving the deviation."),
    )

    # ---- ranking at R+1 (or selectable) ----------------------------------
    target_tp = view.get("ranking_at", "R+1")
    if target_tp not in timepoints:
        target_tp = "R+1" if "R+1" in timepoints else timepoints[0]
    idx = timepoints.index(target_tp)

    rows = []
    for crew_id, traj in msd["per_astronaut"].items():
        s = traj.get("scores", [])
        v = s[idx] if idx < len(s) else None
        if v is not None:
            rows.append((crew_id, v))
    rows.sort(key=lambda r: r[1], reverse=True)

    if rows:
        st.markdown(f"**Multi-system ranking at {target_tp}**")
        rank_data = [{"Rank": i + 1,
                      "Astronaut": crew_names.get(c, c),
                      "Multi-system distance": f"{v:.2f}"}
                     for i, (c, v) in enumerate(rows)]
        st.dataframe(rank_data, hide_index=True, use_container_width=True)

    # ---- methods note ----------------------------------------------------
    with st.expander("How this is computed"):
        st.write(msd.get("method", ""))
        st.caption(f"Axis order in the score vector: "
                   f"{msd.get('axis_order', [])}.  "
                   f"Preflight pool size: "
                   f"{msd.get('preflight_pool_n', '?')} rows.")
