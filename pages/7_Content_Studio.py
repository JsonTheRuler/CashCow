#!/usr/bin/env python3
"""Content studio page for the Cash Cow multipage dashboard."""

from __future__ import annotations

import streamlit as st

from prompts import build_video_subject
from dashboard_shared import (
    get_prompt_vibes,
    get_top_markets,
    get_viral_hooks,
    render_overview_metrics,
    render_shell,
)


st.set_page_config(page_title="Content Studio | Cash Cow", page_icon="CC", layout="wide")
render_shell("Content Studio", "Turn market data into short-form video prompts")
render_overview_metrics()

markets = get_top_markets(10)
vibes = get_prompt_vibes()
hooks = get_viral_hooks()

if not markets:
    st.warning("No scored markets available for prompt generation.")
else:
    selected_question = st.selectbox("Choose a market", [row["question"] for row in markets])
    selected_market = next(row for row in markets if row["question"] == selected_question)
    selected_vibe = st.selectbox("Choose a prompt vibe", vibes)

    prompt_text = build_video_subject(
        selected_vibe,
        selected_market["question"],
        float(selected_market["yes_pct"]),
        float(selected_market["no_pct"]),
        float(selected_market["volume_24h"]),
        str(selected_market.get("description", "")),
    )

    st.subheader("MoneyPrinterTurbo video_subject")
    st.text_area("Prompt", value=prompt_text, height=260)

st.subheader("Hook Library")
st.dataframe([{"hook": hook} for hook in hooks], use_container_width=True, hide_index=True)


if __name__ == "__main__":
    print(len(hooks))
