#!/usr/bin/env python3
"""
Cash Cow — Streamlit dashboard (hackathon demo).

Run: streamlit run dashboard.py --server.port 8502
Install: pip install ".[dashboard]"
"""

from __future__ import annotations

import html
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st

try:
    from streamlit_autorefresh import st_autorefresh
except ImportError:
    st_autorefresh = None

ROOT = Path(__file__).resolve().parent
STATE_PATH = ROOT / "state.json"
LOGS_DIR = ROOT / "logs"
BRIDGE = ROOT / "bridge.py"
VIDEO_BASE = "http://127.0.0.1:8080"
POLY_URL = (
    "https://gamma-api.polymarket.com/markets"
    "?active=true&order=volume24hr&ascending=false&limit={limit}"
)
LLAMA_URLS = (
    "https://api.llama.fi/pools",
    "https://yields.llama.fi/pools",
)

SAMPLE_POLY = [
    {
        "question": "Demo: Will the dashboard load? (offline sample)",
        "outcomePrices": '["0.72", "0.28"]',
        "outcomes": '["Yes", "No"]',
        "volume24hr": 1250000.0,
        "liquidity": "500000.00",
        "slug": "demo-offline",
        "id": "sample-1",
        "endDate": "2026-12-31T00:00:00Z",
    }
]

SAMPLE_POOLS = pd.DataFrame(
    [
        {
            "project": "demo-aave",
            "chain": "Ethereum",
            "symbol": "USDC",
            "apy": 8.2,
            "tvlUsd": 5_000_000,
        },
        {
            "project": "demo-compound",
            "chain": "Arbitrum",
            "symbol": "USDT",
            "apy": 6.1,
            "tvlUsd": 3_200_000,
        },
    ]
)

SAMPLE_STATE = {
    "pipeline_status": "stopped",
    "signals": [
        {
            "ticker": "SPY",
            "rating": "HOLD",
            "summary": "Sample signal — add state.json from your orchestrator.",
        }
    ],
    "detected_tickers": ["SPY"],
}


def inject_css() -> None:
    st.markdown(
        """
<style>
  @keyframes cc-gradient {
    0% { background-position: 0% 50%; }
    50% { background-position: 100% 50%; }
    100% { background-position: 0% 50%; }
  }
  .cc-banner {
    background: linear-gradient(270deg, #1a3a2f, #0f2840, #2b1f4a, #1a3a2f);
    background-size: 800% 800%;
    animation: cc-gradient 12s ease infinite;
    padding: 1.25rem 1.5rem;
    border-radius: 12px;
    margin-bottom: 1.25rem;
    border: 1px solid rgba(255,255,255,0.12);
  }
  .cc-banner h1 {
    margin: 0;
    font-size: 1.65rem;
    font-weight: 700;
    color: #f0f4f8;
    letter-spacing: -0.02em;
  }
  .cc-banner p {
    margin: 0.35rem 0 0 0;
    color: rgba(240,244,248,0.75);
    font-size: 0.95rem;
  }
  .stApp {
    background-color: #0e1117;
  }
  section[data-testid="stSidebar"] {
    background-color: #161b22;
  }
  div[data-testid="stMetricValue"] {
    color: #58a6ff;
  }
</style>
""",
        unsafe_allow_html=True,
    )


def fetch_polymarket(limit: int) -> list[dict[str, Any]]:
    try:
        r = requests.get(POLY_URL.format(limit=limit), timeout=20)
        r.raise_for_status()
        data = r.json()
        if isinstance(data, list):
            return data
        return []
    except Exception:
        return list(SAMPLE_POLY)


def parse_outcomes(m: dict[str, Any]) -> tuple[list[str], list[float]]:
    try:
        labels = json.loads(m.get("outcomes") or '["Yes","No"]')
        prices = [float(x) for x in json.loads(m.get("outcomePrices") or "[0.5,0.5]")]
    except (json.JSONDecodeError, TypeError, ValueError):
        labels, prices = ["Yes", "No"], [0.5, 0.5]
    while len(prices) < len(labels):
        prices.append(0.0)
    return labels, prices


def market_card_color(yes_or_first: float) -> str:
    no_or_second = 1.0 - yes_or_first
    if yes_or_first > 0.7:
        return "#238636"
    if no_or_second > 0.7:
        return "#da3633"
    return "#d29922"


def fetch_defi_pools() -> pd.DataFrame:
    for url in LLAMA_URLS:
        try:
            r = requests.get(url, timeout=45)
            r.raise_for_status()
            body = r.json()
            rows = body.get("data") if isinstance(body, dict) else body
            if not isinstance(rows, list):
                continue
            df = pd.DataFrame(rows)
            if df.empty or "tvlUsd" not in df.columns:
                continue
            if "stablecoin" in df.columns:
                df = df[df["stablecoin"] == True]  # noqa: E712
            elif "symbol" in df.columns:
                sy = df["symbol"].astype(str).str.upper()
                df = df[sy.str.contains("USD|DAI|FRAX|GUSD|LUSD|USDT|USDC", regex=True, na=False)]
            df = df[df["tvlUsd"] > 1_000_000]
            if "apy" not in df.columns:
                continue
            df = df.sort_values("apy", ascending=False).head(10)
            return df[
                ["project", "chain", "symbol", "apy", "tvlUsd"]
            ].reset_index(drop=True)
        except Exception:
            continue
    return SAMPLE_POOLS.copy()


