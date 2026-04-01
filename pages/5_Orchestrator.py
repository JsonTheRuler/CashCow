#!/usr/bin/env python3
"""Orchestrator page for the Cash Cow multipage dashboard."""

from __future__ import annotations

import streamlit as st

from orchestrator import run_once
from dashboard_shared import (
    get_last_plan_snapshot,
    get_pipeline_diagram,
    read_log_tail,
    refresh_dashboard,
    render_overview_metrics,
    render_shell,
)


st.set_page_config(page_title="Orchestrator | Cash Cow", page_icon="CC", layout="wide")
render_shell("Orchestrator", "Run and inspect the autonomous pipeline loop")
render_overview_metrics()

if st.button("Run one orchestrator cycle"):
    st.session_state["orchestrator_result"] = run_once()
    refresh_dashboard()

st.subheader("Execution Plan")
st.json(get_last_plan_snapshot())

if "orchestrator_result" in st.session_state:
    st.subheader("Latest Run Result")
    st.json(st.session_state["orchestrator_result"])

st.subheader("Pipeline Diagram")
st.code(get_pipeline_diagram(), language="mermaid")

st.subheader("Pipeline Log")
st.code(read_log_tail())


if __name__ == "__main__":
    print(get_last_plan_snapshot())
