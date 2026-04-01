#!/usr/bin/env python3
"""Market forecaster page for the Cash Cow multipage dashboard."""

from __future__ import annotations

import streamlit as st

from forecaster import linear_forecast
from dashboard_shared import get_forecast_snapshot, get_top_markets, render_overview_metrics, render_shell


st.set_page_config(page_title="Market Forecaster | Cash Cow", page_icon="CC", layout="wide")
render_shell("Market Forecaster", "Project market direction and a bounded short-term trend")
render_overview_metrics()

markets = get_top_markets(12)
if not markets:
    st.warning("No scored markets available for forecasting.")
else:
    selected_question = st.selectbox("Choose a market to forecast", [row["question"] for row in markets])
    selected_market = next(row for row in markets if row["question"] == selected_question)
    forecast = get_forecast_snapshot(str(selected_market["id"]))
    raw = selected_market.get("raw_polymarket", {})
    current_prob = float(selected_market["yes_pct"]) / 100.0

    one_day_change = raw.get("oneDayPriceChange") if isinstance(raw, dict) else None
    try:
        day_delta = float(one_day_change or 0.0)
    except (TypeError, ValueError):
        day_delta = 0.0

    recent_history = [
        max(0.01, min(0.99, current_prob - (day_delta * 0.60))),
        max(0.01, min(0.99, current_prob - (day_delta * 0.30))),
        max(0.01, min(0.99, current_prob - (day_delta * 0.15))),
        max(0.01, min(0.99, current_prob - (day_delta * 0.05))),
        current_prob,
    ]
    projected = linear_forecast(recent_history, steps=6)

    c1, c2, c3 = st.columns(3)
    c1.metric("Direction", str(forecast.get("direction", "unknown")).upper())
    c2.metric("Confidence", f"{float(forecast.get('confidence', 0.0)):.2f}")
    c3.metric("Current YES", f"{selected_market['yes_pct']:.1f}%")

    st.subheader("Forecast Snapshot")
    st.json(forecast)

    st.subheader("Synthetic Probability Path")
    st.line_chart({"recent": recent_history, "forecast": projected})


if __name__ == "__main__":
    print(len(markets))
