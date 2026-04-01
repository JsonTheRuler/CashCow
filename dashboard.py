#!/usr/bin/env python3
"""Cash Cow Streamlit dashboard — root imports only, no sys.path hacks."""

from __future__ import annotations

import html
import json
import os
from pathlib import Path
from typing import Any

import pandas as pd
import requests
import streamlit as st
import streamlit.components.v1 as components
from streamlit_autorefresh import st_autorefresh
from streamlit_option_menu import option_menu

ROOT = Path(__file__).resolve().parent
STATE_PATH = ROOT / "state.json"
LOGS_DIR = ROOT / "logs"
API_BASE = (os.getenv("CASH_COW_API_URL") or os.getenv("CASH_COW_API") or "http://127.0.0.1:8090").rstrip("/")
MPT_BASE = os.getenv("MONEYPRINTERTURBO_API_URL", "http://127.0.0.1:8080").rstrip("/")
HUB_URL = (os.getenv("CASH_COW_HUB_URL") or "http://127.0.0.1:3000").rstrip("/")
HUB_IFRAME_HEIGHT = int(os.getenv("CASH_COW_HUB_IFRAME_HEIGHT", "800"))

_NAV_OPTIONS: tuple[str, ...] = (
    "Hub",
    "Overview",
    "Polymarket",
    "TradingAgents signals",
    "DeFi yields",
    "Video factory",
    "Orchestrator",
    "API & docs",
)


def inject_css() -> None:
    st.markdown(
        """
<style>
  .stApp {
    background: linear-gradient(165deg, #0a0e14 0%, #0d1117 40%, #111827 100%);
    color: #e6edf3;
  }
  section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #111827 0%, #0d1117 100%);
    border-right: 1px solid #30363d;
  }
  .cc-metric-card {
    background: linear-gradient(145deg, #161b22 0%, #1c2430 100%);
    border: 1px solid #30363d;
    border-radius: 14px;
    padding: 1rem 1.15rem;
    margin-bottom: 0.75rem;
    box-shadow: 0 8px 28px rgba(0,0,0,0.35);
  }
  .cc-metric-card h4 { margin: 0 0 0.35rem 0; color: #e6edf3; font-size: 0.95rem; font-weight: 600; line-height: 1.35; }
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
  .cc-banner {
    background: linear-gradient(90deg, #1f2937 0%, #312e81 50%, #1e3a5f 100%);
    border: 1px solid #4c1d95;
    border-radius: 12px;
    padding: 1rem 1.25rem;
    margin-bottom: 1rem;
  }
  .cc-badge-buy {
    display: inline-block; padding: 0.2rem 0.65rem; border-radius: 999px;
    background: #238636; color: #fff; font-weight: 700; font-size: 0.85rem;
  }
  .cc-badge-sell {
    display: inline-block; padding: 0.2rem 0.65rem; border-radius: 999px;
    background: #da3633; color: #fff; font-weight: 700; font-size: 0.85rem;
  }
  .cc-badge-hold {
    display: inline-block; padding: 0.2rem 0.65rem; border-radius: 999px;
    background: #9e6a03; color: #fff; font-weight: 700; font-size: 0.85rem;
  }
  div[data-testid="stMetricValue"] { font-weight: 700; color: #58a6ff !important; }
  .health-dot { display: inline-block; width: 9px; height: 9px; border-radius: 50%; margin-right: 6px; vertical-align: middle; }
  .health-up { background: #3fb950; box-shadow: 0 0 6px #3fb95088; }
  .health-down { background: #f85149; }
  .cc-alpha-chip {
    display: inline-block;
    margin-right: 0.45rem;
    padding: 0.15rem 0.5rem;
    border-radius: 6px;
    font-size: 0.72rem;
    font-weight: 800;
    letter-spacing: 0.02em;
    color: #0a0e14;
    background: linear-gradient(90deg, #fbbf24, #f59e0b);
    vertical-align: middle;
  }
  .cc-page-shell {
    border: 1px solid #30363d;
    border-radius: 16px;
    padding: 1rem 1.15rem 1.25rem;
    margin-bottom: 1rem;
    background: linear-gradient(165deg, rgba(22,27,34,0.55) 0%, rgba(13,17,23,0.35) 100%);
    box-shadow: 0 12px 40px rgba(0,0,0,0.25);
  }
  .cc-page-shell h2, .cc-page-shell h3 { color: #fbbf24 !important; margin-top: 0; }
  .cc-kv { color: #8b949e; font-size: 0.88rem; line-height: 1.55; }
  .cc-kv code { color: #f59e0b; font-size: 0.85rem; }
  .main h1 { color: #fbbf24 !important; font-weight: 800 !important; }
  .main h2, .main h3 { color: #f59e0b !important; }
  div[data-testid="stMetricValue"] { color: #3fb950 !important; }
  div[data-testid="stMetricLabel"] { color: #8b949e !important; }
  div[data-testid="stExpander"] details {
    border: 1px solid #30363d !important;
    border-radius: 12px !important;
    background: #161b22 !important;
  }
  div[data-testid="stExpander"] summary { color: #fbbf24 !important; font-weight: 600 !important; }
  div[data-testid="stAlert"] {
    border-radius: 12px !important;
    border: 1px solid #30363d !important;
    background: #161b22 !important;
  }
  [data-testid="stDataFrame"] { border: 1px solid #30363d; border-radius: 12px; overflow: hidden; }
  .stButton > button[kind="primary"], button[data-testid="baseButton-primary"] {
    background: linear-gradient(90deg, #238636, #3fb950) !important;
    color: #fff !important;
    border: none !important;
    font-weight: 700 !important;
  }
  .stButton > button[kind="secondary"], button[data-testid="baseButton-secondary"] {
    border-color: #f59e0b !important;
    color: #fbbf24 !important;
  }
  div[data-baseweb="select"] > div {
    border-color: #30363d !important;
    background-color: #161b22 !important;
  }
  .stTextArea textarea, .stTextInput input {
    border-color: #30363d !important;
    background-color: #0d1117 !important;
    color: #e6edf3 !important;
  }
  .stCodeBlock { border: 1px solid #30363d !important; border-radius: 10px !important; }
</style>
""",
        unsafe_allow_html=True,
    )


