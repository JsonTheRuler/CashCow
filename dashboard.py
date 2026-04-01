#!/usr/bin/env python3
"""Cash Cow Streamlit dashboard — flat root imports (no sys.path hacks)."""

from __future__ import annotations

import html
import json
import os
from pathlib import Path
from typing import Any

import requests
import streamlit as st

ROOT = Path(__file__).resolve().parent
STATE_PATH = ROOT / "state.json"
LOGS_DIR = ROOT / "logs"
MPT_BASE = os.getenv("MONEYPRINTERTURBO_API_URL", "http://127.0.0.1:8080").rstrip("/")


def inject_css() -> None:
    st.markdown(
        """
<style>
  .stApp { background: linear-gradient(180deg, #0d1117 0%, #0a0e14 100%); }
  section[data-testid="stSidebar"] { background-color: #111827; border-right: 1px solid #30363d; }
  .cc-metric-card {
    background: linear-gradient(145deg, #161b22 0%, #1c2430 100%);
    border: 1px solid #30363d;
    border-radius: 14px;
    padding: 1rem 1.15rem;
    margin-bottom: 0.75rem;
    box-shadow: 0 8px 24px rgba(0,0,0,0.25);
  }
  .cc-metric-card h4 { margin: 0 0 0.35rem 0; color: #e6edf3; font-size: 0.95rem; font-weight: 600; }
  .cc-score { font-size: 1.35rem; font-weight: 800; color: #58a6ff; }
  .cc-prob-track {
    height: 10px; border-radius: 6px; background: #21262d; overflow: hidden; margin: 0.5rem 0;
  }
  .cc-prob-fill { height: 100%; border-radius: 6px; transition: width 0.25s ease; }
  .cc-fill-high { background: linear-gradient(90deg, #238636, #3fb950); }
  .cc-fill-mid { background: linear-gradient(90deg, #9e6a03, #d29922); }
  .cc-fill-low { background: linear-gradient(90deg, #da3633, #f85149); }
  .cc-alert-card {
    background: #1a2332;
    border-left: 4px solid #a371f7;
    border-radius: 8px;
    padding: 0.85rem 1rem;
    margin-bottom: 0.65rem;
  }
  div[data-testid="stMetricValue"] { font-weight: 700; }
</style>
""",
        unsafe_allow_html=True,
    )


def load_state() -> dict[str, Any]:
    if not STATE_PATH.exists():
        return {"pipeline_status": "idle", "signals": [], "detected_tickers": []}
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"pipeline_status": "unknown", "signals": [], "detected_tickers": []}


def read_log_tail() -> str:
    for name in ("pipeline.log", "cash_cow.log"):
        path = LOGS_DIR / name
        if path.exists():
            try:
                return path.read_text(encoding="utf-8")[-8000:]
            except OSError:
                continue
    return "No logs yet."


def _prob_fill_class(yes_pct: float) -> str:
    if yes_pct > 60:
        return "cc-fill-high"
    if yes_pct < 40:
        return "cc-fill-low"
    return "cc-fill-mid"


