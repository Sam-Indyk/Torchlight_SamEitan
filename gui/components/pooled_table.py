"""Sorted bar chart of top-N pooled-DE features by pooled log2FC."""

import plotly.graph_objects as go
import streamlit as st

from gui import config, data


def render_pooled_table(view: dict, manifest: dict) -> None:
    st.subheader(view["title"])

    df = data.load_csv(view["csv"])
    if df.empty:
        st.info(
            f"No pooled DE hits in this view (`{view['csv']}`). "
            "This is itself a finding."
        )
        return

    expected = {"feature", "direction", "phase_compared", "pooled"}
    missing = expected - set(df.columns)
    if missing:
        st.error(f"CSV is missing expected columns: {sorted(missing)}")
        st.dataframe(df.head())
        return

    top_n = view.get("top_n", config.DEFAULT_TOP_N)
    df = df.assign(_mag=df["pooled"].abs())
    df = df.sort_values("_mag", ascending=False).drop(columns="_mag").head(top_n)
    df = df.iloc[::-1]  # so the largest magnitudes appear at the top of the bar chart

    colors = [
        config.COLOR_UP if v >= 0 else config.COLOR_DOWN for v in df["pooled"]
    ]

    fig = go.Figure(
        go.Bar(
            x=df["pooled"],
            y=df["feature"].astype(str),
            orientation="h",
            marker_color=colors,
            hovertemplate=(
                "<b>%{y}</b><br>log2FC: %{x:.2f}<extra></extra>"
            ),
        )
    )
    fig.update_layout(
        height=max(320, 22 * len(df) + 80),
        margin=dict(l=10, r=10, t=10, b=40),
        xaxis=dict(title="log2FC (pooled)", zeroline=True, zerolinecolor="#888"),
        yaxis=dict(tickfont=dict(size=11)),
    )
    st.plotly_chart(fig, use_container_width=True)

    with st.expander("Source data"):
        st.caption(view["csv"])
        st.dataframe(df.reset_index(drop=True))