@st.cache_data(ttl=20)
def fetch_api_health() -> dict[str, Any] | None:
    try:
        r = requests.get(f"{API_BASE}/api/v1/health", timeout=6)
        if r.ok:
            return r.json()
    except requests.RequestException:
        pass
    return None


@st.cache_data(ttl=10)
def fetch_alpha_signals_payload() -> dict[str, Any] | None:
    try:
        r = requests.get(f"{API_BASE}/api/v1/alpha-signals", timeout=8)
        if r.ok:
            return r.json()
    except requests.RequestException:
        pass
    return None


def track_copy_click(market_id: str | None, source: str) -> None:
    try:
        requests.post(
            f"{API_BASE}/api/v1/track-copy-click",
            json={"market_id": market_id, "source": source},
            timeout=8,
        )
    except requests.RequestException:
        pass


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
                return path.read_text(encoding="utf-8")[-12000:]
            except OSError:
                continue
    return "No logs yet."


def _prob_fill_class(yes_pct: float) -> str:
    if yes_pct > 60:
        return "cc-fill-high"
    if yes_pct < 40:
        return "cc-fill-low"
    return "cc-fill-mid"


def _preview_script_request(market_index: int, vibe: str) -> dict[str, Any] | None:
    try:
        r = requests.post(
            f"{API_BASE}/api/v1/preview-script",
            json={"market_index": market_index, "vibe": vibe},
            timeout=45,
        )
        if r.ok:
            return r.json()
        return {"ok": False, "error": r.text[:500], "status": r.status_code}
    except requests.RequestException as e:
        return None


