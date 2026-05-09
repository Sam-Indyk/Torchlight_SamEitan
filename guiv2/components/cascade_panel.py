"""Upstream Causes — render cascade-inference results.

Reads `dashboard_data.json["cascade_inference"]` (computed by
risk_profile_claude/cascade_inference.py against the literature-derived
cascade table in pathway_priors.py) and renders, for each cascade:

  - The hypothesized stressor → root cause → intermediate nodes →
    terminal observations chain
  - A score and matched/missing/disagreed counts
  - The list of expected vs. observed perturbations with directional
    agreement
  - Confidence flag and citation

The panel is explicit that these are HYPOTHESIS-GENERATING — n=4
cannot prove a causal chain. The panel surfaces a top banner repeating
that and the README's honesty clauses.
"""

from __future__ import annotations

import streamlit as st

from guiv2 import config, data
from guiv2.components._chart_about import about_chart


_CONFIDENCE_BADGE = {
    "high":     ("High confidence", "#5fb1c4"),
    "moderate": ("Moderate confidence", "#d4a052"),
    "low":      ("Low confidence", "#9aa3ad"),
    "expected (currently unmatchable: see DDR axis)":
                ("Pending data: see DDR axis", "#9aa3ad"),
}


def render_cascade_panel(view: dict, manifest: dict) -> None:
    st.subheader(view["title"])

    dashboard = data.load_json(view.get("json", "data/dashboard_data.json"))
    if not dashboard:
        st.error("Dashboard JSON not found. "
                 "Run `python risk_profile_claude/build_risk_profile.py`.")
        return

    block = dashboard.get("cascade_inference")
    if not block or "cascades" not in block:
        st.info("Cascade inference is not present in this JSON. "
                "It is skipped in --mock-only builds; run the real "
                "build_risk_profile.py to populate.")
        return

    # ---- top banner: hypothesis-generating reminder ---------------------
    st.markdown(
        f"<div style='background:{config.COLOR_BG_BANNER};"
        f"color:{config.COLOR_PRIMARY};padding:12px 16px;border-radius:8px;"
        f"border-left:4px solid {config.COLOR_GOLD};margin-bottom:14px;'>"
        f"<strong>What this is.</strong> Each row below is a "
        "hypothesized cascade from a known spaceflight stressor "
        "(microgravity, radiation, fluid shift) through a root-cause "
        "node, through intermediate signaling, to terminal observable "
        "molecules. We score how many of those terminal observations "
        "actually move in the predicted direction in the analysis "
        "pipeline's output. <strong>This is hypothesis-generating, not "
        "causal proof.</strong> n = 4 cannot establish causation — we "
        "are flagging that the observed pattern is consistent with a "
        "known upstream cause, with the literature doing the causal "
        "lifting."
        "</div>",
        unsafe_allow_html=True,
    )
    st.caption(f"Method: {block.get('method', '—')}")
    st.caption(f"Total observations scanned: "
               f"{block.get('n_observations', 0):,}")

    # ---- ranking summary -------------------------------------------------
    st.markdown("### Ranking — cascades whose terminal observations match")
    rows = []
    for c in block["cascades"]:
        rows.append({
            "Cascade":       c.get("name", c.get("id", "?")),
            "Stressor":      c.get("stressor", "?"),
            "Score ratio":   f"{c.get('score_ratio', 0):.2f}",
            "Matched":       c.get("n_matched", 0),
            "Disagreed":     c.get("n_disagreed", 0),
            "Missing":       c.get("n_missing", 0),
            "Confidence":    c.get("confidence", "?"),
        })
    st.dataframe(rows, hide_index=True, use_container_width=True)
    st.caption(
        "**Score ratio** = weighted score / sum of terminal weights. "
        "Ratios > 1 indicate the cascade's terminal observations are "
        "matching with high observed strength. **Matched** = terminal "
        "observation moved in the expected direction; **Disagreed** = "
        "moved in the opposite direction (soft penalty); **Missing** = "
        "terminal feature not found in our pipeline output (could mean "
        "the assay didn't measure it, or the gene-symbol mapping isn't "
        "in place yet)."
    )

    about_chart(
        chart_type="Sortable summary table over a hand-curated cascade table",
        shows=("Each row is one of the eight literature-defined cascades "
               "from `risk_profile_claude/pathway_priors.py`, scored "
               "against every concordant perturbation in "
               "`analysis/results/`."),
        x_axis="Columns: cascade name, hypothesized stressor, score ratio "
               "(weighted matches / total weight), matched/disagreed/missing "
               "terminal-observation counts, confidence flag",
        y_axis="Rows: one cascade each. Sorted by score_ratio descending — "
               "top rows are the most strongly supported in this dataset",
        why=("A ranked table is the right shape when each row carries "
             "structured detail (stressor + counts + confidence) that "
             "doesn't reduce to a single number. The drill-down expanders "
             "below let judges inspect any cascade's full chain."),
    )

    st.divider()

    # ---- per-cascade detail ---------------------------------------------
    st.markdown("### Per-cascade detail")
    st.caption(
        "Click any cascade below to see the full chain (stressor → root "
        "cause → intermediates → terminal observations), the per-feature "
        "matches, the cited evidence, and the confidence flag."
    )
    for i, c in enumerate(block["cascades"]):
        _render_one_cascade(i, c)

    # ---- bottom honesty note -------------------------------------------
    st.divider()
    st.warning(
        f"**Honesty note from the analysis layer.**  \n"
        f"{block.get('honesty_note', '')}"
    )


