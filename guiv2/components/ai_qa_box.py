"""Ask the Dashboard — natural-language Q&A over dashboard_data.json.

Sends the user's question + a slimmed copy of the dashboard JSON to
Claude, which is constrained by a tight system prompt to (1) answer
in 1-3 sentences, (2) cite numbers verbatim from the JSON, (3) refuse
out-of-scope inferences. Numeric claims in the answer are verified
against the source JSON; any unverified number is flagged.

Suggested questions are pre-loaded as buttons so judges can try the
feature without thinking up a question.
"""

from __future__ import annotations

import streamlit as st

from guiv2 import data
from guiv2.ai import client as ai_client, qa as ai_qa


SUGGESTED_QUESTIONS = [
    "Which astronaut had the largest R+1 inflammation deviation?",
    "Whose post-flight inflammation took longest to return to baseline?",
    "What's the multi-system deviation ranking at R+1?",
    "How does the cohort's R+1 immune score compare to the Tierney 2024 prior?",
    "Which body site had the strongest microbiome shift during flight?",
]


def render_ai_qa_box(view: dict, manifest: dict) -> None:
    st.subheader(view["title"])
    st.markdown(
        "**Ask the dashboard a question.** Claude reads the dashboard "
        "JSON and answers in 1-3 sentences, citing numbers verbatim from "
        "the source data. Out-of-scope questions (general spaceflight "
        "inference, clinical recommendations) are politely declined."
    )

    dashboard = data.load_json(view.get("json", "data/dashboard_data.json"))
    if not dashboard:
        st.error("Dashboard JSON not found. "
                 "Run `python risk_profile_claude/build_risk_profile.py`.")
        return

    # ---- API key gate ---------------------------------------------------
    if ai_client.get_api_key() is None:
        st.warning(
            "No Anthropic API key set. Paste one below to enable Q&A. "
            "Stored in browser session state only."
        )
        ai_client.api_key_input(label="Anthropic API key (for Q&A)",
                                 key_suffix="qa")
        return

    # ---- suggestion buttons -------------------------------------------
    st.markdown("**Try a suggested question:**")
    sugg_cols = st.columns(len(SUGGESTED_QUESTIONS))
    for col, q in zip(sugg_cols, SUGGESTED_QUESTIONS):
        if col.button(q, key=f"sugg_{hash(q)}", use_container_width=True):
            st.session_state["_qa_question"] = q

    # ---- input box -----------------------------------------------------
    question = st.text_input(
        "Or type your own:",
        value=st.session_state.get("_qa_question", ""),
        placeholder='e.g. "Which axis recovered fastest for C002?"',
        key="_qa_input",
    )
    submit = st.button("Ask", type="primary", key="_qa_submit",
                       use_container_width=False)

    if (submit or st.session_state.get("_qa_question")) and question.strip():
        # only run the LLM call if the question changed
        cache_key = f"_qa_answer::{question.strip()}"
        if cache_key not in st.session_state:
            with st.spinner("Reading the dashboard…"):
                result = ai_qa.answer(question, dashboard)
            st.session_state[cache_key] = result
        result = st.session_state[cache_key]
        # clear the suggestion-set so the user can re-type
        st.session_state.pop("_qa_question", None)

        if "error" in result:
            st.error(f"Q&A failed: `{result['error']}`")
            return

        st.markdown(
            f"<div class='ai-qa-card'>"
            f"<div class='ai-qa-q'>Q: {question.strip()}</div>"
            f"<div class='ai-qa-a'>{result.get('text', '')}</div>"
            f"</div>",
            unsafe_allow_html=True,
        )
        unverified = result.get("unverified", [])
        if unverified:
            st.warning(
                "**Unverified numbers in this answer:** "
                f"`{', '.join(unverified)}`. "
                "These don't appear in the JSON — treat with skepticism."
            )
        else:
            st.success(
                "✓ Every number in this answer is grounded in the "
                "dashboard JSON."
            )
        st.caption(
            f"_Model: {result.get('model', '?')}. The system prompt "
            "constrains Claude to cite verbatim numbers, refuse causal "
            "claims, and decline clinical recommendations._"
        )
