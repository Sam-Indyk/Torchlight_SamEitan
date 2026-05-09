"""Per-astronaut clinical-style report card.

Reads dashboard_data.json, picks one astronaut at a time, and renders a
short factual summary for each Track 2 axis: status (elevated / suppressed
/ stable), magnitudes (R+1 score, population z), recovery half-life, and
within-cohort rank. Intended to read like the bottom of a clinical
report — short paragraphs, one per axis, no chartjunk.

Drives the "Track 2 astronaut-readable dashboard" deliverable described
in README.md ("a per-astronaut score trajectory ... an actionable line:
which marker is worth monitoring on a longer-duration mission, and what
preflight baseline would tighten the estimate next time").
"""
from __future__ import annotations

import streamlit as st

from guiv2 import data


_R1 = "R+1"
_R45 = "R+45"


def render_report_card(view: dict, manifest: dict) -> None:
    st.subheader(view["title"])

    dashboard = data.load_json(view["json"])
    if not dashboard:
        st.error(f"Could not load risk-profile JSON at `{view['json']}`. "
                 "Run risk_profile_claude/build_risk_profile.py first.")
        return

    timepoints = dashboard["metadata"]["timepoints"]
    axes = dashboard.get("axes", [])
    if _R1 not in timepoints or not axes:
        st.warning("Dashboard JSON missing required structure for report card.")
        return

    crew_names = data.crew_display_names(manifest)
    crew_ids = data.crew_columns(manifest)

    tab_labels = [crew_names.get(c, c) for c in crew_ids]
    tabs = st.tabs(tab_labels)
    for tab, crew_id in zip(tabs, crew_ids):
        with tab:
            _render_one_astronaut(crew_id, crew_names.get(crew_id, crew_id),
                                  axes, timepoints)


def _render_one_astronaut(crew_id: str, display_name: str,
                          axes: list[dict], timepoints: list[str]) -> None:
    st.markdown(f"### {display_name} — risk profile summary")

    r1_idx  = timepoints.index(_R1)
    r45_idx = timepoints.index(_R45) if _R45 in timepoints else None

    # ---- per-axis paragraphs ---------------------------------------------
    summary_rows: list[dict] = []
    for axis in axes:
        traj = axis.get("trajectories", {}).get(crew_id, {})
        scores = traj.get("scores", [])
        pop_z  = traj.get("population_z", [])
        rec    = traj.get("recovery")

        r1_score = scores[r1_idx] if r1_idx < len(scores) else None
        r1_popz  = pop_z[r1_idx]  if r1_idx  < len(pop_z)  else None
        r45_score = (scores[r45_idx]
                     if r45_idx is not None and r45_idx < len(scores)
                     else None)

        # cohort rank at R+1 (descending by absolute score)
        cohort_scores = [(c, axis["trajectories"][c]["scores"][r1_idx])
                         for c in axis.get("trajectories", {})]
        cohort_scores = [(c, v) for c, v in cohort_scores if v is not None]
        cohort_scores.sort(key=lambda r: abs(r[1]), reverse=True)
        rank = next((i + 1 for i, (c, _) in enumerate(cohort_scores)
                     if c == crew_id), None)
        n_ranked = len(cohort_scores)

        # build a one-paragraph summary
        para = _axis_paragraph(
            axis_label=axis.get("label", axis.get("id", "?")),
            r1_score=r1_score, r1_popz=r1_popz, r45_score=r45_score,
            recovery=rec, rank=rank, n_ranked=n_ranked,
            is_mock=axis.get("is_mock", False),
            is_cohort=axis.get("is_cohort_level", False),
            actionable=axis.get("actionable_line"),
        )
        st.markdown(para)

        summary_rows.append({
            "Axis": axis.get("label", axis.get("id")),
            "R+1 score":   _fmt(r1_score),
            "R+1 pop z":   _fmt(r1_popz),
            "R+45 score":  _fmt(r45_score),
            "Half-life (d)": (f"{rec['half_life_days']:.0f}"
                              if rec and rec.get("half_life_days") is not None
                              else "—"),
            "Cohort rank":  (f"{rank} of {n_ranked}" if rank else "—"),
        })

    # ---- compact summary table -------------------------------------------
    st.markdown("---")
    st.markdown("**Summary table**")
    st.dataframe(summary_rows, hide_index=True, use_container_width=True)

    # ---- top-line takeaway ------------------------------------------------
    biggest = _biggest_concern(axes, crew_id, r1_idx, r45_idx)
    if biggest:
        st.success(f"**Top-line:** {biggest}")