def render_sidebar_health() -> None:
    st.markdown("**API health**")
    h = fetch_api_health()
    if h and h.get("services"):
        for name, stt in h["services"].items():
            cls = "health-up" if stt == "up" else "health-down"
            label = name.replace("_", " ")
            st.markdown(
                f'<span class="health-dot {cls}"></span>{label}: **{stt}**',
                unsafe_allow_html=True,
            )
        st.caption(f"Backend `{API_BASE}`")
    else:
        st.markdown('<span class="health-dot health-down"></span>API offline', unsafe_allow_html=True)
        st.caption("Start: `uvicorn api:app --host 0.0.0.0 --port 8090`")


def _pipeline_metrics_strip() -> None:
    state = load_state()
    c1, c2, c3 = st.columns(3)
    c1.metric("Pipeline", str(state.get("pipeline_status", "unknown")).upper())
    c2.metric("Tickers", len(state.get("detected_tickers", [])))
    c3.metric("Signals", len(state.get("signals", [])))


def render_hub_tab() -> None:
    """Embed the Vite React hub (port 3000) via iframe inside components.html."""
    st.subheader("Cash Cow Hub")
    st.caption(
        f"React shell at `{HUB_URL}` — run `cd hub && npm install && npm run dev`. "
        "Override with env `CASH_COW_HUB_URL`."
    )
    safe_url = html.escape(HUB_URL, quote=True)
    h = HUB_IFRAME_HEIGHT
    iframe_html = (
        f'<iframe src="{safe_url}" width="100%" height="{h}" '
        'style="border:none;border-radius:14px;background:#0a0e14;box-shadow:0 12px 48px rgba(0,0,0,0.45);" '
        'title="Cash Cow Hub" loading="lazy" referrerpolicy="no-referrer-when-downgrade"></iframe>'
    )
    components.html(iframe_html, height=h + 28, scrolling=True)


def render_overview_tab() -> None:
    state = load_state()
    st.subheader("Mission control")
    st.markdown(
        '<div class="cc-kv">Pipeline status, tickers, and signal counts at a glance — same branding as the '
        '<strong style="color:#3fb950;">Hub</strong> and <strong style="color:#fbbf24;">Alpha</strong> surfaces.</div>',
        unsafe_allow_html=True,
    )
    c1, c2, c3 = st.columns(3)
    c1.metric("Pipeline", str(state.get("pipeline_status", "unknown")).upper())
    c2.metric("Tickers", len(state.get("detected_tickers", [])))
    c3.metric("Signals", len(state.get("signals", [])))
    st.divider()
    st.markdown("#### Quick links")
    lc1, lc2, lc3 = st.columns(3)
    with lc1:
        st.link_button("Open API Swagger", f"{API_BASE}/docs", use_container_width=True)
    with lc2:
        st.link_button("Hub (dev server)", HUB_URL, use_container_width=True)
    with lc3:
        st.link_button("Polymarket", "https://polymarket.com", use_container_width=True)
    st.markdown(
        '<div class="cc-page-shell" style="margin-top:1rem;"><p class="cc-kv"><strong>Ports</strong> · API '
        "<code>8090</code> · Dashboard <code>8502</code> · Hub <code>3000</code> · MPT <code>8080</code></p></div>",
        unsafe_allow_html=True,
    )


def render_api_docs_tab() -> None:
    st.subheader("API and docs")
    st.markdown(
        '<div class="cc-kv">Unified FastAPI backend — gold accents in the UI map to primary actions; green for '
        "live health and positive deltas.</div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="cc-page-shell">'
        "<ul style='margin:0;padding-left:1.2rem;color:#8b949e;line-height:1.7;font-size:0.9rem;'>"
        "<li><code style='color:#f59e0b;'>GET</code> <strong>/api/v1/health</strong> — dependency status</li>"
        "<li><code style='color:#f59e0b;'>GET</code> <strong>/api/v1/dashboard</strong> — bundled dashboard payload</li>"
        "<li><code style='color:#f59e0b;'>GET</code> <strong>/api/v1/alpha-signals</strong> — Cash Cow Alpha rows</li>"
        "<li><code style='color:#f59e0b;'>POST</code> <strong>/api/v1/track-copy-click</strong> — engagement</li>"
        "<li><code style='color:#f59e0b;'>POST</code> <strong>/api/v1/preview-script</strong> — script bundle for video</li>"
        "</ul></div>",
        unsafe_allow_html=True,
    )
    st.link_button("Open interactive docs", f"{API_BASE}/docs", type="primary", use_container_width=False)


