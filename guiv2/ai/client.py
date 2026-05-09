"""Thin Anthropic client wrapper.

Reads the API key from (in order):
  1. session_state["anthropic_api_key"] — set when the user pastes one
     into the GUI's "Bring your own key" textbox
  2. ANTHROPIC_API_KEY env var
  3. .streamlit/secrets.toml -> [anthropic] api_key

If none of these are set, returns a sentinel "no client" object that
the UI can detect and prompt the user to paste a key.

Default model: claude-haiku-4-5-20251001 — fast and cheap, fine for
two-paragraph summaries and NL Q&A grounded in a small JSON.
"""

from __future__ import annotations
import os
from typing import Any

try:
    import anthropic
except ImportError:  # graceful when the SDK isn't installed
    anthropic = None  # type: ignore

import streamlit as st


DEFAULT_MODEL = "claude-haiku-4-5-20251001"
DEFAULT_MAX_TOKENS = 800


def get_api_key() -> str | None:
    """Returns the key from session, env, or Streamlit secrets — or None."""
    key = st.session_state.get("anthropic_api_key")
    if key:
        return key
    key = os.environ.get("ANTHROPIC_API_KEY")
    if key:
        return key
    try:
        return st.secrets.get("anthropic", {}).get("api_key")
    except Exception:
        return None


def get_client() -> "anthropic.Anthropic | None":
    if anthropic is None:
        return None
    key = get_api_key()
    if not key:
        return None
    try:
        return anthropic.Anthropic(api_key=key)
    except Exception:
        return None


def generate(system: str, user: str,
             *, model: str = DEFAULT_MODEL,
             max_tokens: int = DEFAULT_MAX_TOKENS,
             temperature: float = 0.2) -> dict[str, Any]:
    """Run a single Claude completion and return:
        {"text": str, "input_tokens": int, "output_tokens": int}
    or
        {"error": "<message>"}

    Failures are returned as dicts so the UI doesn't crash on a missing
    key, network blip, or rate limit.
    """
    client = get_client()
    if client is None:
        return {"error": "no_client"}
    try:
        msg = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
    except Exception as e:
        return {"error": str(e)}
    text = "".join(b.text for b in msg.content if getattr(b, "type", "")
                   == "text")
    usage = getattr(msg, "usage", None)
    return {
        "text": text,
        "input_tokens":  getattr(usage, "input_tokens", None),
        "output_tokens": getattr(usage, "output_tokens", None),
        "model": model,
    }


def api_key_input(label: str = "Anthropic API key",
                  key_suffix: str = "default") -> None:
    """Render a password textbox for the user to paste their own key.

    `key_suffix` makes the Streamlit widget key unique when this helper
    is rendered from multiple panels in the same session. Stored only
    in st.session_state — never written to disk.
    """
    widget_key = f"_paste_anthropic_key__{key_suffix}"
    val = st.text_input(
        label,
        type="password",
        placeholder="sk-ant-...",
        help=("Pasted in the browser, kept in session state only, "
              "never written to disk. Anthropic free tier works."),
        key=widget_key,
    )
    if val:
        st.session_state["anthropic_api_key"] = val
        st.success("API key set for this session.")
