"""
TradingAgents web console: run multi-agent analysis from the browser and optionally log or route orders.

Start (from repo root, after `pip install ".[web]"`):
  uvicorn webapp.main:app --reload --host 127.0.0.1 --port 8765

Streaming: POST /api/run/stream (SSE) or WebSocket /ws/run — same events as CLI chunk flow.
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from tradingagents.default_config import DEFAULT_CONFIG

from webapp.execution import execute_decision, normalize_rating
from webapp.graph_runner import propagate_request
from webapp.schemas import RunRequest, RunResponse
from webapp.streaming import sse_json_dumps, start_stream_thread

STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI(
    title="TradingAgents Console",
    description="Multi-agent LLM analysis with SSE/WebSocket progress and broker hooks.",
    version="0.2.0",
)


def _provider_key_ok(provider: str) -> bool:
    p = provider.lower()
    if p == "openai":
        return bool(os.getenv("OPENAI_API_KEY"))
    if p == "google":
        return bool(os.getenv("GOOGLE_API_KEY"))
    if p == "anthropic":
        return bool(os.getenv("ANTHROPIC_API_KEY"))
    if p == "xai":
        return bool(os.getenv("XAI_API_KEY"))
    if p == "openrouter":
        return bool(os.getenv("OPENROUTER_API_KEY"))
    if p == "ollama":
        return True
    return False


def _results_dir() -> Path:
    return Path(
        os.getenv("TRADINGAGENTS_RESULTS_DIR", DEFAULT_CONFIG["results_dir"])
    ).resolve()


@app.get("/api/health")
def health() -> dict:
    return {
        "status": "ok",
        "openai": bool(os.getenv("OPENAI_API_KEY")),
        "google": bool(os.getenv("GOOGLE_API_KEY")),
        "anthropic": bool(os.getenv("ANTHROPIC_API_KEY")),
        "alpaca": bool(
            os.getenv("ALPACA_API_KEY_ID") or os.getenv("ALPACA_API_KEY")
        )
        and bool(os.getenv("ALPACA_API_SECRET_KEY") or os.getenv("ALPACA_SECRET_KEY")),
        "tradier": bool(os.getenv("TRADIER_ACCESS_TOKEN") and os.getenv("TRADIER_ACCOUNT_ID")),
        "webhook": bool(os.getenv("EXECUTION_WEBHOOK_URL", "").strip()),
    }


@app.post("/api/run", response_model=RunResponse)
def run_analysis(req: RunRequest) -> RunResponse:
    if not _provider_key_ok(req.llm_provider):
        raise HTTPException(
            status_code=400,
            detail=f"No API key found for provider '{req.llm_provider}'. Set the matching env var or use ollama.",
        )

    try:
        final_state, rating = propagate_request(req)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    full_decision = final_state.get("final_trade_decision") or ""
    fd = str(full_decision)
    excerpt = (fd[:8000] + "…") if len(fd) > 8000 else fd

    normalized = normalize_rating(str(rating).strip())
    execution = execute_decision(
        ticker=req.ticker.strip(),
        rating_raw=normalized,
        execution_mode=req.execution_mode,
        order_qty=req.order_qty,
        results_dir=_results_dir(),
        paper_trading=req.alpaca_paper,
    )

    return RunResponse(
        ok=True,
        ticker=req.ticker.strip(),
        analysis_date=req.analysis_date.strip(),
        rating=normalized,
        execution=execution,
        final_decision_excerpt=excerpt,
    )


@app.post("/api/run/stream")
async def run_analysis_stream(req: RunRequest) -> StreamingResponse:
    if not _provider_key_ok(req.llm_provider):
        raise HTTPException(
            status_code=400,
            detail=f"No API key found for provider '{req.llm_provider}'. Set the matching env var or use ollama.",
        )

    _, q = start_stream_thread(req)

    async def event_gen():
        while True:
            item = await asyncio.to_thread(q.get)
            if item is None:
                break
            kind, payload = item
            yield f"data: {sse_json_dumps({'type': kind, 'payload': payload})}\n\n"

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.websocket("/ws/run")
async def run_analysis_ws(ws: WebSocket) -> None:
    await ws.accept()
    try:
        raw = await ws.receive_json()
        req = RunRequest.model_validate(raw)
    except WebSocketDisconnect:
        return
    except Exception as e:
        try:
            await ws.send_json({"type": "error", "payload": f"Invalid request: {e}"})
        except Exception:
            pass
        await ws.close(code=4400)
        return

    if not _provider_key_ok(req.llm_provider):
        await ws.send_json(
            {
                "type": "error",
                "payload": f"No API key for provider '{req.llm_provider}'.",
            }
        )
        await ws.close(code=4401)
        return

    _, q = start_stream_thread(req)
    try:
        while True:
            item = await asyncio.to_thread(q.get)
            if item is None:
                break
            kind, payload = item
            await ws.send_json({"type": kind, "payload": payload})
    except WebSocketDisconnect:
        return


@app.get("/")
def index() -> FileResponse:
    index_path = STATIC_DIR / "index.html"
    if not index_path.is_file():
        raise HTTPException(status_code=404, detail="Missing webapp/static/index.html")
    return FileResponse(index_path)


if STATIC_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