def render_sidebar_alpha() -> None:
    import alpha_signals

    st.markdown("**Cash Cow Alpha**")
    st.link_button(
        f"Follow {alpha_signals.X_DISPLAY_NAME} on X",
        alpha_signals.X_FOLLOW_URL,
        use_container_width=True,
    )
    pay = fetch_alpha_signals_payload()
    total = int(pay.get("copy_click_total", 0)) if pay else 0
    st.metric("Copy-div clicks (tracked)", total)
    st.caption(alpha_signals.DISCLAIMER_SHORT)


def render_polymarket_tab() -> None:
    import alpha_signals

    from prompts import generate_script
    from scorer import score_single, top_markets
    import sentiment

    markets = top_markets(10)
    vibe = st.selectbox(
        "Default vibe for Preview Script",
        ["breaking_news", "explainer", "hot_take", "deep_analysis", "countdown"],
        index=0,
        key="poly_vibe",
    )

    # Alert banner (top divergences)
    divs = sentiment.get_top_divergences(3)
    if divs:
        top = divs[0]
        idx = html.escape(str(top.get("divergence_index", top.get("score", "—"))))
        summ = html.escape(str(top.get("summary", "")))[:220]
        st.markdown(
            f'<div class="cc-banner"><strong style="color:#c4b5fd;">Social divergence watch</strong> — '
            f"Divergence <strong>{idx}</strong><br/><span style='opacity:0.92;font-size:0.9rem;'>{summ}</span></div>",
            unsafe_allow_html=True,
        )

    st.subheader("Polymarket (live)")
    if not markets:
        st.warning("No markets available from Polymarket right now.")
        return

    preview = score_single(markets[0]["raw_polymarket"])
    m1, m2, m3 = st.columns(3)
    m1.metric("Top market score", f"{preview['score']:.2f}")
    m2.metric("Rows", len(markets))
    m3.metric("Social Δ (top)", sentiment.social_divergence_for_market(markets[0].get("question", "")))

    alpha_rows = alpha_signals.list_alpha_copy_signals(markets, 10)
    alpha_ids = {
        str(r["market_id"])
        for r in alpha_rows
        if r.get("market_id") is not None and str(r["market_id"]).strip() != ""
    }

    st.divider()
    st.markdown(f"#### {alpha_signals.PRODUCT_NAME}")
    st.caption(
        "Divergence-triggered watchlist for paper / educational use — not financial advice. "
        "Bridge + API attach the same footer to generated video descriptions."
    )
    for j, s in enumerate(alpha_rows[:5]):
        soft = " · soft tier" if s.get("soft_tier") else ""
        label = (str(s.get("question") or "?")[:72] + "…") if len(str(s.get("question") or "")) > 72 else str(s.get("question") or "?")
        with st.expander(f"{label}{soft}", expanded=False):
            st.write(s.get("copy_frame", ""))
            if s.get("intel_summary"):
                st.caption(str(s.get("intel_summary")))
            div_d = s.get("divergence_display")
            if div_d:
                st.caption(f"Divergence: {div_d}")
            mid = str(s["market_id"]) if s.get("market_id") is not None else None
            ac1, ac2 = st.columns(2)
            with ac1:
                if st.button("Copy This Divergence", key=f"ctd_alpha_strip_{j}", use_container_width=True):
                    track_copy_click(mid, "dashboard_alpha_strip")
                    row_fb: dict[str, Any] = (
                        next((m for m in markets if str(m.get("id")) == mid), {}) if mid else {}
                    )
                    st.session_state[f"alpha_strip_url_{j}"] = s.get("polymarket_url") or alpha_signals.polymarket_link_for_market(
                        row_fb
                    )
            with ac2:
                pu = s.get("polymarket_url") or "https://polymarket.com"
                st.link_button("Open Polymarket", pu, use_container_width=True)
            if st.session_state.get(f"alpha_strip_url_{j}"):
                st.success("Click logged. Open the market when you are ready (paper only).")
                st.markdown(f"[Polymarket →]({st.session_state[f'alpha_strip_url_{j}']})")

    st.divider()
    st.markdown("#### Grok-style divergence alerts")
    for alert in sentiment.get_top_divergences(4):
        idx = alert.get("divergence_index", alert.get("score", "—"))
        soc = alert.get("social_sentiment", "")
        summ = html.escape(str(alert.get("summary", "")))
        implied = alert.get("market_yes_implied", "")
        soc_d = html.escape(str(soc).replace("_", " ")) if soc else ""
        idx_s = html.escape(str(idx))
        implied_bit = f" · market YES ~{implied}%" if implied != "" else ""
        st.markdown(
            f'<div class="cc-alert-card"><strong>Divergence {idx_s}</strong>'
            f"{' · ' + soc_d if soc else ''}{implied_bit}<br/><span style='opacity:0.9'>{summ}</span></div>",
            unsafe_allow_html=True,
        )

    st.divider()
    for i, row in enumerate(markets):
        q = str(row.get("question", "—"))
        yes = float(row.get("yes_pct", 50))
        vol = float(row.get("volume_24h", 0))
        score = float(row.get("score") or row.get("cash_cow_score") or 0)
        div_label = html.escape(str(sentiment.social_divergence_for_market(q)))
        pct_w = max(0.0, min(100.0, yes))
        fill_cls = _prob_fill_class(yes)
        q_safe = html.escape(q)
        mid_str = str(row.get("id")) if row.get("id") is not None else ""
        alpha_chip = (
            '<span class="cc-alpha-chip">Cash Cow Alpha</span>' if mid_str and mid_str in alpha_ids else ""
        )

        st.markdown(
            f'<div class="cc-metric-card">'
            f"<h4>{alpha_chip}{q_safe}</h4>"
            f'<div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:0.5rem;">'
            f'<span class="cc-score">Score {score:.1f}</span>'
            f"<span style='color:#8b949e'>YES <strong style='color:#e6edf3'>{yes:.1f}%</strong></span>"
            f"<span style='color:#79c0ff'><strong>Social Δ</strong> {div_label}</span>"
            f"</div>"
            f'<div class="cc-prob-track"><div class="cc-prob-fill {fill_cls}" style="width:{pct_w}%;"></div></div>'
            f"<span style='font-size:0.8rem;color:#8b949e'>24h vol ${vol:,.0f}</span>"
            f"</div>",
            unsafe_allow_html=True,
        )

        b1, b2, b3 = st.columns([1, 1, 1])
        with b1:
            if st.button("Preview Script", key=f"prev_{i}", use_container_width=True):
                api_res = _preview_script_request(i, vibe)
                if api_res and api_res.get("ok"):
                    st.session_state[f"preview_{i}"] = api_res.get("script", {})
                else:
                    top = markets[i]
                    bundle = generate_script(
                        vibe,
                        str(top.get("question", "")),
                        float(top.get("yes_pct", 50)),
                        float(top.get("no_pct", 50)),
                        float(top.get("volume_24h", 0)),
                        str(top.get("description", top.get("question", ""))),
                    )
                    st.session_state[f"preview_{i}"] = bundle
                    if api_res is not None and not api_res.get("ok"):
                        st.caption("API fallback — local `generate_script`")
        with b2:
            pid = mid_str if mid_str else f"idx{i}"
            if st.button("Copy This Divergence", key=f"ctd_row_{i}_{pid}", use_container_width=True):
                track_copy_click(mid_str or None, "dashboard_polymarket_row")
                st.session_state[f"ctd_url_{i}"] = alpha_signals.polymarket_link_for_market(row)
        with b3:
            pass

        if st.session_state.get(f"ctd_url_{i}"):
            st.markdown(f"[Open Polymarket →]({st.session_state[f'ctd_url_{i}']}) · click tracked (paper only)")

        if st.session_state.get(f"preview_{i}"):
            prev = st.session_state[f"preview_{i}"]
            with st.expander(f"Script preview · market #{i + 1}", expanded=False):
                st.text_area(
                    "video_subject",
                    value=prev.get("video_subject", ""),
                    height=160,
                    key=f"ta_{i}",
                )
                if prev.get("video_description"):
                    st.text_area(
                        "video_description (Cash Cow Alpha footer for Shorts / YT)",
                        value=prev.get("video_description", ""),
                        height=220,
                        key=f"vd_{i}",
                    )


