"""Smoke-test guiv2 by running it through Streamlit's AppTest framework.

Verifies the app renders without exceptions on every panel and view.
Run from repo root:
    python guiv2/_smoketest.py
"""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from streamlit.testing.v1 import AppTest


def main() -> int:
    at = AppTest.from_file(str(REPO_ROOT / "guiv2" / "app.py"),
                           default_timeout=60)
    at.run()
    if at.exception:
        print("FAIL: app raised exception during initial render")
        for e in at.exception:
            print("  ", e.value)
        return 1

    def _ascii(s: str) -> str:
        return s.encode("ascii", "replace").decode("ascii")
    print(f"title: {_ascii(at.title[0].value) if at.title else '(no title)'}")
    print(f"tabs:  {[_ascii(t.label) for t in at.tabs]}")
    print(f"errors: {len(at.error)}  warnings: {len(at.warning)}")

    # Walk each tab and exercise it
    n_views = 0
    for tab in at.tabs:
        # Tabs are click-able children but in AppTest they render eagerly
        # within the script; just count subheaders and dataframes inside.
        n_views += len(tab.subheader)
    print(f"subheaders rendered: {n_views}")

    if at.error:
        print("FAIL: errors surfaced in the app:")
        for err in at.error:
            print("  ", err.value)
        return 1
    print("OK: app rendered all panels without errors")
    return 0


if __name__ == "__main__":
    sys.exit(main())