def _render_one_cascade(idx: int, c: dict) -> None:
    badge_text, badge_color = _CONFIDENCE_BADGE.get(
        c.get("confidence", "moderate"),
        (c.get("confidence", "moderate"), "#9aa3ad"))

    score_ratio = c.get("score_ratio", 0.0)
    if score_ratio >= 1.0:
        rating = "✅ strong match"
    elif score_ratio >= 0.5:
        rating = "🟢 moderate match"
    elif score_ratio >= 0.1:
        rating = "🟡 weak match"
    else:
        rating = "⚪ no match (yet)"

    with st.expander(f"**{c.get('name', '?')}**  ·  {rating}  ·  "
                     f"score ratio {score_ratio:.2f}"):
        # header row with badges
        st.markdown(
            f"<span style='display:inline-block;padding:3px 10px;"
            f"border-radius:12px;background:{badge_color};color:white;"
            f"font-size:0.78rem;font-weight:600;letter-spacing:0.04em;"
            f"text-transform:uppercase;'>{badge_text}</span>  "
            f"<span style='margin-left:10px;color:#5a6675;font-size:0.85rem;'>"
            f"Stressor: <strong>{c.get('stressor', '?')}</strong>"
            f"</span>",
            unsafe_allow_html=True,
        )

        # hypothesized chain — rendered as colored pill chips with
        # arrows so the directionality of the cascade reads cleanly.
        st.markdown("**Hypothesized chain**")
        st.markdown(
            _render_chain_pills(
                stressor=c.get("stressor", "?"),
                root_cause=c.get("root_cause", "?"),
                intermediates=c.get("intermediate_nodes", []),
            ),
            unsafe_allow_html=True,
        )

        # mechanism prose
        st.markdown(f"_{c.get('mechanism', '')}_")

        # terminal-observation matches
        st.markdown("**Terminal observations matched against pipeline output:**")
        match_rows = []
        for r in c.get("terminal_results", []):
            obs = r.get("observed")
            agreement = r.get("agreement")
            sym = ("✅" if agreement is True
                   else ("❌" if agreement is False
                         else "—"))
            match_rows.append({
                "":                sym,
                "Feature":         r.get("feature", "?"),
                "Expected":        r.get("expected", "?"),
                "Observed":        obs if obs else "(not observed)",
                "Strength (|log2FC|)":
                    f"{r.get('strength', 0):.2f}" if r.get('strength') else "—",
                "Weight":          r.get("weight", 0),
                "Source CSV":      r.get("source") or "—",
            })
        st.dataframe(match_rows, hide_index=True,
                     use_container_width=True)

        # evidence
        st.markdown(f"**Evidence.** {c.get('evidence', '')}")


def _render_chain_pills(*, stressor: str, root_cause: str,
                         intermediates: list[str]) -> str:
    """HTML for the cascade chain, rendered as colored pill chips with
    arrow connectors. Uses inline styles so it works inside Streamlit's
    markdown renderer."""
    pill_styles = {
        "stressor":   ("#0a1f44", "white"),         # navy = upstream stressor
        "root":       ("#d4a052", "white"),         # gold = root cause
        "interm":     ("#5fb1c4", "white"),         # ice = intermediate
        "terminal":   ("rgba(95,177,196,0.18)", "#0a1f44"),
    }
    def pill(label: str, kind: str) -> str:
        bg, fg = pill_styles[kind]
        return (f'<span style="display:inline-block;padding:5px 11px;'
                f'border-radius:14px;background:{bg};color:{fg};'
                f'font-size:0.84rem;font-weight:600;'
                f'letter-spacing:0.01em;margin:3px 0;'
                f'box-shadow:0 1px 3px rgba(10,31,68,0.12);">'
                f'{label}</span>')
    arrow = ('<span style="color:#5a6675;font-size:1.1rem;'
             'margin:0 8px;font-weight:600;">→</span>')
    parts = [pill(stressor, "stressor"), arrow,
             pill(root_cause, "root")]
    for n in intermediates:
        parts += [arrow, pill(n, "interm")]
    parts += [arrow, pill("terminal observations", "terminal")]
    return ('<div style="display:flex;flex-wrap:wrap;align-items:center;'
            'gap:0;line-height:2;padding:6px 0 12px 0;">'
            + "".join(parts)
            + "</div>")