def _axis_paragraph(*, axis_label: str,
                    r1_score: float | None, r1_popz: float | None,
                    r45_score: float | None,
                    recovery: dict | None,
                    rank: int | None, n_ranked: int,
                    is_mock: bool, is_cohort: bool,
                    actionable: str | None) -> str:
    """Build a 2-3 sentence factual paragraph summarizing one axis for one
    astronaut.
    """
    flag = ""
    if is_mock:    flag = " *(preliminary — mock data)*"
    elif is_cohort: flag = " *(cohort-level only)*"

    if r1_score is None:
        return f"**{axis_label}**{flag}: no R+1 reading available."

    direction = "elevated" if r1_score > 0.3 else \
                "suppressed" if r1_score < -0.3 else "near baseline"

    pop_phrase = ""
    if r1_popz is not None:
        if abs(r1_popz) >= 2.0:
            pop_phrase = (f" — {abs(r1_popz):.1f} SD outside the healthy-adult "
                          f"reference range ({'high' if r1_popz > 0 else 'low'} side)")
        elif abs(r1_popz) >= 1.0:
            pop_phrase = (f" — within ~{abs(r1_popz):.1f} SD of the healthy-adult "
                          "reference range")
        else:
            pop_phrase = " — inside the healthy-adult reference range"

    recovery_phrase = ""
    if recovery is not None:
        q = recovery.get("fit_quality")
        hl = recovery.get("half_life_days")
        if q == "ok" and hl is not None:
            recovery_phrase = f" Half-life {hl:.0f} days"
            if r45_score is not None and abs(r45_score) < 0.3:
                recovery_phrase += " (returned to baseline by R+45)"
            recovery_phrase += "."
        elif q == "low_n" and hl is not None:
            recovery_phrase = (f" Half-life ~{hl:.0f} days "
                               "(low-confidence fit, only 2 same-side post points).")
        elif q == "non_decaying":
            recovery_phrase = (" Trajectory does not monotonically decay — "
                               "post-flight readings cross zero or oscillate.")
        elif q == "poor_fit":
            recovery_phrase = " Recovery fit is poor (R^2 < 0.5)."

    rank_phrase = ""
    if rank is not None and n_ranked > 1:
        if rank == 1:
            rank_phrase = (f" This is the largest absolute deviation across the "
                           f"crew on this axis (rank 1 of {n_ranked}).")
        elif rank == n_ranked:
            rank_phrase = (f" This is the smallest absolute deviation across "
                           f"the crew on this axis (rank {rank} of {n_ranked}).")
        else:
            rank_phrase = f" Rank {rank} of {n_ranked} for absolute deviation."

    para = (f"**{axis_label}**{flag}: {direction} at R+1 "
            f"(composite {r1_score:+.2f} own-baseline SD"
            f"{pop_phrase}).{recovery_phrase}{rank_phrase}")
    if actionable and not is_mock and not is_cohort:
        para += f"  \n*Action:* {actionable}"
    return para


def _biggest_concern(axes: list[dict], crew_id: str,
                     r1_idx: int, r45_idx: int | None) -> str | None:
    """Pick the axis where this astronaut shows the most concerning combination
    of (large R+1 deviation) AND (slow or non-decaying recovery)."""
    candidates = []
    for axis in axes:
        if axis.get("is_mock") or axis.get("is_cohort_level"):
            continue
        traj = axis.get("trajectories", {}).get(crew_id, {})
        scores = traj.get("scores", [])
        rec = traj.get("recovery")
        r1 = scores[r1_idx] if r1_idx < len(scores) else None
        if r1 is None:
            continue
        r1_abs = abs(r1)
        if rec is None:
            continue
        q = rec.get("fit_quality")
        hl = rec.get("half_life_days")
        # concern score: bigger initial deviation + slower recovery
        if q == "non_decaying":
            concern = r1_abs * 2.0  # non-decaying is worst
            phrase = (f"{axis['label']} — R+1 deviation of {r1:+.2f} SD that "
                      f"does not monotonically decay across the post-flight "
                      f"window. Worth a clinician's eye on a longer-duration "
                      f"mission.")
        elif hl is not None and hl > 60 and r1_abs > 0.5:
            concern = r1_abs * (hl / 60)
            phrase = (f"{axis['label']} — R+1 deviation of {r1:+.2f} SD with "
                      f"a slow half-life of {hl:.0f} days. Consider extended "
                      f"post-flight follow-up.")
        elif r1_abs > 1.0:
            concern = r1_abs
            phrase = (f"{axis['label']} — R+1 deviation of {r1:+.2f} SD "
                      f"(magnitude alone). Recovery profile is acceptable.")
        else:
            continue
        candidates.append((concern, phrase))
    if not candidates:
        return None
    candidates.sort(key=lambda r: r[0], reverse=True)
    return candidates[0][1]


def _fmt(v: float | None) -> str:
    if v is None:
        return "—"
    return f"{v:+.2f}"