def render_signals_tab() -> None:
    """TradingAgents signals with colored badges + confidence progress."""
    from trading_signal import get_signal

    st.subheader("TradingAgents signals")
    state = load_state()
    tickers = state.get("detected_tickers") or ["SPY", "NVDA", "BTC"]
    for t in tickers[:8]:
        sig = get_signal(str(t))
        raw = str(sig.get("signal", "HOLD")).upper()
        if raw in ("BUY", "OVERWEIGHT"):
            badge_html = '<span class="cc-badge-buy">BUY</span>'
        elif raw in ("SELL", "UNDERWEIGHT"):
            badge_html = '<span class="cc-badge-sell">SELL</span>'
        else:
            badge_html = '<span class="cc-badge-hold">HOLD</span>'
        conf = float(sig.get("confidence", 0) or 0)
        summ = html.escape(str(sig.get("summary", "")))[:280]
        t_esc = html.escape(str(t))
        c1, c2 = st.columns([3, 1])
        with c1:
            st.markdown(
                f"<div class='cc-metric-card'><strong style='font-size:1.1rem'>{t_esc}</strong> {badge_html}<br/>"
                f"<span style='color:#8b949e;font-size:0.88rem'>{summ}</span></div>",
                unsafe_allow_html=True,
            )
        with c2:
            st.progress(min(1.0, max(0.0, conf)), text=f"{conf*100:.0f}% conf")


