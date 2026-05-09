"""AI-generated per-astronaut narrative summaries.

Uses Claude (Anthropic API) grounded in dashboard_data.json to write a
short factual narrative for each crew member. Every numeric claim in
the output is verified against the source JSON; unverified numbers are
surfaced to the user as warnings.

Tabs: one per astronaut. Cached on disk (keyed by JSON hash) so reloads
don't burn tokens.
"""

from __future__ import annotations

import streamlit as st

from guiv2 import data
from guiv2.ai import client as ai_client, narrative as ai_narrative


def render_ai_narrative_panel(view: dict, manifest: dict) -> None:
    st.subheader(view["title"])
    st.markdown(
        "**AI-generated narrative summaries.** Two short paragraphs per "
        "astronaut, written by Claude using only the precomputed risk-"
        "profile JSON. Every number is verified against the source data; "
        "if a number is invented, the panel flags it. The deterministic "
        "rule-based version of these summaries lives in the *Per-astronaut "
        "report cards* panel."
    )

    dashboard = data.load_json(view.get("json", "data/dashboard_data.json"))
    if not dashboard:
        st.error("Dashboard JSON not found. "
                 "Run `python risk_profile_claude/build_risk_profile.py`.")
        return

    # ---- API key gate ---------------------------------------------------
    if ai_client.get_api_key() is None:
        st.warning(
            "No Anthropic API key found in environment, secrets, or "
            "session. Paste one below to enable narrative generation. "
            "The key stays in browser session state and is not written "
            "to disk."
        )
        ai_client.api_key_input(key_suffix="narrative")
        st.caption(
            "_Free tier works; you can get a key at console.anthropic.com. "
            "If you have an `ANTHROPIC_API_KEY` env var set when launching "
            "Streamlit, this gate is skipped automatically._"
        )
        return

    crew_ids = data.crew_columns(manifest)
    crew_names = data.crew_display_names(manifest)
    tab_labels = [crew_names.get(c, c) for c in crew_ids]
    tabs = st.tabs(tab_labels)

    for tab, crew_id in zip(tabs, crew_ids):
        with tab:
            _render_one_crew(crew_id, crew_names.get(crew_id, crew_id),
                             dashboard)


def _render_one_crew(crew_id: str, display_name: str,
                     dashboard: dict) -> None:
    cache_key = f"_ai_narrative_{crew_id}"
    force_key = f"_ai_narrative_force_{crew_id}"

    cols = st.columns([3, 1])
    cols[0].markdown(f"### {display_name}")
    if cols[1].button("Regenerate", key=f"regen_{crew_id}",
                      use_container_width=True):
        st.session_state[force_key] = True
        st.session_state.pop(cache_key, None)

    # generate / fetch
    if cache_key not in st.session_state:
        with st.spinner(f"Generating narrative for {display_name}…"):
            result = ai_narrative.generate_narrative(
                crew_id, dashboard,
                force=bool(st.session_state.pop(force_key, False)),
            )
        st.session_state[cache_key] = result
    else:
        result = st.session_state[cache_key]

    if "error" in result:
        st.error(f"Generation failed: `{result['error']}`. "
                 "Check your API key or try Regenerate.")
        return

    text = result.get("text", "")
    unverified = result.get("unverified", [])
    from_cache = result.get("from_cache", False)
    model = result.get("model", "?")

    # show the narrative inside a styled card
    st.markdown(
        f"<div class='ai-narrative-card'>{_md_to_html(text)}</div>",
        unsafe_allow_html=True,
    )

    # verification badges
    if unverified:
        st.warning(
            "**Unverified numbers in this narrative:** "
            f"`{', '.join(unverified)}`  \n"
            "These don't appear in the source JSON. Treat with skepticism, "
            "or click Regenerate to retry."
        )
    else:
        st.success(
            "✓ Every number in this narrative is grounded in "
            "`data/dashboard_data.json`."
        )

    src_label = "from cache" if from_cache else f"freshly generated · {model}"
    st.caption(
        f"_Narrative source: {src_label}. The two-paragraph format is "
        "enforced by the system prompt (see "
        "[`guiv2/ai/prompts.py`](../guiv2/ai/prompts.py))._"
    )


def _md_to_html(text: str) -> str:
    """Trivial markdown -> html for the two-paragraph card.
    Preserves paragraph breaks; escapes nothing fancy."""
    paras = [p.strip() for p in text.split("\n\n") if p.strip()]
    return "".join(f"<p>{p}</p>" for p in paras)
