"""Render one Track 2 axis as a trajectory dashboard.

Reads a single axis out of dashboard_data.json (produced by
risk_profile_claude/build_risk_profile.py) and renders:
  - A trajectory line chart with one line per astronaut, optional CI bands.
  - A choice of which score channel to display (composite score,
    own_baseline_z, population_z, or mahalanobis distance).
  - A within-cohort ranking at a selectable timepoint.
  - The methods note + actionable line + dataset/observability flags.

Schema reference: risk_profile_claude/SCHEMA.md
"""

from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

from guiv2 import config, data
from guiv2._plotly_theme import apply_clean_theme
from guiv2.components._chart_about import about_chart


_CHANNEL_LABELS = {
    "scores":         "Composite score — SDs from this astronaut's preflight mean",
    "own_baseline_z": "Own-baseline z — SDs from this astronaut's preflight mean",
    "population_z":   "Population z — SDs from healthy-adult reference range",
    "mahalanobis":    "Mahalanobis distance — multivariate, unitless, ≥ 0",
}


def render_risk_axis_panel(view: dict, manifest: dict) -> None:
    st.subheader(view["title"])

    dashboard = data.load_json(view["json"])
    if not dashboard:
        st.error(f"Could not load risk-profile JSON at `{view['json']}`. "
                 "Run risk_profile_claude/build_risk_profile.py first.")
        return

    axis_id = view["axis_id"]
    axis = data.find_axis(dashboard, axis_id)
    if axis is None:
        st.error(f"Axis `{axis_id}` not found in {view['json']}.")
        return

    # --- header strip: provenance, observability, mock/cohort flags --------
    flags = []
    if axis.get("is_mock"):         flags.append("preliminary (mock)")
    if axis.get("is_cohort_level"): flags.append("cohort-level only")
    if not axis.get("in_flight_observable", True):
        flags.append("ground-only")
    flag_html = (" · ".join(f"<code>{f}</code>" for f in flags)) \
                if flags else "&nbsp;"
    st.markdown(
        f"<div style='color:#666; font-size:0.92em; margin-bottom:8px;'>"
        f"Datasets: {', '.join(axis.get('datasets_used', []))}"
        f"{' · ' + flag_html if flags else ''}"
        "</div>",
        unsafe_allow_html=True,
    )
    st.markdown(f"_{axis.get('description', '')}_")

    # --- channel selector ---------------------------------------------------
    timepoints = dashboard["metadata"]["timepoints"]
    available = [k for k in _CHANNEL_LABELS
                 if any(any(v is not None
                            for v in axis["trajectories"][a].get(k, []))
                        for a in axis["trajectories"])]
    default_idx = available.index("scores") if "scores" in available else 0
    col1, col2 = st.columns([3, 2])
    with col1:
        channel = st.selectbox(
            "Score channel",
            options=available,
            index=default_idx,
            format_func=lambda k: _CHANNEL_LABELS.get(k, k),
            key=f"chan_{axis_id}",
        )
    with col2:
        show_ci = st.checkbox(
            "Show 95% bootstrap CI band",
            value=(channel == "scores"),
            key=f"ci_{axis_id}",
        )

    # --- trajectory chart ---------------------------------------------------
    fig = go.Figure()
    crew_names = data.crew_display_names(manifest)

    for crew_id, traj in axis["trajectories"].items():
        ys = traj.get(channel, [None] * len(timepoints))
        color = config.CREW_COLORS.get(crew_id, "#444")

        # main line — Plotly draws gaps where y is None, which is what we want
        # for unobservable timepoints. legendgroup keeps crew lines linked
        # across the chart and the legend toggle.
        fig.add_trace(go.Scatter(
            x=timepoints,
            y=ys,
            mode="lines+markers",
            name=crew_names.get(crew_id, crew_id),
            legendgroup=crew_id,
            line=dict(color=color, width=2.5, shape="spline", smoothing=0.6),
            marker=dict(size=8, color=color,
                        line=dict(color="white", width=1.5),
                        symbol="circle"),
            connectgaps=False,
            hovertemplate=(f"<b>{crew_names.get(crew_id, crew_id)}</b>"
                           "<br>%{x}: %{y:.2f} SD<extra></extra>"),
            hoverlabel=dict(bgcolor=color, font=dict(color="white",
                                                     size=12)),
        ))

        # CI band (only meaningful for the composite "scores" channel)
        if show_ci and channel == "scores":
            lo = traj.get("ci_lower")
            hi = traj.get("ci_upper")
            if lo and hi and any(v is not None for v in lo):
                xs_band = [tp for tp, lv, hv in zip(timepoints, lo, hi)
                           if lv is not None and hv is not None]
                lo_band = [lv for lv in lo if lv is not None]
                hi_band = [hv for hv in hi if hv is not None]
                if xs_band:
                    fillcolor = _hex_to_rgba(color, config.CI_BAND_ALPHA)
                    fig.add_trace(go.Scatter(
                        x=xs_band + xs_band[::-1],
                        y=hi_band + lo_band[::-1],
                        fill="toself",
                        fillcolor=fillcolor,
                        line=dict(color="rgba(0,0,0,0)"),
                        hoverinfo="skip",
                        showlegend=False,
                        name=f"{crew_id}_ci",
                    ))

    # vertical separators between mission phases
    pre  = dashboard["metadata"].get("preflight_timepoints", [])
    during = dashboard["metadata"].get("in_flight_timepoints", [])
    if pre and during:
        # boundary between last preflight and first in-flight
        boundary_x = (timepoints.index(pre[-1]) + 0.5)
        fig.add_vline(x=boundary_x, line_dash="dot", line_color="#aaa")
    if during:
        last_during = (timepoints.index(during[-1]) + 0.5)
        fig.add_vline(x=last_during, line_dash="dot", line_color="#aaa")

    # zero reference line
    fig.add_hline(y=0, line_color="#bbb", line_width=1)

    # prior-cohort overlay: horizontal line at the published-prior R+1
    # estimate, drawn only when we're showing the composite-score channel
    # so it remains comparable to the per-astronaut trajectories.
    overlay = axis.get("prior_cohort_overlay")
    if overlay and channel == "scores":
        prior_y = overlay.get("r1_score_estimate")
        if prior_y is not None:
            fig.add_hline(
                y=prior_y,
                line_dash="dash", line_color="#888",
                annotation_text=f"Prior cohort R+1 ≈ {prior_y:+.1f} "
                                f"({overlay.get('source', '?')})"
                                + (" *approx*"
                                   if overlay.get("is_approximate")
                                   else ""),
                annotation_position="top right",
                annotation_font=dict(size=10, color="#666"),
            )

    fig.update_layout(
        height=380,
        margin=dict(l=10, r=10, t=20, b=40),
        xaxis=dict(title="Mission timepoint (preflight L–, in-flight FD, post-flight R+)",
                   tickfont=dict(size=11)),
        yaxis=dict(title=_CHANNEL_LABELS[channel],
                   zeroline=False, tickfont=dict(size=11)),
        legend=dict(orientation="h", yanchor="bottom", y=1.02,
                    xanchor="right", x=1),
        hovermode="x unified",
    )
    apply_clean_theme(fig)
    st.plotly_chart(fig, use_container_width=True)

    about_chart(
        chart_type="Trajectory line chart, one line per astronaut, "
                   "with optional 95% bootstrap CI bands",
        shows=("How each astronaut's score on this axis changes from "
               "preflight (L−92, L−44, L−3) through in-flight (FD1–3, "
               "blanked when the assay required ground-only collection) "
               "to post-flight (R+1, R+45, R+82, R+194). Vertical dotted "
               "lines mark the phase boundaries; the solid horizontal "
               "line at y=0 is each astronaut's preflight baseline. "
               "If a published prior cohort overlay exists, it appears "
               "as a dashed reference line."),
        x_axis="Mission timepoint, ordinal (10 visits across pre/in/post)",
        y_axis=("Standard deviations (SDs) from baseline. Score channel "
                "is selectable above the chart: composite (own-baseline "
                "mean across the panel), own-baseline z, population z, "
                "or Mahalanobis. |z| ≥ 2 ≈ outside 95% interval."),
        why=("A line chart with one line per astronaut is the cleanest "
             "way to see (a) magnitude of deviation, (b) recovery "
             "trajectory, and (c) per-crew differences simultaneously. "
             "We deliberately avoid bar charts of single timepoints "
             "since the *shape* of recovery is the actual risk signal."),
    )

    # --- recovery rate (post-flight exponential decay fit) -----------------
    _render_recovery_table(axis, crew_names)

    # --- within-cohort ranking ---------------------------------------------
    wc = axis.get("within_cohort_comparison", {})
    if wc.get("ranking"):
        st.markdown("**Within-cohort ranking**")
        rank_df_rows = [
            {"Astronaut": crew_names.get(r["astronaut"], r["astronaut"]),
             "Score":     r["score"]}
            for r in wc["ranking"]
        ]
        st.dataframe(rank_df_rows, hide_index=True,
                     use_container_width=True)
        st.caption(wc.get("summary", ""))
    elif wc.get("summary"):
        st.markdown(f"**Within-cohort:** {wc['summary']}")

    # --- prior cohort -------------------------------------------------------
    prior = axis.get("prior_cohort_comparison")
    if prior and prior.get("summary"):
        st.markdown(f"**vs. published priors ({prior.get('source', '?')}):** "
                    f"{prior['summary']}")
    overlay = axis.get("prior_cohort_overlay")
    if overlay and overlay.get("r1_score_estimate") is not None:
        approx_tag = " *(approximate)*" if overlay.get("is_approximate") else ""
        st.caption(
            f"Reference line at R+1 = {overlay['r1_score_estimate']:+.1f} "
            f"from {overlay.get('source', '?')}.{approx_tag}  "
            f"_{overlay.get('method', '')}_"
        )

    # --- actionable line ---------------------------------------------------
    if axis.get("actionable_line"):
        st.success(f"**Actionable:** {axis['actionable_line']}")

    # --- methods + raw data expanders --------------------------------------
    with st.expander("Scoring method"):
        st.write(axis.get("scoring_method", ""))
        if axis.get("ground_only_note"):
            st.caption(f"Observability note: {axis['ground_only_note']}")
        if axis.get("feature_panel"):
            st.markdown("**Features in this panel:**")
            st.dataframe(axis["feature_panel"], hide_index=True,
                         use_container_width=True)

    with st.expander("Raw trajectories"):
        st.json(axis["trajectories"], expanded=False)


