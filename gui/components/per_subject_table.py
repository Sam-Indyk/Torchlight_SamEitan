"""Heatmap of top-N features × {C001..C004}, colored by per-subject log2FC."""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from gui import config, data


def render_per_subject_table(view: dict, manifest: dict) -> None:
    st.subheader(view["title"])

    df = data.load_csv(view["csv"])
    if df.empty:
        st.info(
            f"No features passed the concordance filter for this view "
            f"(`{view['csv']}`). This is itself a finding."
        )
        return

    crew_cols = data.crew_columns(manifest)
    expected = {"feature", "direction", "phase_compared", *crew_cols}
    missing = expected - set(df.columns)
    if missing:
        st.error(f"CSV is missing expected columns: {sorted(missing)}")
        st.dataframe(df.head())
        return

    top_n = view.get("top_n", config.DEFAULT_TOP_N)
    df = _sort_features(df, crew_cols, view.get("sort_by", "magnitude"))
    df = df.head(top_n)

    display_names = data.crew_display_names(manifest)
    z = df[crew_cols].to_numpy()

    fig = go.Figure(
        go.Heatmap(
            z=z,
            x=[display_names[c] for c in crew_cols],
            y=df["feature"].astype(str),
            colorscale=config.HEATMAP_COLORSCALE,
            zmid=0,
            colorbar=dict(title="log2FC"),
            hovertemplate=(
                "<b>%{y}</b><br>%{x}<br>log2FC: %{z:.2f}<extra></extra>"
            ),
        )
    )
    fig.update_layout(
        height=max(320, 22 * len(df) + 80),
        margin=dict(l=10, r=10, t=10, b=10),
        yaxis=dict(autorange="reversed", tickfont=dict(size=11)),
        xaxis=dict(side="top"),
    )
    st.plotly_chart(fig, use_container_width=True)

    with st.expander("Source data"):
        st.caption(view["csv"])
        st.dataframe(df.reset_index(drop=True))


def _sort_features(df: pd.DataFrame, crew_cols: list[str], sort_by: str) -> pd.DataFrame:
    if sort_by == "magnitude":
        df = df.assign(_mag=df[crew_cols].abs().mean(axis=1))
        return df.sort_values("_mag", ascending=False).drop(columns="_mag")
    if sort_by == "feature":
        return df.sort_values("feature")
    if sort_by == "direction":
        return df.sort_values(["direction", "feature"])
    return df
