#!/usr/bin/env python3
"""Social intelligence page for the Cash Cow multipage dashboard."""

from __future__ import annotations

import streamlit as st

from sentiment import divergence_score
from dashboard_shared import get_market_analytics, get_social_divergences, render_overview_metrics, render_shell


st.set_page_config(page_title="Social Intelligence | Cash Cow", page_icon="CC", layout="wide")
render_shell("Social Intelligence", "Track sentiment divergence against market pricing")
render_overview_metrics()

rows = get_social_divergences()
analytics = get_market_analytics(20)

left, right = st.columns((1.2, 1.0))
with left:
    st.subheader("Divergence Board")
    st.dataframe(rows, use_container_width=True, hide_index=True)
with right:
    st.subheader("Market Category Mix")
    st.json(analytics.get("category_counts", {}))
    st.metric("Avg price nudge", str(analytics.get("momentum", {}).get("avg_price_nudge")))

query = st.text_input("Check a topic", value="BTC")
if query:
    st.subheader("Topic Snapshot")
    st.json(divergence_score(query))


if __name__ == "__main__":
    print(rows)
