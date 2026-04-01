#!/usr/bin/env python3
"""Shared helpers for the Cash Cow Streamlit multipage dashboard."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import streamlit as st

ROOT = Path(__file__).resolve().parent
STATE_PATH = ROOT / "state.json"
LOGS_DIR = ROOT / "logs"


@st.cache_data(ttl=120)
def load_state() -> dict[str, Any]:
    """Load the latest persisted pipeline state."""
    if not STATE_PATH.exists():
        return {"pipeline_status": "idle", "signals": [], "detected_tickers": []}
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"pipeline_status": "unknown", "signals": [], "detected_tickers": []}


@st.cache_data(ttl=30)
def read_log_tail(limit: int = 8000) -> str:
    """Return the most recent pipeline log text for observability pages."""
    for name in ("pipeline.log", "cash_cow.log"):
        path = LOGS_DIR / name
        if path.exists():
            try:
                return path.read_text(encoding="utf-8")[-limit:]
            except OSError:
                continue
    return "No logs yet."


@st.cache_data(ttl=120)
def get_top_markets(limit: int = 10) -> list[dict[str, Any]]:
    """Fetch the current top-scored markets for dashboard pages."""
    from scorer import top_markets

    return top_markets(limit)


@st.cache_data(ttl=120)
def get_defi_summary(limit: int = 10) -> dict[str, Any]:
    """Fetch DeFi summary data for the yields page."""
    from defi_pipeline import get_defi_summary as _get_defi_summary

    return _get_defi_summary(limit=limit)


@st.cache_data(ttl=120)
def get_market_analytics(limit: int = 25) -> dict[str, Any]:
    """Fetch aggregate market analytics for overview pages."""
    from market_analytics import full_analytics

    return full_analytics(limit)


@st.cache_data(ttl=120)
def get_social_divergences() -> list[dict[str, Any]]:
    """Fetch cached social divergence snapshots."""
    from sentiment import top_divergences

    return top_divergences()


@st.cache_data(ttl=120)
def get_prompt_vibes() -> list[str]:
    """Expose available prompt vibes from the content prompt module."""
    from prompts import PROMPT_BUILDERS

    return list(PROMPT_BUILDERS.keys())


@st.cache_data(ttl=120)
def get_viral_hooks() -> list[str]:
    """Expose the reusable hook library for prompt previews."""
    from prompts import VIRAL_HOOKS

    return VIRAL_HOOKS


@st.cache_data(ttl=120)
def score_market_preview(raw_market: dict[str, Any]) -> dict[str, Any]:
    """Score a single market for detail views."""
    from scorer import score_single

    return score_single(raw_market)


@st.cache_data(ttl=120)
def get_signal_snapshot(ticker: str) -> dict[str, Any]:
    """Fetch a ticker signal for the signals page."""
    from trading_signal import get_signal

    return get_signal(ticker)


@st.cache_data(ttl=120)
def get_forecast_snapshot(token_id: str) -> dict[str, Any]:
    """Fetch a forecast snapshot for the forecaster page."""
    from forecaster import forecast_market

    return forecast_market(token_id)


@st.cache_data(ttl=120)
def get_last_plan_snapshot() -> dict[str, Any]:
    """Fetch the last orchestrator plan."""
    from orchestrator import get_last_plan

    return get_last_plan()


@st.cache_data(ttl=120)
def get_pipeline_diagram() -> str:
    """Fetch the orchestrator pipeline diagram."""
    from orchestrator import pipeline_diagram_mermaid

    return pipeline_diagram_mermaid()


def refresh_dashboard() -> None:
    """Clear cache and trigger a rerun after state-changing actions."""
    st.cache_data.clear()
    st.rerun()


def render_shell(title: str, subtitle: str) -> None:
    """Render a consistent page heading."""
    st.title(title)
    st.caption(subtitle)


def render_overview_metrics() -> None:
    """Render the shared high-level pipeline metrics row."""
    state = load_state()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Pipeline", str(state.get("pipeline_status", "unknown")).upper())
    c2.metric("Detected tickers", str(len(state.get("detected_tickers", []))))
    c3.metric("Signals", str(len(state.get("signals", []))))
    c4.metric("Video runs", str(len(state.get("video_runs", []))))


if __name__ == "__main__":
    print({"state_exists": STATE_PATH.exists(), "logs_dir": str(LOGS_DIR)})
