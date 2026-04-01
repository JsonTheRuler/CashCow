"""Cash Cow unified REST API — port 8090."""

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

import defi_pipeline
import forecaster
import market_analytics
import orchestrator
import scorer
import trading_signal

try:
    from prompts import build_video_subject
except ImportError:
    build_video_subject = None  # type: ignore[misc, assignment]

app = FastAPI(title="Cash Cow API", version="0.2.0", description="Unified backend for dashboard + integrations")
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
    vibe: str = Field("breaking_news", description="Video vibe for subject builder")


@app.get("/api/v1/health")
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


@app.get("/api/v1/markets")
def api_markets(n: int = Query(10, ge=1, le=40)) -> dict[str, Any]:
    markets = cached(f"markets_{n}", 25, lambda: scorer.top_markets(n))
    return {"count": len(markets), "markets": markets}


@app.get("/api/v1/yields")
def api_yields() -> dict[str, Any]:
    pools = cached("yields_top", 30, defi_pipeline.get_top_yield_pools)
    return {"count": len(pools), "pools": pools}


@app.get("/api/v1/signals/{ticker}")
def api_signal(ticker: str) -> dict[str, Any]:
    return trading_signal.get_signal(ticker)


@app.get("/api/v1/analytics")
def api_analytics() -> dict[str, Any]:
    return cached("analytics", 30, lambda: market_analytics.full_analytics(25))


@app.get("/api/v1/forecast/{token_id}")
def api_forecast(token_id: str) -> dict[str, Any]:
    return forecaster.forecast_market(token_id)


@app.get("/api/v1/orchestrator/plan")
def api_orchestrator_plan() -> dict[str, Any]:
    return orchestrator.get_last_plan()


@app.post("/api/v1/generate")
def api_generate(body: GenerateBody) -> dict[str, Any]:
    ranked = scorer.top_markets(max(15, body.market_index + 1))
    if not ranked:
        raise HTTPException(status_code=503, detail="No markets available from Polymarket")
    if body.market_index >= len(ranked):
        raise HTTPException(status_code=400, detail="market_index out of range")
    pick = ranked[body.market_index]
    sd = pick.get("source_data") or {}
    title = pick.get("question") or sd.get("question") or "Polymarket"
    yes = float(sd.get("yes_pct") or pick.get("yes_pct") or 50.0)
    no = float(sd.get("no_pct") or pick.get("no_pct") or 50.0)
    vol = float(sd.get("volume_24h") or pick.get("volume_24h") or 0.0)
    desc = str(sd.get("description") or "")

    payloads_to_try: list[tuple[str, dict[str, Any]]] = []

    if build_video_subject:
        try:
            video_subject = build_video_subject(
                body.vibe,
                title,
                yes,
                no,
                vol,
                desc or title,
            )
        except ValueError:
            video_subject = None
        if video_subject:
            payloads_to_try.append(
                (
                    "mpt_v1",
                    {
                        "video_subject": video_subject,
                        "video_language": "en",
                        "aspect": "9:16",
                        "metadata": {
                            "cash_cow_rank": pick.get("rank"),
                            "cash_cow_score": pick.get("cash_cow_score"),
                            "vibe": body.vibe,
                        },
                    },
                )
            )

    raw_pm = pick.get("raw_polymarket") or {}
    payloads_to_try.extend(
        [
            (
                "generic_videos",
                {
                    "topic": title,
                    "slug": raw_pm.get("slug"),
                    "market_id": pick.get("id"),
                    "source": "polymarket",
                    "vibe": body.vibe,
                },
            ),
            (
                "minimal",
                {"topic": title, "market_id": pick.get("id")},
            ),
        ]
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
                        "response": data,
                    }
                last_error = f"{url} [{label}]: HTTP {r.status_code} {r.text[:200]}"
            except requests.RequestException as e:
                last_error = str(e)
    raise HTTPException(status_code=502, detail=last_error or "MoneyPrinterTurbo unreachable")


@app.get("/api/v1/dashboard")
def api_dashboard() -> dict[str, Any]:
    def _build() -> dict[str, Any]:
        markets = scorer.top_markets(12)
        yields_list = defi_pipeline.get_top_yield_pools()
        analytics = market_analytics.full_analytics(25)
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
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "markets": markets,
            "yields": yields_list,
            "analytics": analytics,
            "state": state,
            "suggested_tickers": sorted(tickers)[:12],
            "video_tasks": tasks[:20],
            "pipeline_log_tail": _read_pipeline_log(),
            "orchestrator": orchestrator.get_last_plan(),
        }

    return cached("dashboard_bundle", 30, _build)


def main() -> None:
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8090)


if __name__ == "__main__":
    main()
