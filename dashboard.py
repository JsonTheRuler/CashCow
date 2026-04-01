#!/usr/bin/env python3
"""Cash Cow Streamlit dashboard wired to the flat-root project layout."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import streamlit as st

ROOT = Path(__file__).resolve().parent
STATE_PATH = ROOT / "state.json"
LOGS_DIR = ROOT / "logs"


def load_state() -> dict[str, Any]:
    """Load persisted state for the dashboard."""
    if not STATE_PATH.exists():
        return {"pipeline_status": "idle", "signals": [], "detected_tickers": []}
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"pipeline_status": "unknown", "signals": [], "detected_tickers": []}


def read_log_tail() -> str:
    """Return the most recent pipeline log text."""
    for name in ("pipeline.log", "cash_cow.log"):
        path = LOGS_DIR / name
        if path.exists():
            try:
                return path.read_text(encoding="utf-8")[-8000:]
            except OSError:
                continue
    return "No logs yet."


def render_markets_tab() -> None:
    """Render prediction markets and single-market scoring preview."""
    from scorer import score_single, top_markets

    markets = top_markets(10)
    st.subheader("Trending Prediction Markets")
    if not markets:
        st.warning("No markets available from Polymarket right now.")
        return

    preview = score_single(markets[0]["raw_polymarket"])
    st.metric("Top market score", f"{preview['score']:.2f}")
    st.dataframe(
        [
            {
                "rank": row["rank"],
                "question": row["question"],
                "yes_pct": row["yes_pct"],
                "volume_24h": row["volume_24h"],
                "score": row["score"],
            }
            for row in markets
        ],
        use_container_width=True,
        hide_index=True,
    )


def render_signals_tab() -> None:
    """Render trading signals derived from the current state or heuristics."""
    from trading_signal import get_signal

    state = load_state()
    tickers = state.get("detected_tickers") or ["BTC-USD", "SPY", "NVDA"]
    rows = [get_signal(str(ticker)) for ticker in tickers[:5]]
    st.subheader("Trading Signals")
    st.dataframe(rows, use_container_width=True, hide_index=True)


def render_yields_tab() -> None:
    """Render DeFi yield opportunities."""
    from defi_pipeline import get_defi_summary

    summary = get_defi_summary(limit=10)
    st.subheader("DeFi Yield Opportunities")
    c1, c2, c3 = st.columns(3)
    c1.metric("Pools", str(summary.get("count", 0)))
    c2.metric("Avg APY", f"{summary.get('avg_apy', 0.0):.2f}%")
    c3.metric("Total TVL", f"${summary.get('total_tvl_usd', 0.0):,.0f}")
    st.dataframe(summary.get("pools", []), use_container_width=True, hide_index=True)


def render_video_tab() -> None:
    """Render video submission controls and bridge results."""
    from bridge import run_bridge, submit_video
    from scorer import top_markets

    st.subheader("Video Generation")
    markets = top_markets(5)
    if markets and st.button("Submit Top Market to MoneyPrinterTurbo"):
        result = submit_video(markets[0])
        st.json(result)

    if st.button("Run Bridge for 2 Videos"):
        st.session_state["bridge_results"] = run_bridge(max_videos=2)

    if "bridge_results" in st.session_state:
        st.dataframe(st.session_state["bridge_results"], use_container_width=True, hide_index=True)


def render_orchestrator_tab() -> None:
    """Render orchestrator controls, plan state, and logs."""
    from orchestrator import get_last_plan, run_once

    st.subheader("Orchestrator")
    if st.button("Run One Orchestrator Cycle"):
        st.session_state["orchestrator_result"] = run_once()

    st.markdown("**Last plan**")
    st.json(get_last_plan())
    if "orchestrator_result" in st.session_state:
        st.markdown("**Latest run**")
        st.json(st.session_state["orchestrator_result"])

    st.markdown("**Pipeline log**")
    st.code(read_log_tail())


def main() -> None:
    """Launch the five-tab Streamlit dashboard."""
    st.set_page_config(page_title="Cash Cow Dashboard", page_icon="CC", layout="wide")
    st.title("Cash Cow")
    st.caption("Autonomous Market Intelligence Engine")

    state = load_state()
    c1, c2, c3 = st.columns(3)
    c1.metric("Pipeline", str(state.get("pipeline_status", "unknown")).upper())
    c2.metric("Detected tickers", str(len(state.get("detected_tickers", []))))
    c3.metric("Signals", str(len(state.get("signals", []))))

    tabs = st.tabs(["Markets", "Signals", "Yields", "Videos", "Orchestrator"])
    with tabs[0]:
        render_markets_tab()
    with tabs[1]:
        render_signals_tab()
    with tabs[2]:
        render_yields_tab()
    with tabs[3]:
        render_video_tab()
    with tabs[4]:
        render_orchestrator_tab()


if __name__ == "__main__":
    main()