def render_markets_tab() -> None:
    from prompts import generate_script
    from scorer import score_single, top_markets
    import sentiment

    markets = top_markets(10)
    st.subheader("Trending prediction markets")

    vibe = st.selectbox(
        "Video vibe (Quick Generate)",
        ["breaking_news", "explainer", "hot_take", "deep_analysis", "countdown"],
        index=0,
        key="quick_vibe",
    )

    c1, c2 = st.columns([1, 1])
    with c1:
        if st.button("Quick Generate — top scored market", type="primary", use_container_width=True):
            if not markets:
                st.warning("No markets available.")
            else:
                top = markets[0]
                q = str(top.get("question", ""))
                y = float(top.get("yes_pct", 50))
                n = float(top.get("no_pct", 50))
                v = float(top.get("volume_24h", 0))
                d = str(top.get("description", q))
                bundle = generate_script(vibe, q, y, n, v, d)
                st.session_state["quick_script_bundle"] = bundle
                st.session_state["quick_script_market"] = top
    with c2:
        if st.session_state.get("quick_script_bundle") and st.button(
            "Send script to MoneyPrinterTurbo", use_container_width=True
        ):
            bundle = st.session_state["quick_script_bundle"]
            payload = {
                "video_subject": bundle.get("video_subject", ""),
                "video_script": bundle.get("video_script") or "",
                "video_language": "en",
                "aspect": "9:16",
            }
            ok = False
            for ep in ("/api/v1/videos", "/api/v1/generate", "/videos"):
                try:
                    r = requests.post(f"{MPT_BASE}{ep}", json=payload, timeout=25)
                    if r.status_code < 400:
                        st.success(f"Queued via {ep}")
                        st.json(r.json() if r.content else {})
                        ok = True
                        break
                except requests.RequestException as e:
                    st.caption(str(e))
            if not ok:
                st.error("Could not reach MoneyPrinterTurbo — check :8080.")

    if st.session_state.get("quick_script_bundle"):
        b = st.session_state["quick_script_bundle"]
        with st.expander("Generated video script (video_subject)", expanded=True):
            st.text_area("Copy for MPT", value=b.get("video_subject", ""), height=220, key="script_copy")

    st.divider()
    st.markdown("#### Grok-style divergence alerts")
    st.caption("Loaded from `intel/divergence_alerts.json` (or demo seed).")
    for alert in sentiment.get_top_divergences(5):
        idx = alert.get("divergence_index", alert.get("score", "—"))
        soc = alert.get("social_sentiment", "")
        summ = html.escape(str(alert.get("summary", "")))
        implied = alert.get("market_yes_implied", "")
        soc_d = html.escape(str(soc).replace("_", " ")) if soc else ""
        idx_s = html.escape(str(idx))
        implied_bit = f" · market YES ~{implied}%" if implied != "" else ""
        st.markdown(
            f'<div class="cc-alert-card"><strong>Divergence {idx_s}</strong>'
            f"{' · ' + soc_d if soc else ''}"
            f"{implied_bit}<br/><span style='opacity:0.9'>{summ}</span></div>",
            unsafe_allow_html=True,
        )

    st.divider()
    if not markets:
        st.warning("No markets available from Polymarket right now.")
        return

    preview = score_single(markets[0]["raw_polymarket"])
    m1, m2, m3 = st.columns(3)
    m1.metric("Top market score", f"{preview['score']:.2f}")
    m2.metric("Markets shown", len(markets))
    m3.metric("Top social divergence (row #1)", sentiment.social_divergence_for_market(markets[0].get("question", "")))

    for row in markets:
        q = str(row.get("question", "—"))
        yes = float(row.get("yes_pct", 50))
        vol = float(row.get("volume_24h", 0))
        score = float(row.get("score") or row.get("cash_cow_score") or 0)
        div_label = sentiment.social_divergence_for_market(q)
        pct_w = max(0.0, min(100.0, yes))
        fill_cls = _prob_fill_class(yes)

        q_safe = html.escape(q)
        st.markdown(
            f'<div class="cc-metric-card">'
            f"<h4>{q_safe}</h4>"
            f'<div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:0.5rem;">'
            f'<span class="cc-score">Cash Cow {score:.1f}</span>'
            f"<span style='color:#8b949e'>YES <strong style='color:#e6edf3'>{yes:.1f}%</strong></span>"
            f"<span style='color:#79c0ff'><strong>Social Δ</strong> {div_label}</span>"
            f"</div>"
            f'<div class="cc-prob-track"><div class="cc-prob-fill {fill_cls}" style="width:{pct_w}%;"></div></div>'
            f"<span style='font-size:0.8rem;color:#8b949e'>24h vol ${vol:,.0f}</span>"
            f"</div>",
            unsafe_allow_html=True,
        )


def render_signals_tab() -> None:
    from trading_signal import get_signal

    state = load_state()
    tickers = state.get("detected_tickers") or ["BTC-USD", "SPY", "NVDA"]
    rows = [get_signal(str(ticker)) for ticker in tickers[:5]]
    st.subheader("Trading signals")
    st.dataframe(rows, use_container_width=True, hide_index=True)


def render_yields_tab() -> None:
    from defi_pipeline import get_defi_summary

    summary = get_defi_summary(limit=10)
    st.subheader("DeFi yield opportunities")
    c1, c2, c3 = st.columns(3)
    c1.metric("Pools", str(summary.get("count", 0)))
    c2.metric("Avg APY", f"{summary.get('avg_apy', 0.0):.2f}%")
    c3.metric("Total TVL", f"${summary.get('total_tvl_usd', 0.0):,.0f}")
    st.dataframe(summary.get("pools", []), use_container_width=True, hide_index=True)


def render_video_tab() -> None:
    from bridge import run_bridge, submit_video
    from scorer import top_markets

    st.subheader("Video generation")
    markets = top_markets(5)
    vibe_v = st.selectbox("Vibe for submit", ["breaking_news", "explainer", "hot_take"], key="vid_vibe")
    if markets and st.button("Submit top market to MoneyPrinterTurbo"):
        result = submit_video(markets[0], vibe=vibe_v)
        st.json(result)

    if st.button("Run bridge for 2 videos"):
        st.session_state["bridge_results"] = run_bridge(max_videos=2)

    if "bridge_results" in st.session_state:
        st.dataframe(st.session_state["bridge_results"], use_container_width=True, hide_index=True)


def render_orchestrator_tab() -> None:
    from orchestrator import get_last_plan, run_once

    st.subheader("Orchestrator")
    if st.button("Run one orchestrator cycle"):
        st.session_state["orchestrator_result"] = run_once()

    st.markdown("**Last plan**")
    st.json(get_last_plan())
    if "orchestrator_result" in st.session_state:
        st.markdown("**Latest run**")
        st.json(st.session_state["orchestrator_result"])

    st.markdown("**Pipeline log**")
    st.code(read_log_tail(), language="log")


def main() -> None:
    st.set_page_config(page_title="Cash Cow Dashboard", page_icon="🐄", layout="wide")
    inject_css()
    st.title("Cash Cow")
    st.caption("Autonomous market intelligence engine")

    state = load_state()
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Pipeline", str(state.get("pipeline_status", "unknown")).upper())
    with c2:
        st.metric("Detected tickers", len(state.get("detected_tickers", [])))
    with c3:
        st.metric("Signals", len(state.get("signals", [])))

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
