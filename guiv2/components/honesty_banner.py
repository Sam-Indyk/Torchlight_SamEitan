"""Top-of-dashboard banner that surfaces null findings and methodological caveats.

Adapted from gui/components/honesty_banner.py (Eitan's). Same visual treatment;
imports from guiv2.config so styling is independent.
"""

import streamlit as st

from guiv2 import config


def render_honesty_banner(notes: list[str]) -> None:
    if not notes:
        return
    body = "<br/>".join(f"• {n}" for n in notes)
    st.markdown(
        f"""
        <div style="background-color:{config.COLOR_BG_BANNER};
                    color:{config.COLOR_TEXT_BANNER};
                    padding:14px 18px;
                    border-radius:8px;
                    border-left:4px solid {config.COLOR_ACCENT};
                    margin-bottom:18px;
                    font-size:0.95em;
                    line-height:1.5;">
          <strong>Honesty note</strong><br/>
          {body}
        </div>
        """,
        unsafe_allow_html=True,
    )
