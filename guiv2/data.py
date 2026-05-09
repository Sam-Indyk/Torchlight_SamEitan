"""Manifest, CSV, and JSON loading for guiv2.

Two data backends:
  - CSV files in analysis/results/ (per-subject heatmaps, pooled bar charts)
  - JSON file at data/dashboard_data.json (per-astronaut risk profiles, flow
    diagram). Schema is documented in risk_profile_claude/SCHEMA.md.

Both are cached so Streamlit reruns are fast.
"""

from __future__ import annotations
import json
from pathlib import Path

import pandas as pd
import streamlit as st

REPO_ROOT = Path(__file__).resolve().parent.parent


@st.cache_data
def load_manifest(manifest_path: str) -> dict:
    path = REPO_ROOT / manifest_path
    with path.open(encoding="utf-8") as f:
        return json.load(f)


@st.cache_data
def load_csv(csv_path: str) -> pd.DataFrame:
    """Load a CSV referenced by the manifest. Path is relative to repo root."""
    path = REPO_ROOT / csv_path
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


@st.cache_data
def load_json(json_path: str) -> dict:
    """Load a JSON document (e.g. dashboard_data.json). Returns {} if missing."""
    path = REPO_ROOT / json_path
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def crew_columns(manifest: dict) -> list[str]:
    return [c["id"] for c in manifest["metadata"]["crew"]]


def crew_display_names(manifest: dict) -> dict[str, str]:
    return {c["id"]: c["name"] for c in manifest["metadata"]["crew"]}


def find_axis(dashboard: dict, axis_id: str) -> dict | None:
    for ax in dashboard.get("axes", []):
        if ax.get("id") == axis_id:
            return ax
    return None