def load_state() -> dict[str, Any]:
    if not STATE_PATH.exists():
        return dict(SAMPLE_STATE)
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return dict(SAMPLE_STATE)


def fetch_video_tasks() -> list[dict[str, Any]]:
    try:
        r = requests.get(f"{VIDEO_BASE}/api/v1/tasks", timeout=5)
        r.raise_for_status()
        data = r.json()
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            for key in ("tasks", "data", "items"):
                if isinstance(data.get(key), list):
                    return data[key]
        return []
    except Exception:
        return []


def post_generate_video(market: dict[str, Any], aspect_ratio: str, voice: str) -> tuple[bool, str]:
    payload = {
        "topic": market.get("question", "Polymarket"),
        "slug": market.get("slug"),
        "market_id": market.get("id"),
        "source": "polymarket",
        "aspect_ratio": aspect_ratio,
        "voice": voice,
    }
    try:
        r = requests.post(
            f"{VIDEO_BASE}/api/v1/videos",
            json=payload,
            timeout=30,
        )
        if r.status_code < 400:
            return True, r.text[:500] or "OK"
        return False, f"HTTP {r.status_code}: {r.text[:300]}"
    except requests.RequestException as e:
        return False, str(e)


def read_pipeline_logs(max_bytes: int = 12000) -> str:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    log_file = LOGS_DIR / "pipeline.log"
    if not log_file.exists():
        return "(No pipeline.log yet — run the bridge or orchestrator.)\n"
    try:
        raw = log_file.read_bytes()
        if len(raw) > max_bytes:
            raw = raw[-max_bytes:]
        return raw.decode("utf-8", errors="replace")
    except OSError:
        return "(Could not read logs.)\n"


def rating_badge_color(rating: str) -> str:
    r = rating.upper()
    if r in ("BUY", "OVERWEIGHT"):
        return "🟢"
    if r in ("SELL", "UNDERWEIGHT"):
        return "🔴"
    return "🟡"


