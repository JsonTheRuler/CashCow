"""Cash Cow unified REST API — port 8090. Run: uvicorn api:app --host 0.0.0.0 --port 8090"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

import requests
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

import alpha_signals
import defi_pipeline
import forecaster
import market_analytics
import orchestrator
import prompts
import scorer
import sentiment
import trading_signal

app = FastAPI(
    title="Cash Cow API",
    version="0.5.0",
    description="REST API for Polymarket, DeFi, signals, divergences, Cash Cow Alpha copy-trade signals, video generation, and orchestration.",
    docs_url="/docs",
    redoc_url="/redoc",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_cache: dict[str, tuple[Any, datetime]] = {}
MPT_BASE = os.getenv("MONEYPRINTERTURBO_API_URL", "http://127.0.0.1:8080").rstrip("/")
ROOT = Path(__file__).resolve().parent
STATE_PATH = ROOT / "state.json"
LOGS_DIR = ROOT / "logs"

# --- Copy-trade click analytics (in-memory + optional JSONL) ---
_copy_click_total: int = 0
_copy_click_by_market: dict[str, int] = {}


def _record_copy_click(market_id: str | None, source: str) -> None:
    global _copy_click_total
    _copy_click_total += 1
    key = market_id or "_unknown"
    _copy_click_by_market[key] = _copy_click_by_market.get(key, 0) + 1
    try:
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        line_obj = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "market_id": market_id,
            "source": source,
        }
        (LOGS_DIR / "copy_trade_clicks.jsonl").open("a", encoding="utf-8").write(
            json.dumps(line_obj, ensure_ascii=False) + "\n"
        )
    except OSError:
        pass


def cached(key: str, ttl_seconds: int, fn: Callable[[], Any]) -> Any:
    now = datetime.now(timezone.utc)
    if key in _cache:
        data, ts = _cache[key]
        if now - ts < timedelta(seconds=ttl_seconds):
            return data
    result = fn()
    _cache[key] = (result, now)
    return result


def _load_state() -> dict[str, Any]:
    if not STATE_PATH.exists():
        return {"pipeline_status": "stopped", "signals": [], "detected_tickers": []}
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"pipeline_status": "unknown", "signals": [], "detected_tickers": []}


def _read_pipeline_log(max_bytes: int = 16000) -> str:
    for name in ("pipeline.log", "cash_cow.log"):
        p = LOGS_DIR / name
        if p.exists():
            try:
                raw = p.read_bytes()
                if len(raw) > max_bytes:
                    raw = raw[-max_bytes:]
                return raw.decode("utf-8", errors="replace")
            except OSError:
                pass
    return ""


def _probe_get(url: str, timeout: float = 4.0) -> bool:
    try:
        r = requests.get(url, timeout=timeout)
        return r.status_code < 500
    except requests.RequestException:
        return False


class GenerateBody(BaseModel):
    market_index: int = Field(0, ge=0, description="Index into ranked markets (0 = top)")
    vibe: str = Field("breaking_news", description="Video vibe for script generation")


class RunCycleBody(BaseModel):
    max_videos: int = Field(2, ge=1, le=10, description="Markets to send to MoneyPrinterTurbo per cycle")


class CopyClickBody(BaseModel):
    market_id: str | None = Field(None, description="Polymarket / scorer market id")
    source: str = Field("dashboard", description="dashboard | video | api")


def _pick_market(body: GenerateBody) -> dict[str, Any]:
    ranked = scorer.top_markets(max(15, body.market_index + 1))
    if not ranked:
        raise HTTPException(status_code=503, detail="No markets available from Polymarket")
    if body.market_index >= len(ranked):
        raise HTTPException(status_code=400, detail="market_index out of range")
    return ranked[body.market_index]


# --- 1. Health ---
@app.get("/api/v1/health", tags=["health"])
def health() -> dict[str, Any]:
    poly_ok = _probe_get("https://gamma-api.polymarket.com/markets?limit=1&active=true", timeout=6.0)
    llama_ok = False
    for u in ("https://yields.llama.fi/pools", "https://api.llama.fi/pools"):
        if _probe_get(u, timeout=8.0):
            llama_ok = True
            break
    mpt_ok = _probe_get(f"{MPT_BASE}/", timeout=2.0) or _probe_get(f"{MPT_BASE}/api/v1/tasks", timeout=2.0)
    return {
        "status": "ok",
        "services": {
            "polymarket_gamma": "up" if poly_ok else "down",
            "defillama_yields": "up" if llama_ok else "down",
            "moneyprinterturbo": "up" if mpt_ok else "down",
        },
        "moneyprinter_base": MPT_BASE,
    }


# --- 2. Markets ---
@app.get("/api/v1/markets", tags=["markets"])
def api_markets(n: int = Query(10, ge=1, le=40)) -> dict[str, Any]:
    markets = cached(f"markets_{n}", 25, lambda: scorer.top_markets(n))
    return {"count": len(markets), "markets": markets}


# --- 3. Yields ---
@app.get("/api/v1/yields", tags=["defi"])
def api_yields() -> dict[str, Any]:
    pools = cached("yields_top", 30, defi_pipeline.get_top_yield_pools)
    return {"count": len(pools), "pools": pools}


# --- 4. Signals ---
@app.get("/api/v1/signals/{ticker}", tags=["signals"])
def api_signal(ticker: str) -> dict[str, Any]:
    return trading_signal.get_signal(ticker)


# --- 5. Analytics ---
@app.get("/api/v1/analytics", tags=["analytics"])
def api_analytics() -> dict[str, Any]:
    return cached("analytics", 30, lambda: market_analytics.full_analytics(25))


# --- 6. Forecast ---
@app.get("/api/v1/forecast/{token_id}", tags=["forecast"])
def api_forecast(token_id: str) -> dict[str, Any]:
    return forecaster.forecast_market(token_id)


# --- 7. Divergences ---
@app.get("/api/v1/divergences", tags=["sentiment"])
def api_divergences(limit: int = Query(12, ge=1, le=50)) -> dict[str, Any]:
    rows = cached(f"divergences_{limit}", 20, lambda: sentiment.get_top_divergences(limit))
    return {"count": len(rows), "divergences": rows}


@app.get("/api/v1/alpha-signals", tags=["alpha"])
def api_alpha_signals(limit: int = Query(10, ge=1, le=20)) -> dict[str, Any]:
    """Divergence-triggered **Cash Cow Alpha Signal** rows (educational copy-trade framing)."""
    markets = scorer.top_markets(15)
    signals = alpha_signals.list_alpha_copy_signals(markets, limit=limit)
    return {
        "product": alpha_signals.PRODUCT_NAME,
        "count": len(signals),
        "signals": signals,
        "x_follow_url": alpha_signals.X_FOLLOW_URL,
        "x_display_name": alpha_signals.X_DISPLAY_NAME,
        "copy_click_total": _copy_click_total,
        "disclaimer": alpha_signals.DISCLAIMER_SHORT,
    }


@app.post("/api/v1/track-copy-click", tags=["alpha"])
def api_track_copy_click(body: CopyClickBody) -> dict[str, Any]:
    """Track 'Copy This Divergence' engagement (success metric: cumulative clicks)."""
    _record_copy_click(body.market_id, body.source)
    return {
        "ok": True,
        "copy_click_total": _copy_click_total,
        "by_market": dict(sorted(_copy_click_by_market.items(), key=lambda x: -x[1])[:20]),
    }


# --- 8. Generate (MPT) ---
@app.post("/api/v1/generate", tags=["video"])
def api_generate(body: GenerateBody) -> dict[str, Any]:
    pick = _pick_market(body)
    title = pick.get("question") or "Polymarket"
    yes = float(pick.get("yes_pct") or 50.0)
    no = float(pick.get("no_pct") or 50.0)
    vol = float(pick.get("volume_24h") or 0.0)
    desc = str(pick.get("description") or (pick.get("source_data") or {}).get("description") or title)

    script_bundle = prompts.generate_script(body.vibe, title, yes, no, vol, desc)
    video_subject = script_bundle["video_subject"]
    vid_desc = script_bundle.get("video_description") or video_subject

    payloads_to_try: list[tuple[str, dict[str, Any]]] = [
        (
            "mpt_from_script",
            {
                "video_subject": video_subject,
                "video_script": script_bundle.get("video_script") or "",
                "video_language": "en",
                "aspect": "9:16",
                "video_description": vid_desc[:8000],
                "metadata": {
                    "cash_cow_rank": pick.get("rank"),
                    "cash_cow_score": pick.get("cash_cow_score") or pick.get("score"),
                    "vibe": body.vibe,
                    "cash_cow_alpha_signal": script_bundle.get("alpha_signal"),
                    "video_description": vid_desc[:4000],
                },
            },
        ),
        (
            "mpt_legacy",
            {
                "video_subject": video_subject,
                "video_language": "en",
                "aspect": "9:16",
            },
        ),
    ]
    raw_pm = pick.get("raw_polymarket") or {}
    payloads_to_try.append(
        (
            "generic_topic",
            {
                "topic": title,
                "slug": raw_pm.get("slug"),
                "market_id": pick.get("id"),
                "source": "polymarket",
                "vibe": body.vibe,
            },
        )
    )

    urls = [
        f"{MPT_BASE}/api/v1/generate",
        f"{MPT_BASE}/api/v1/videos",
        f"{MPT_BASE}/videos",
    ]

    last_error = ""
    for url in urls:
        for label, payload in payloads_to_try:
            try:
                r = requests.post(url, json=payload, timeout=35)
                if r.status_code < 400:
                    try:
                        data = r.json()
                    except Exception:
                        data = {"raw": r.text[:800]}
                    tid = data.get("task_id") or data.get("id") or data.get("uuid") or data.get("taskId")
                    return {
                        "ok": True,
                        "task_id": tid,
                        "endpoint": url,
                        "payload_style": label,
                        "script": script_bundle,
                        "response": data,
                    }
                last_error = f"{url} [{label}]: HTTP {r.status_code} {r.text[:200]}"
            except requests.RequestException as e:
                last_error = str(e)
    raise HTTPException(status_code=502, detail=last_error or "MoneyPrinterTurbo unreachable")


# --- 9. Dashboard bundle (30s cache) ---
@app.get("/api/v1/dashboard", tags=["dashboard"])
def api_dashboard() -> dict[str, Any]:
    def _build() -> dict[str, Any]:
        markets = scorer.top_markets(12)
        yields_list = defi_pipeline.get_top_yield_pools()
        analytics = market_analytics.full_analytics(25)
        divergences = sentiment.get_top_divergences(12)
        state = _load_state()
        tasks: list[dict[str, Any]] = []
        for path in ("/api/v1/tasks", "/tasks"):
            try:
                r = requests.get(f"{MPT_BASE}{path}", timeout=4)
                if r.ok:
                    data = r.json()
                    if isinstance(data, list):
                        tasks = data
                    elif isinstance(data, dict):
                        for k in ("tasks", "data", "items"):
                            if isinstance(data.get(k), list):
                                tasks = data[k]
                                break
                    break
            except requests.RequestException:
                continue
        tickers: set[str] = set(state.get("detected_tickers") or [])
        for m in markets[:8]:
            q = m.get("question") or ""
            try:
                from extractors import extract_tickers

                for t in extract_tickers(q, allow_llm_fallback=False):
                    tickers.add(t)
            except Exception:
                pass
        alpha_list = alpha_signals.list_alpha_copy_signals(markets, limit=10)
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "markets": markets,
            "yields": yields_list,
            "analytics": analytics,
            "divergences": divergences,
            "alpha_signals": alpha_list,
            "alpha_product": alpha_signals.PRODUCT_NAME,
            "x_follow_url": alpha_signals.X_FOLLOW_URL,
            "x_display_name": alpha_signals.X_DISPLAY_NAME,
            "copy_click_total": _copy_click_total,
            "state": state,
            "suggested_tickers": sorted(tickers)[:12],
            "video_tasks": tasks[:20],
            "pipeline_log_tail": _read_pipeline_log(),
            "orchestrator_plan": orchestrator.get_last_plan(),
        }

    return cached("dashboard_bundle", 30, _build)


# --- 10. Preview script (no MPT) ---
@app.post("/api/v1/preview-script", tags=["video"])
def api_preview_script(body: GenerateBody) -> dict[str, Any]:
    pick = _pick_market(body)
    title = pick.get("question") or "Polymarket"
    yes = float(pick.get("yes_pct") or 50.0)
    no = float(pick.get("no_pct") or 50.0)
    vol = float(pick.get("volume_24h") or 0.0)
    desc = str(pick.get("description") or (pick.get("source_data") or {}).get("description") or title)
    script_bundle = prompts.generate_script(body.vibe, title, yes, no, vol, desc)
    return {
        "ok": True,
        "market_index": body.market_index,
        "market": {
            "id": pick.get("id"),
            "question": title,
            "rank": pick.get("rank"),
            "cash_cow_score": pick.get("cash_cow_score") or pick.get("score"),
        },
        "script": script_bundle,
    }


# --- 11. Run orchestrator cycle ---
@app.post("/api/v1/run-cycle", tags=["orchestrator"])
def api_run_cycle(body: RunCycleBody = RunCycleBody()) -> dict[str, Any]:
    try:
        result = orchestrator.run_once(max_videos=body.max_videos)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(e)) from e
    return {"ok": True, "result": result}


# --- 12. Persisted pipeline state ---
@app.get("/api/v1/state", tags=["state"])
def api_state() -> dict[str, Any]:
    return _load_state()


# --- 13. Orchestrator plan artifact ---
@app.get("/api/v1/orchestrator/plan", tags=["orchestrator"])
def api_orchestrator_plan() -> dict[str, Any]:
    return orchestrator.get_last_plan()


def main() -> None:
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8090)


if __name__ == "__main__":
    main()
