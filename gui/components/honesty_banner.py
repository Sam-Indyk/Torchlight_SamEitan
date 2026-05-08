"""Top-of-dashboard banner that surfaces null findings and methodological caveats."""

import streamlit as st

from gui import config


def render_honesty_banner(notes: list[str]) -> None:
    if not notes:
        return
    body = "  \n".join(f"- {n}" for n in notes)
    st.markdown(
        f"""
        <div style="background-color:{config.COLOR_BG_BANNER};
                    color:{config.COLOR_TEXT_BANNER};
                    padding:14px 18px;
                    border-radius:8px;
                    border-left:4px solid {config.COLOR_ACCENT};
                    margin-bottom:18px;">
          <strong>Honesty note</strong><br/>
          {body.replace(chr(10), "<br/>")}
        </div>
        """,
        unsafe_allow_html=True,
    )
