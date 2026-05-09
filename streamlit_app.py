"""Streamlit Cloud entry point.

Streamlit Cloud auto-detects a top-level file named `streamlit_app.py`
or `app.py`. We keep the real app under guiv2/ for clarity, so this
shim just delegates.

Local dev: prefer `streamlit run guiv2/app.py` (slightly less
indirection in tracebacks). This file exists for cloud deploys.
"""
import sys
from pathlib import Path

# make the repo root importable so `guiv2.foo` works
sys.path.insert(0, str(Path(__file__).resolve().parent))

# delegate to the real app
from guiv2.app import main  # noqa: E402

if __name__ == "__main__":
    main()
else:
    # Streamlit imports the file at module level, not via __main__.
    main()
