#!/usr/bin/env python3
"""Signals page for the Cash Cow multipage dashboard."""

from __future__ import annotations

import streamlit as st

from dashboard_shared import get_signal_snapshot, load_state, render_overview_metrics, render_shell


st.set_page_config(page_title="Signals | Cash Cow", page_icon="CC", layout="wide")
render_shell("Signals", "Trading-style signals derived from detected market tickers")
render_overview_metrics()

state = load_state()
default_tickers = state.get("detected_tickers") or ["BTC-USD", "SPY", "NVDA", "TSLA"]
rows = [get_signal_snapshot(str(ticker)) for ticker in default_tickers[:8]]

st.subheader("Current Signal Board")
st.dataframe(rows, use_container_width=True, hide_index=True)

manual_ticker = st.text_input("Run a manual signal", value=str(default_tickers[0]))
if manual_ticker:
    st.subheader("Manual Lookup")
    st.json(get_signal_snapshot(manual_ticker))

with st.expander("State-backed signals"):
    st.json(state.get("signals", []))


if __name__ == "__main__":
    print(rows)
