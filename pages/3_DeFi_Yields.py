#!/usr/bin/env python3
"""DeFi yield page for the Cash Cow multipage dashboard."""

from __future__ import annotations

import streamlit as st

from dashboard_shared import get_defi_summary, render_overview_metrics, render_shell


st.set_page_config(page_title="DeFi Yields | Cash Cow", page_icon="CC", layout="wide")
render_shell("DeFi Yields", "Stablecoin opportunities ranked by APY and TVL")
render_overview_metrics()

summary = get_defi_summary(12)
pools = summary.get("pools", [])

c1, c2, c3 = st.columns(3)
c1.metric("Pools", str(summary.get("count", 0)))
c2.metric("Average APY", f"{summary.get('avg_apy', 0.0):.2f}%")
c3.metric("Total TVL", f"${summary.get('total_tvl_usd', 0.0):,.0f}")

if pools:
    st.dataframe(pools, use_container_width=True, hide_index=True)
    best = summary.get("best_pool") or {}
    st.subheader("Best Pool")
    st.write(
        f"{best.get('project', 'Unknown')} on {best.get('chain', 'Unknown')} offers "
        f"{best.get('apy', 0.0):.2f}% APY with ${best.get('tvl_usd', 0.0):,.0f} TVL."
    )
else:
    st.warning("No DeFi yield pools are available right now.")


if __name__ == "__main__":
    print(summary)
