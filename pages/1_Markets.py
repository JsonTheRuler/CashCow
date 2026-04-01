#!/usr/bin/env python3
"""Markets page for the Cash Cow multipage dashboard."""

from __future__ import annotations

import streamlit as st

from dashboard_shared import get_top_markets, render_overview_metrics, render_shell, score_market_preview


st.set_page_config(page_title="Markets | Cash Cow", page_icon="CC", layout="wide")
render_shell("Markets", "Trending prediction markets ranked by Cash Cow score")
render_overview_metrics()

markets = get_top_markets(15)
if not markets:
    st.warning("No markets are available from the scorer right now.")
else:
    st.dataframe(
        [
            {
                "rank": row["rank"],
                "question": row["question"],
                "yes_pct": row["yes_pct"],
                "no_pct": row["no_pct"],
                "volume_24h": row["volume_24h"],
                "score": row["score"],
            }
            for row in markets
        ],
        use_container_width=True,
        hide_index=True,
    )

    selected_question = st.selectbox("Inspect a market", [row["question"] for row in markets])
    selected_market = next(row for row in markets if row["question"] == selected_question)
    scored = score_market_preview(selected_market["raw_polymarket"])

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Cash Cow score", f"{scored['score']:.2f}")
    c2.metric("YES", f"{scored['yes_pct']:.1f}%")
    c3.metric("NO", f"{scored['no_pct']:.1f}%")
    c4.metric("24h volume", f"${scored['volume_24h']:,.0f}")

    st.subheader("Score Breakdown")
    st.dataframe(
        [{"factor": key, "value": value} for key, value in scored.get("score_breakdown", {}).items()],
        use_container_width=True,
        hide_index=True,
    )

    with st.expander("Description and raw market payload"):
        st.write(selected_market.get("description", ""))
        st.json(selected_market.get("raw_polymarket", {}))


if __name__ == "__main__":
    print(f"Loaded {len(markets)} markets")
