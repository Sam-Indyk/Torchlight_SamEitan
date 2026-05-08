"""Manifest + CSV loading. Cached so Streamlit reruns are fast."""

import json
from pathlib import Path

import pandas as pd
import streamlit as st

REPO_ROOT = Path(__file__).resolve().parent.parent


@st.cache_data
def load_manifest(manifest_path: str) -> dict:
    path = REPO_ROOT / manifest_path
    with path.open() as f:
        return json.load(f)


@st.cache_data
def load_csv(csv_path: str) -> pd.DataFrame:
    """Load a CSV referenced by the manifest. Path is relative to repo root."""
    path = REPO_ROOT / csv_path
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_csv(path)
    return df


def crew_columns(manifest: dict) -> list[str]:
    return [c["id"] for c in manifest["metadata"]["crew"]]


def crew_display_names(manifest: dict) -> dict[str, str]:
    return {c["id"]: c["name"] for c in manifest["metadata"]["crew"]}
