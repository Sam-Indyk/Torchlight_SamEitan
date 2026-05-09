"""Side-by-side astronaut comparison panel.

Pick any two crew members from a pair of selectboxes; the panel
overlays their trajectories on every Track 2 axis, computes a per-
axis difference table (R+1 score gap, R+45 score gap, recovery
half-life gap), and shows the multi-system Mahalanobis distance gap.

Answers the actual Track 2 question — "given two candidates, who
should fly?" — without forcing a single risk number to do all the work.
"""

from __future__ import annotations

import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

from guiv2 import config, data
from guiv2._plotly_theme import apply_clean_theme
from guiv2.components._chart_about import about_chart


def render_astronaut_compare(view: dict, manifest: dict) -> None:
    st.subheader(view["title"])

    dashboard = data.load_json(view.get("json", "data/dashboard_data.json"))
    if not dashboard:
        st.error("Dashboard JSON not found. "
                 "Run `python risk_profile_claude/build_risk_profile.py`.")
        return

    crew_ids = data.crew_columns(manifest)
    crew_names = data.crew_display_names(manifest)
    if len(crew_ids) < 2:
        st.info("Need at least two crew members to compare.")
        return

    # ---- selectors ---------------------------------------------------
    cols = st.columns([1, 1, 2])
    with cols[0]:
        a_id = st.selectbox(
            "Astronaut A", options=crew_ids,
            format_func=lambda c: crew_names.get(c, c),
            index=0, key="_compare_a")
    with cols[1]:
        # default B = the second crew member, but skip whichever was picked
        # for A so the dropdown never starts on a duplicate
        default_b = next((i for i, c in enumerate(crew_ids) if c != a_id), 1)
        b_id = st.selectbox(
            "Astronaut B", options=crew_ids,
            format_func=lambda c: crew_names.get(c, c),
            index=default_b, key="_compare_b")
    if a_id == b_id:
        st.info("Pick two different crew members to compare.")
        return

    a_color = config.CREW_COLORS.get(a_id, "#444")
    b_color = config.CREW_COLORS.get(b_id, "#888")
    a_label = crew_names.get(a_id, a_id)
    b_label = crew_names.get(b_id, b_id)

    timepoints = dashboard["metadata"]["timepoints"]
    axes = dashboard.get("axes", [])

    # ---- 4-axis trajectory comparison --------------------------------
    n_axes = len(axes)
    rows = 2
    cols_g = (n_axes + rows - 1) // rows
    titles = [ax.get("label", ax.get("id", "?"))
              + ("  *(mock)*" if ax.get("is_mock") else
                 "  *(cohort-level)*" if ax.get("is_cohort_level") else "")
              for ax in axes]

    fig = make_subplots(rows=rows, cols=cols_g,
                         subplot_titles=titles,
                         horizontal_spacing=0.08, vertical_spacing=0.18)
    legend_seen: set[str] = set()
    for i, ax in enumerate(axes):
        r = i // cols_g + 1
        c = i % cols_g + 1
        for crew_id, color in ((a_id, a_color), (b_id, b_color)):
            traj = ax.get("trajectories", {}).get(crew_id, {})
            ys = traj.get("scores", [None] * len(timepoints))
            show_legend = crew_id not in legend_seen
            legend_seen.add(crew_id)
            fig.add_trace(go.Scatter(
                x=timepoints, y=ys,
                mode="lines+markers",
                name=(a_label if crew_id == a_id else b_label),
                line=dict(color=color, width=2.6, shape="spline",
                          smoothing=0.6),
                marker=dict(size=8, color=color,
                            line=dict(color="white", width=1.5)),
                connectgaps=False,
                legendgroup=crew_id, showlegend=show_legend,
                hovertemplate=(f"<b>{(a_label if crew_id==a_id else b_label)}"
                               f" — {ax.get('label')}</b>"
                               "<br>%{x}: %{y:.2f} SD<extra></extra>"),
                hoverlabel=dict(bgcolor=color,
                                font=dict(color="white", size=11)),
            ), row=r, col=c)
        fig.add_hline(y=0, line_color="#bbb", line_width=1, row=r, col=c)

    fig.update_layout(
        height=420 * rows,
        margin=dict(l=10, r=10, t=60, b=40),
        legend=dict(orientation="h", yanchor="bottom", y=1.04,
                    xanchor="center", x=0.5),
        hovermode="closest",
    )
    fig.update_xaxes(tickfont=dict(size=9),
                     title=dict(text="Mission timepoint",
                                font=dict(size=10)))
    fig.update_yaxes(tickfont=dict(size=10), zeroline=False,
                     title=dict(text="SDs from preflight",
                                font=dict(size=10)))
    apply_clean_theme(fig)
    st.plotly_chart(fig, use_container_width=True)

    # ---- per-axis difference table ------------------------------------
    r1_idx  = timepoints.index("R+1") if "R+1" in timepoints else None
    r45_idx = timepoints.index("R+45") if "R+45" in timepoints else None
    diff_rows: list[dict] = []
    for ax in axes:
        a_traj = ax.get("trajectories", {}).get(a_id, {})
        b_traj = ax.get("trajectories", {}).get(b_id, {})
        a_r1  = _idx(a_traj.get("scores"), r1_idx)
        b_r1  = _idx(b_traj.get("scores"), r1_idx)
        a_r45 = _idx(a_traj.get("scores"), r45_idx)
        b_r45 = _idx(b_traj.get("scores"), r45_idx)
        a_rec = (a_traj.get("recovery") or {}).get("half_life_days")
        b_rec = (b_traj.get("recovery") or {}).get("half_life_days")
        diff_rows.append({
            "Axis":              ax.get("label", ax.get("id", "?")),
            f"{a_label} R+1":   _fmt_num(a_r1, "SD"),
            f"{b_label} R+1":   _fmt_num(b_r1, "SD"),
            "Δ R+1 (A−B)":      _fmt_diff(a_r1, b_r1, "SD"),
            f"{a_label} R+45":  _fmt_num(a_r45, "SD"),
            f"{b_label} R+45":  _fmt_num(b_r45, "SD"),
            f"{a_label} t½":    _fmt_num(a_rec, "d"),
            f"{b_label} t½":    _fmt_num(b_rec, "d"),
            "Δ t½ (A−B)":       _fmt_diff(a_rec, b_rec, "d"),
        })
    st.markdown("### Per-axis difference (A − B)")
    st.dataframe(diff_rows, hide_index=True, use_container_width=True)
    st.caption(
        "**SD** = standard deviations from this astronaut's own preflight "
        "mean. **t½** = post-flight recovery half-life in days from the "
        "exponential-decay fit. Negative Δ means A is below B; positive "
        "means above. Empty cells are timepoints that weren't observed "
        "(e.g., in-flight blood draws on this mission)."
    )

    # ---- multi-system gap --------------------------------------------
    msd = dashboard.get("multi_system_deviation", {})
    msd_per = (msd or {}).get("per_astronaut", {})
    if msd_per and a_id in msd_per and b_id in msd_per:
        st.markdown("### Multi-system Mahalanobis trajectory")
        msd_fig = go.Figure()
        for crew_id, color, label in (
            (a_id, a_color, a_label), (b_id, b_color, b_label)
        ):
            ys = msd_per[crew_id].get("scores", [None] * len(timepoints))
            msd_fig.add_trace(go.Scatter(
                x=timepoints, y=ys,
                mode="lines+markers", name=label,
                line=dict(color=color, width=2.6, shape="spline",
                          smoothing=0.6),
                marker=dict(size=8, color=color,
                            line=dict(color="white", width=1.5)),
                connectgaps=False,
                hovertemplate=(f"<b>{label}</b>"
                               "<br>%{x}: %{y:.2f}<extra></extra>"),
                hoverlabel=dict(bgcolor=color,
                                font=dict(color="white", size=11)),
            ))
        msd_fig.update_layout(
            height=320,
            margin=dict(l=10, r=10, t=20, b=40),
            xaxis=dict(title="Mission timepoint"),
            yaxis=dict(title="Multi-system Mahalanobis distance "
                             "(unitless · higher = farther outside preflight)"),
            legend=dict(orientation="h", yanchor="bottom", y=1.02,
                        xanchor="right", x=1),
            hovermode="x unified",
        )
        apply_clean_theme(msd_fig)
        st.plotly_chart(msd_fig, use_container_width=True)

        # gap at R+1
        if r1_idx is not None:
            a_d = _idx(msd_per[a_id].get("scores"), r1_idx)
            b_d = _idx(msd_per[b_id].get("scores"), r1_idx)
            if a_d is not None and b_d is not None:
                gap = a_d - b_d
                bigger = a_label if gap > 0 else b_label
                st.markdown(
                    f"**At R+1**, {a_label} sits at "
                    f"`{a_d:.2f}` and {b_label} at `{b_d:.2f}` — "
                    f"{bigger} is `{abs(gap):.2f}` units farther outside "
                    "the cohort's preflight envelope on this scoring."
                )

    about_chart(
        chart_type="Side-by-side trajectory subplots + per-axis difference table",
        shows=("Two astronauts overlaid on every Track 2 axis, plus a "
               "summary table that subtracts B's R+1, R+45, and recovery "
               "half-life from A's. The multi-system Mahalanobis chart "
               "compresses everything into one trajectory pair."),
        x_axis="Mission timepoints (10 visits across pre / in-flight / post). "
               "Same scale as the per-axis panels.",
        y_axis="SDs from each astronaut's own preflight mean per subplot, "
               "and unitless Mahalanobis distance for the multi-system "
               "chart at the bottom.",
        why=("Same-scale overlays plus a numeric diff table is the "
             "cleanest way to surface 'who differs from whom and on which "
             "axis.' Track 2's astronaut-facing question is multifaceted, "
             "so we don't collapse to one number — but the multi-system "
             "Mahalanobis at the bottom is there for ordering when you "
             "need a single ranked comparator."),
    )


def _idx(seq, i):
    if seq is None or i is None or i >= len(seq):
        return None
    return seq[i]


def _fmt_num(v, unit: str) -> str:
    if v is None:
        return "—"
    return f"{v:+.2f} {unit}" if unit == "SD" else f"{v:.0f} {unit}"


def _fmt_diff(a, b, unit: str) -> str:
    if a is None or b is None:
        return "—"
    diff = a - b
    return f"{diff:+.2f} {unit}" if unit == "SD" else f"{diff:+.0f} {unit}"