def _hex_to_rgba(hex_color: str, alpha: float) -> str:
    """Turn '#1f77b4' into 'rgba(31,119,180,0.18)' for fill colors."""
    h = hex_color.lstrip("#")
    if len(h) != 6:
        return f"rgba(100,100,100,{alpha})"
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{alpha:.3f})"


_QUALITY_LABELS = {
    "ok":           "good fit",
    "low_n":        "limited fit (only 2 same-side post points)",
    "poor_fit":     "poor fit (R^2 < 0.5)",
    "non_decaying": "trajectory does not monotonically decay",
}


def _render_recovery_table(axis: dict, crew_names: dict[str, str]) -> None:
    """Render the post-flight exponential-decay summary per astronaut.

    Reports tau (time constant) and half-life in days. A fast half-life means
    this astronaut recovered quickly on this axis; a slow or absent half-life
    is the actual risk signal we care about.
    """
    rows = []
    for crew_id, traj in axis.get("trajectories", {}).items():
        rec = traj.get("recovery")
        name = crew_names.get(crew_id, crew_id)
        if rec is None:
            rows.append({
                "Astronaut": name,
                "Half-life (days)":   "—",
                "tau (days)":         "—",
                "Initial deviation":  "—",
                "R^2":                "—",
                "Fit quality":        "no fit (small initial deviation or <2 post points)",
            })
            continue
        tau = rec.get("tau_days")
        hl  = rec.get("half_life_days")
        a   = rec.get("initial_deviation")
        r2  = rec.get("r_squared")
        q   = rec.get("fit_quality") or "—"
        rows.append({
            "Astronaut": name,
            "Half-life (days)":   f"{hl:.0f}" if hl is not None else "—",
            "tau (days)":         f"{tau:.0f}" if tau is not None else "—",
            "Initial deviation":  f"{a:+.2f}"  if a  is not None else "—",
            "R^2":                f"{r2:.2f}"  if r2 is not None else "—",
            "Fit quality":        _QUALITY_LABELS.get(q, q),
        })

    st.markdown("**Post-flight recovery rate** "
                "(exp decay fit on |y| over post timepoints)")
    st.dataframe(rows, hide_index=True, use_container_width=True)
    st.caption(
        "Half-life = days for the deviation to halve, fit on R+1 / R+45 / "
        "R+82 / R+194. Faster half-life = quicker return to baseline. "
        "Astronauts whose half-life is long (or whose trajectory does not "
        "decay at all) are the per-axis risk signals worth flagging."
    )
