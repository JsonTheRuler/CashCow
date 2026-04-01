"""
Cash Cow — FastAPI Unified REST API (port 8090).

Serves scored Polymarket markets, DeFi Llama yields,
TradingAgents signals, and forwards video scripts to
MoneyPrinterTurbo.
"""

from __future__ import annotations

import time
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.data import (
    MarketItem,
    SignalItem,
    YieldItem,
    fetch_all_dashboard_data,
    fetch_markets,
    fetch_signals,
    fetch_turbo_status,
    fetch_yields,
    generate_video_script,
    logger,
    submit_to_turbo,
)

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

_START_TIME = time.time()

app = FastAPI(
    title="Cash Cow API",
    description=(
        "Unified API for trending prediction markets, DeFi yields, "
        "trading signals, and AI video generation."
    ),
    version="0.1.0",
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

# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


class GenerateRequest(BaseModel):
    market_index: int = Field(..., ge=0, description="Index into the current markets list")
    vibe: str = Field(default="engaging", description="Video vibe: hype, contrarian, analytical, debate, engaging")


class GenerateResponse(BaseModel):
    task_id: str
    topic: str
    script: str
    status: str
    note: str | None = None


class StatusResponse(BaseModel):
    polymarket_api: str
    defi_api: str
    turbo: str
    uptime_seconds: float


class DashboardResponse(BaseModel):
    markets: list[dict[str, Any]]
    yields: list[dict[str, Any]]
    signals: list[dict[str, Any]]
    videos: list[dict[str, Any]]
    pipeline_status: dict[str, Any]


# ---------------------------------------------------------------------------
# Middleware: request timing logger
# ---------------------------------------------------------------------------


@app.middleware("http")
async def log_request_timing(request: Any, call_next: Any) -> Any:
    t0 = time.time()
    response = await call_next(request)
    elapsed = round(time.time() - t0, 3)
    logger.info(
        "%s %s | %d | %.3fs",
        request.method,
        request.url.path,
        response.status_code,
        elapsed,
    )
    return response


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.get("/api/v1/markets", response_model=list[MarketItem], tags=["Data"])
async def get_markets() -> list[MarketItem]:
    """Fetch trending Polymarket markets, scored and ranked."""
    return fetch_markets()


@app.get("/api/v1/yields", response_model=list[YieldItem], tags=["Data"])
async def get_yields() -> list[YieldItem]:
    """Fetch top DeFi Llama yield pools, scored and ranked."""
    return fetch_yields(top_n=10)


@app.get("/api/v1/signals", response_model=list[SignalItem], tags=["Data"])
async def get_signals() -> list[SignalItem]:
    """Return TradingAgents signals from state.json (or mock data)."""
    return fetch_signals()


@app.get("/api/v1/dashboard", response_model=DashboardResponse, tags=["Data"])
async def get_dashboard() -> dict[str, Any]:
    """Return ALL data sources in one call."""
    return fetch_all_dashboard_data()


@app.post("/api/v1/generate", response_model=GenerateResponse, tags=["Video"])
async def generate_video(req: GenerateRequest) -> dict[str, Any]:
    """
    Generate a video script for the market at the given index,
    then forward to MoneyPrinterTurbo (or return mock if Turbo is down).
    """
    markets = fetch_markets()
    if req.market_index >= len(markets):
        raise HTTPException(
            status_code=400,
            detail=f"market_index {req.market_index} out of range (have {len(markets)} markets)",
        )

    market = markets[req.market_index]
    topic = market["question"]
    script = generate_video_script(
        topic=topic,
        vibe=req.vibe,
        yes_pct=market["yes_pct"],
        no_pct=market["no_pct"],
        volume=market["volume"],
    )
    result = submit_to_turbo(topic, script)
    return result


@app.get("/api/v1/status", response_model=StatusResponse, tags=["Health"])
async def get_status() -> dict[str, Any]:
    """Pipeline health check."""
    turbo = fetch_turbo_status()

    # Quick connectivity probes for external APIs
    polymarket_ok = "ok"
    defi_ok = "ok"
    try:
        markets = fetch_markets()
        if not markets:
            polymarket_ok = "empty"
    except Exception:
        polymarket_ok = "error"

    try:
        yields = fetch_yields()
        if not yields:
            defi_ok = "empty"
    except Exception:
        defi_ok = "error"

    return {
        "polymarket_api": polymarket_ok,
        "defi_api": defi_ok,
        "turbo": turbo["status"],
        "uptime_seconds": round(time.time() - _START_TIME, 1),
    }


# ---------------------------------------------------------------------------
# Root redirect
# ---------------------------------------------------------------------------


@app.get("/", include_in_schema=False)
async def root() -> dict[str, str]:
    return {"message": "Cash Cow API — visit /docs for Swagger UI"}


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.api:app", host="0.0.0.0", port=8090, reload=True)