def render_defi_tab() -> None:
    from defi_pipeline import get_defi_summary, get_top_yield_pools

    st.subheader("DeFi yields (live)")
    summary = get_defi_summary(limit=12)
    c1, c2, c3 = st.columns(3)
    c1.metric("Pools tracked", str(summary.get("count", 0)))
    c2.metric("Avg APY", f"{summary.get('avg_apy', 0.0):.2f}%")
    c3.metric("Aggregate TVL (USD)", f"${summary.get('total_tvl_usd', 0.0):,.0f}")

    pools = summary.get("pools") or get_top_yield_pools()
    if not pools:
        st.info("No yield rows returned.")
        return
    df = pd.DataFrame(pools)
    if "apy" in df.columns:
        apys = df["apy"].astype(float)
        lo, hi = float(apys.min()), float(apys.max())

        def _apy_style(v: Any) -> str:
            try:
                fv = float(v)
            except (TypeError, ValueError):
                return ""
            if hi <= lo:
                return "color: #8b949e"
            t = (fv - lo) / (hi - lo)
            g = int(120 + 135 * t)
            return f"color: rgb(56,{g},108); font-weight: 700"

        show_cols = [c for c in ("chain", "project", "symbol", "apy", "tvlUsd") if c in df.columns]
        if show_cols:
            sub = df[show_cols].copy()
            try:
                styler = sub.style.map(_apy_style, subset=["apy"] if "apy" in sub.columns else [])
                st.dataframe(styler, use_container_width=True, hide_index=True)
            except Exception:
                st.dataframe(sub, use_container_width=True, hide_index=True)
        else:
            st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.dataframe(df, use_container_width=True, hide_index=True)


