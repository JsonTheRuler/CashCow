#!/usr/bin/env python3
"""Cash Cow Streamlit multipage dashboard home screen."""

from __future__ import annotations

import streamlit as st

from dashboard_shared import (
    get_defi_summary,
    get_market_analytics,
    load_state,
    render_overview_metrics,
    render_shell,
)


def main() -> None:
    """Render the multipage dashboard overview."""
    st.set_page_config(page_title="Cash Cow Dashboard", page_icon="CC", layout="wide")
    render_shell("Cash Cow", "Autonomous Market Intelligence Engine")
    render_overview_metrics()

    analytics = get_market_analytics(20)
    defi = get_defi_summary(8)
    state = load_state()

    left, right = st.columns((1.3, 1.0))
    with left:
        st.subheader("What The Engine Sees Right Now")
        top_markets = analytics.get("top_markets", [])
        if top_markets:
            st.dataframe(top_markets, use_container_width=True, hide_index=True)
        else:
            st.info("No market preview is available yet.")

        st.subheader("Pipeline Snapshot")
        st.json(
            {
                "pipeline_status": state.get("pipeline_status", "unknown"),
                "last_orchestrator_run": state.get("last_orchestrator_run"),
                "last_pipeline_trigger": state.get("last_pipeline_trigger"),
                "detected_tickers": state.get("detected_tickers", []),
            }
        )

    with right:
        st.subheader("Navigation")
        st.markdown(
            """
            Use the sidebar to open the eight dedicated pages:

            - Markets
            - Signals
            - DeFi Yields
            - Videos
            - Orchestrator
            - Social Intelligence
            - Content Studio
            - Market Forecaster
            """
        )
        best_pool = defi.get("best_pool") or {}
        st.subheader("Best Yield Right Now")
        if best_pool:
            st.metric("Top APY", f"{best_pool.get('apy', 0.0):.2f}%")
            st.write(
                f"{best_pool.get('project', 'Unknown')} on {best_pool.get('chain', 'Unknown')} "
                f"for {best_pool.get('symbol', 'N/A')}"
            )
        else:
            st.info("No DeFi yield data available right now.")

        st.subheader("Analytics Summary")
        a1, a2, a3 = st.columns(3)
        a1.metric("Markets analyzed", str(analytics.get("markets_analyzed", 0)))
        a2.metric("24h volume", f"${analytics.get('total_volume_24h', 0.0):,.0f}")
        a3.metric("Avg YES", f"{analytics.get('avg_yes_pct', 0.0):.1f}%")


if __name__ == "__main__":
    main()
