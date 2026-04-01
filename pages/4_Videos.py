#!/usr/bin/env python3
"""Video generation page for the Cash Cow multipage dashboard."""

from __future__ import annotations

import streamlit as st

from bridge import run_bridge, submit_video
from dashboard_shared import get_prompt_vibes, get_top_markets, refresh_dashboard, render_overview_metrics, render_shell


st.set_page_config(page_title="Videos | Cash Cow", page_icon="CC", layout="wide")
render_shell("Videos", "Push scored markets into MoneyPrinterTurbo or demo mode")
render_overview_metrics()

markets = get_top_markets(8)
vibes = get_prompt_vibes()

if not markets:
    st.warning("No markets available to generate videos from.")
else:
    selected_question = st.selectbox("Choose a market to submit", [row["question"] for row in markets])
    selected_market = next(row for row in markets if row["question"] == selected_question)
    selected_vibe = st.selectbox("Choose a video vibe", vibes)

    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("Submit selected market"):
            st.session_state["single_video_result"] = submit_video(selected_market, vibe=selected_vibe)
            refresh_dashboard()
    with col_b:
        max_videos = st.slider("Run bridge for top N videos", min_value=1, max_value=5, value=2)
        if st.button("Run bridge"):
            st.session_state["bridge_results"] = run_bridge(max_videos=max_videos)
            refresh_dashboard()

if "single_video_result" in st.session_state:
    st.subheader("Single Submission Result")
    st.json(st.session_state["single_video_result"])

if "bridge_results" in st.session_state:
    st.subheader("Bridge Results")
    st.dataframe(st.session_state["bridge_results"], use_container_width=True, hide_index=True)


if __name__ == "__main__":
    print(st.session_state.get("single_video_result"))