def render_video_factory_tab() -> None:
    import alpha_signals

    from bridge import run_bridge, submit_video
    from scorer import top_markets

    st.subheader("Video factory")
    st.info(
        f"**{alpha_signals.PRODUCT_NAME}** — bridge payloads include `video_description` with X follow "
        f"({alpha_signals.X_DISPLAY_NAME}) + educational disclaimer for platform descriptions. "
        "Monetization (Whop / performance fee) is a later step."
    )
    markets = top_markets(6)
    vibe_v = st.selectbox(
        "Vibe",
        ["breaking_news", "explainer", "hot_take", "deep_analysis", "countdown"],
        key="vf_vibe",
    )
    if markets:
        if st.button("Submit top market to MoneyPrinterTurbo", use_container_width=True):
            st.json(submit_video(markets[0], vibe=vibe_v))
    st.divider()
    if st.button("Run bridge pipeline (2 videos)", type="primary", use_container_width=True):
        with st.spinner("Running bridge…"):
            st.session_state["bridge_results"] = run_bridge(max_videos=2)
        st.success("Bridge run finished.")
    if "bridge_results" in st.session_state:
        st.dataframe(st.session_state["bridge_results"], use_container_width=True, hide_index=True)


def render_orchestrator_tab() -> None:
    from orchestrator import get_last_plan, run_once

    st.subheader("Orchestrator")
    state = load_state()
    st.markdown("**Pipeline state**")
    st.json(
        {
            "pipeline_status": state.get("pipeline_status"),
            "detected_tickers": state.get("detected_tickers", []),
            "last_orchestrator_run": state.get("last_orchestrator_run"),
            "signals_count": len(state.get("signals") or []),
        }
    )
    if st.button("Run one orchestrator cycle", use_container_width=True):
        with st.spinner("Orchestrator running…"):
            st.session_state["orchestrator_result"] = run_once(max_videos=2)
    st.markdown("**Last plan**")
    st.json(get_last_plan())
    if "orchestrator_result" in st.session_state:
        st.markdown("**Latest run**")
        st.json(st.session_state["orchestrator_result"])
    st.markdown("**Pipeline log**")
    st.code(read_log_tail(), language="log")


def main() -> None:
    st.set_page_config(page_title="Cash Cow", page_icon="🐄", layout="wide")
    inject_css()
    # Periodic rerun so sidebar API health + copy-click totals stay current without manual refresh
    st_autorefresh(interval=20_000, key="cc_dashboard_autorefresh")

    with st.sidebar:
        st.markdown("### 🐄 Cash Cow")
        selected = option_menu(
            menu_title="Navigate",
            options=list(_NAV_OPTIONS),
            icons=[
                "house",
                "speedometer2",
                "graph-up",
                "cpu",
                "coin",
                "play-btn",
                "diagram-3",
                "plug",
            ],
            menu_icon="compass",
            default_index=0,
            styles={
                "container": {"padding": "0.25rem 0", "background-color": "transparent"},
                "icon": {"color": "#3fb950", "font-size": "1.05rem"},
                "nav-link": {
                    "font-size": "0.88rem",
                    "text-align": "left",
                    "margin": "2px 0",
                    "--hover-color": "#1c2430",
                },
                "nav-link-selected": {
                    "background": "linear-gradient(90deg, #92400e55, #312e81)",
                    "font-weight": 600,
                    "border-left": "3px solid #f59e0b",
                },
            },
        )
        st.caption("Live metrics: auto-refresh ~20s")
        st.divider()
        render_sidebar_health()
        st.divider()
        render_sidebar_alpha()
        st.divider()
        st.caption("Ports: API **8090** · Dashboard **8502** · MPT **8080**")

    st.title("Cash Cow")
    st.caption(
        f"**{selected}** — gold & pasture green ops console · Hub · Polymarket · DeFi · Signals · Video"
    )

    if selected == "Hub":
        render_hub_tab()
    elif selected == "Overview":
        render_overview_tab()
    elif selected == "Polymarket":
        _pipeline_metrics_strip()
        render_polymarket_tab()
    elif selected == "TradingAgents signals":
        _pipeline_metrics_strip()
        render_signals_tab()
    elif selected == "DeFi yields":
        _pipeline_metrics_strip()
        render_defi_tab()
    elif selected == "Video factory":
        _pipeline_metrics_strip()
        render_video_factory_tab()
    elif selected == "Orchestrator":
        _pipeline_metrics_strip()
        render_orchestrator_tab()
    elif selected == "API & docs":
        render_api_docs_tab()


if __name__ == "__main__":
    main()