def main() -> None:
    st.set_page_config(
        page_title="Cash Cow — Autonomous Market Intelligence Engine",
        page_icon="🐄",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    inject_css()

    if st_autorefresh:
        st_autorefresh(interval=60 * 1000, key="cashcow_refresh")

    if "num_markets" not in st.session_state:
        st.session_state.num_markets = 10
    if "aspect_ratio" not in st.session_state:
        st.session_state.aspect_ratio = "9:16"
    if "voice" not in st.session_state:
        st.session_state.voice = "default"

    with st.sidebar:
        st.markdown("## 🐄 Cash Cow")
        st.caption("Autonomous market intelligence demo")
        st.divider()

        snap = load_state()
        pipe = snap.get("pipeline_status", "unknown")
        st.metric("Pipeline", "● Running" if pipe == "running" else "○ Idle")

        if st.button("Run Pipeline Now", type="primary", use_container_width=True):
            try:
                subprocess.run(
                    [sys.executable, str(BRIDGE)],
                    cwd=str(ROOT),
                    timeout=120,
                    check=False,
                )
                st.success("bridge.py finished — check logs.")
                time.sleep(0.3)
                st.rerun()
            except Exception as e:
                st.error(str(e))

        st.session_state.num_markets = st.slider(
            "Markets to show", 3, 15, int(st.session_state.num_markets)
        )
        st.session_state.aspect_ratio = st.selectbox(
            "Video aspect ratio",
            ["9:16", "16:9", "1:1"],
            index=["9:16", "16:9", "1:1"].index(st.session_state.aspect_ratio)
            if st.session_state.aspect_ratio in ["9:16", "16:9", "1:1"]
            else 0,
        )
        st.session_state.voice = st.selectbox(
            "Voice (passed to video API)",
            ["default", "male", "female", "neutral"],
        )

        st.divider()
        st.markdown(
            """
**Links**
- [Polymarket](https://polymarket.com)
- [DeFi Llama](https://defillama.com)
- [GitHub — CashCow](https://github.com/JsonTheRuler/CashCow)
"""
        )

    st.markdown(
        '<div class="cc-banner"><h1>🐄 Cash Cow</h1>'
        "<p>Autonomous Market Intelligence Engine — Polymarket · Video factory · TradingAgents · Yields</p></div>",
        unsafe_allow_html=True,
    )

    markets = fetch_polymarket(int(st.session_state.num_markets))
    pools_df = fetch_defi_pools()
    tasks = fetch_video_tasks()
    state = load_state()

    vol_sum = sum(float(m.get("volume24hr") or m.get("volume24hrClob") or 0) for m in markets)
    avg_apy = float(pools_df["apy"].mean()) if not pools_df.empty else 0.0
    done_videos = sum(
        1
        for t in tasks
        if str(t.get("status", "")).lower() in ("done", "completed", "success")
    )

    m1, m2, m3 = st.columns(3)
    m1.metric("24h volume (top markets)", f"${vol_sum/1e6:.1f}M" if vol_sum else "—")
    m2.metric("Avg APY (top stable pools)", f"{avg_apy:.2f}%")
    m3.metric("Videos completed (tasks API)", str(done_videos))

    st.subheader("🔥 Trending Prediction Markets")
    st.caption("Gamma API · auto-refresh every 60s when streamlit-autorefresh is installed")

    n_cols = 2
    for i in range(0, len(markets), n_cols):
        cols = st.columns(n_cols)
        for j, col in enumerate(cols):
            idx = i + j
            if idx >= len(markets):
                break
            m = markets[idx]
            labels, prices = parse_outcomes(m)
            first = prices[0] if prices else 0.5
            border = market_card_color(first)
            vol = float(m.get("volume24hr") or m.get("volume24hrClob") or 0)
            liq = m.get("liquidity") or m.get("liquidityNum") or "—"
            q = m.get("question", "—")
            q_safe = html.escape(str(q))

            with col:
                st.markdown(
                    f'<div style="border-left:4px solid {border};padding:0.75rem 1rem;'
                    "background:rgba(255,255,255,0.03);border-radius:8px;margin-bottom:0.75rem;\">"
                    f"<strong>{q_safe}</strong></div>",
                    unsafe_allow_html=True,
                )
                parts = []
                for li, pr in zip(labels, prices):
                    parts.append(f"{li}: **{pr*100:.1f}%**")
                st.markdown(" · ".join(parts))
                st.caption(f"24h vol: ${vol:,.0f} · liquidity: {liq}")
                key = f"gen_{m.get('id', m.get('slug', idx))}_{idx}"
                if st.button("Generate Video", key=key, use_container_width=True):
                    ok, msg = post_generate_video(
                        m,
                        st.session_state.aspect_ratio,
                        st.session_state.voice,
                    )
                    if ok:
                        st.success("Video job accepted.")
                    else:
                        st.warning(f"Video API: {msg}")

    st.divider()
    left, right = st.columns(2)

    with left:
        st.subheader("📊 Trading Signals")
        sigs = state.get("signals") or []
        tickers = state.get("detected_tickers") or []
        if tickers:
            st.caption("Tickers: " + ", ".join(str(t) for t in tickers))
        if not sigs:
            st.info("No signals in state.json — showing sample data.")
            sigs = SAMPLE_STATE["signals"]
        for s in sigs:
            r = str(s.get("rating", "HOLD")).upper()
            badge = rating_badge_color(r)
            st.markdown(f"{badge} **{s.get('ticker', '—')}** — `{r}`")
            st.write(s.get("summary", ""))

    with right:
        st.subheader("📈 Yield Opportunities")
        st.caption("DeFi Llama — stablecoin pools, TVL > $1M, top 10 by APY")
        if pools_df.empty:
            st.warning("Using placeholder pool data.")
        else:
            show = pools_df.copy()
            show["APY %"] = show["apy"].round(2)
            show["TVL"] = show["tvlUsd"].apply(lambda x: f"${x/1e6:.2f}M" if x >= 1e6 else f"${x:,.0f}")
            st.dataframe(
                show[["project", "chain", "symbol", "APY %", "TVL"]],
                use_container_width=True,
                hide_index=True,
            )
            fig = go.Figure(
                go.Bar(
                    x=show["symbol"].astype(str).tolist(),
                    y=show["apy"].tolist(),
                    marker_color="#58a6ff",
                )
            )
            fig.update_layout(
                template="plotly_dark",
                height=280,
                margin=dict(l=20, r=20, t=30, b=20),
                title="Top stablecoin yields (APY %)",
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
            )
            st.plotly_chart(fig, use_container_width=True)

    st.divider()
    st.subheader("🎬 Video Factory")
    v1, v2 = st.columns(2)
    with v1:
        st.markdown("**Active / queued tasks** (`GET /api/v1/tasks`)")
        if not tasks:
            st.caption("No tasks (MoneyPrinterTurbo not running on :8080 or empty queue).")
        else:
            st.json(tasks[:15])
    with v2:
        st.markdown("**Completed — download links**")
        completed = [
            t
            for t in tasks
            if str(t.get("status", "")).lower() in ("done", "completed", "success")
        ]
        if not completed:
            st.caption("Parse `output_url` / `file` / `download` from your API when available.")
        for t in completed[:10]:
            url = (
                t.get("output_url")
                or t.get("download_url")
                or t.get("url")
                or t.get("video_url")
            )
            name = t.get("title") or t.get("id") or "video"
            if url:
                st.markdown(f"- [{name}]({url})")
            else:
                st.write(t)

    st.divider()
    st.subheader("📜 Pipeline log")
    st.text(read_pipeline_logs())


if __name__ == "__main__":
    main()
