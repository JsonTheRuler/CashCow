"""
Unified Data Layer with TTL caching for Cash Cow.

Fetches from Polymarket CLOB, DeFi Llama, local state files,
and MoneyPrinterTurbo. All calls have 5s timeouts and graceful
fallback to sample data.
"""

from __future__ import annotations

import json
import logging
import math
import time
from pathlib import Path
from typing import Any, TypedDict

import httpx

from app.extractor import extract_tickers as _extract_tickers_impl

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

LOG_DIR = Path.home() / "cashcow" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

_log_formatter = logging.Formatter(
    "%(asctime)s | %(levelname)-7s | %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
)
_file_handler = logging.FileHandler(LOG_DIR / "api.log", encoding="utf-8")
_file_handler.setFormatter(_log_formatter)

logger = logging.getLogger("cashcow.data")
logger.setLevel(logging.INFO)
logger.addHandler(_file_handler)

# ---------------------------------------------------------------------------
# Type definitions
# ---------------------------------------------------------------------------


class MarketItem(TypedDict):
    question: str
    yes_pct: float
    no_pct: float
    volume: float
    score: float
    priority: str
    suggested_vibe: str
    tickers: list[str]


class YieldItem(TypedDict):
    project: str
    chain: str
    symbol: str
    apy: float
    tvl: float
    score: float


class SignalItem(TypedDict):
    ticker: str
    signal: str
    confidence: float
    summary: str


# ---------------------------------------------------------------------------
# In-memory TTL cache
# ---------------------------------------------------------------------------

_cache: dict[str, tuple[float, Any]] = {}


def _cache_get(key: str, ttl_seconds: float) -> Any | None:
    """Return cached value if still fresh, else None."""
    entry = _cache.get(key)
    if entry is None:
        return None
    ts, value = entry
    if time.time() - ts > ttl_seconds:
        return None
    return value


def _cache_set(key: str, value: Any) -> None:
    _cache[key] = (time.time(), value)


def cache_invalidate(key: str | None = None) -> None:
    """Clear one key or the entire cache."""
    if key is None:
        _cache.clear()
    else:
        _cache.pop(key, None)


# ---------------------------------------------------------------------------
# HTTP client (shared, with 5s timeout)
# ---------------------------------------------------------------------------

_HTTP_TIMEOUT = 5.0


def _http_client() -> httpx.Client:
    return httpx.Client(timeout=_HTTP_TIMEOUT, follow_redirects=True)


# ---------------------------------------------------------------------------
# Sample / fallback data
# ---------------------------------------------------------------------------

SAMPLE_MARKETS: list[MarketItem] = [
    {
        "question": "Will Bitcoin hit $100k by July 2026?",
        "yes_pct": 62.0,
        "no_pct": 38.0,
        "volume": 4_500_000.0,
        "score": 88.5,
        "priority": "HIGH",
        "suggested_vibe": "hype",
        "tickers": ["BTC"],
    },
    {
        "question": "Will the Fed cut rates in Q2 2026?",
        "yes_pct": 55.0,
        "no_pct": 45.0,
        "volume": 2_100_000.0,
        "score": 72.3,
        "priority": "MEDIUM",
        "suggested_vibe": "analytical",
        "tickers": ["SPY", "TLT"],
    },
    {
        "question": "Will Ethereum flip Bitcoin market cap by 2027?",
        "yes_pct": 18.0,
        "no_pct": 82.0,
        "volume": 1_800_000.0,
        "score": 65.1,
        "priority": "MEDIUM",
        "suggested_vibe": "contrarian",
        "tickers": ["ETH", "BTC"],
    },
]

SAMPLE_YIELDS: list[YieldItem] = [
    {"project": "Aave", "chain": "Ethereum", "symbol": "USDC", "apy": 5.2, "tvl": 1_200_000_000.0, "score": 91.0},
    {"project": "Lido", "chain": "Ethereum", "symbol": "stETH", "apy": 3.8, "tvl": 9_800_000_000.0, "score": 87.5},
    {"project": "Compound", "chain": "Ethereum", "symbol": "DAI", "apy": 4.1, "tvl": 800_000_000.0, "score": 78.2},
]

SAMPLE_SIGNALS: list[SignalItem] = [
    {"ticker": "BTC", "signal": "BUY", "confidence": 0.82, "summary": "Strong momentum with institutional inflows."},
    {"ticker": "ETH", "signal": "HOLD", "confidence": 0.65, "summary": "Consolidation phase post-Dencun upgrade."},
    {"ticker": "SOL", "signal": "BUY", "confidence": 0.74, "summary": "DeFi TVL growth accelerating on Solana."},
]

# ---------------------------------------------------------------------------
# Scoring helpers
# ---------------------------------------------------------------------------


def _score_market(yes_pct: float, volume: float) -> tuple[float, str, str]:
    """
    Score a prediction market by controversy (closeness to 50/50) and volume.

    Returns (score, priority, suggested_vibe).
    """
    controversy = 1.0 - abs(yes_pct - 50.0) / 50.0  # 1.0 = perfectly split
    vol_norm = min(volume / 5_000_000.0, 1.0)  # cap at 5M
    score = round((controversy * 60.0 + vol_norm * 40.0), 1)

    if score >= 75:
        priority = "HIGH"
    elif score >= 50:
        priority = "MEDIUM"
    else:
        priority = "LOW"

    if yes_pct > 70:
        vibe = "hype"
    elif yes_pct < 30:
        vibe = "contrarian"
    elif controversy > 0.8:
        vibe = "debate"
    else:
        vibe = "analytical"

    return score, priority, vibe


def _score_yield(apy: float, tvl: float) -> float:
    """
    Score a DeFi yield pool.  Balances APY attractiveness with TVL safety.
    """
    apy_norm = min(apy / 20.0, 1.0)
    tvl_norm = min(math.log10(max(tvl, 1.0)) / 11.0, 1.0)  # log10(100B)=11
    return round(apy_norm * 50.0 + tvl_norm * 50.0, 1)


# ---------------------------------------------------------------------------
# Polymarket fetcher
# ---------------------------------------------------------------------------

_POLYMARKET_CLOB_URL = "https://clob.polymarket.com/markets"
_POLYMARKET_CACHE_TTL = 30.0  # seconds


def fetch_markets(force_refresh: bool = False) -> list[MarketItem]:
    """
    Fetch trending Polymarket markets, score and rank them.
    Cached for 30 seconds.
    """
    if not force_refresh:
        cached = _cache_get("markets", _POLYMARKET_CACHE_TTL)
        if cached is not None:
            return cached  # type: ignore[return-value]

    t0 = time.time()
    try:
        with _http_client() as client:
            resp = client.get(_POLYMARKET_CLOB_URL, params={"limit": 50, "order": "volume", "ascending": "false"})
            resp.raise_for_status()
            raw: list[dict[str, Any]] = resp.json()

        markets: list[MarketItem] = []
        for m in raw:
            question: str = m.get("question", m.get("description", "Unknown"))
            tokens: list[dict[str, Any]] = m.get("tokens", [])

            yes_pct = 50.0
            no_pct = 50.0
            if len(tokens) >= 2:
                yes_pct = round(float(tokens[0].get("price", 0.5)) * 100, 1)
                no_pct = round(float(tokens[1].get("price", 0.5)) * 100, 1)
            elif len(tokens) == 1:
                yes_pct = round(float(tokens[0].get("price", 0.5)) * 100, 1)
                no_pct = round(100.0 - yes_pct, 1)

            volume = float(m.get("volume", 0) or 0)
            score, priority, vibe = _score_market(yes_pct, volume)

            tickers: list[str] = _extract_tickers(question)

            markets.append(
                MarketItem(
                    question=question,
                    yes_pct=yes_pct,
                    no_pct=no_pct,
                    volume=volume,
                    score=score,
                    priority=priority,
                    suggested_vibe=vibe,
                    tickers=tickers,
                )
            )

        markets.sort(key=lambda x: x["score"], reverse=True)
        elapsed = round(time.time() - t0, 3)
        logger.info("fetch_markets OK | %d items | %.3fs", len(markets), elapsed)
        _cache_set("markets", markets)
        return markets

    except Exception as exc:
        elapsed = round(time.time() - t0, 3)
        logger.warning("fetch_markets FALLBACK (%s) | %.3fs", exc, elapsed)
        _cache_set("markets", SAMPLE_MARKETS)
        return list(SAMPLE_MARKETS)


def _extract_tickers(text: str) -> list[str]:
    """Extract tickers using the dedicated extractor module."""
    result = _extract_tickers_impl(text)
    return list(result.tickers)


# ---------------------------------------------------------------------------
# DeFi Llama fetcher
# ---------------------------------------------------------------------------

_DEFI_LLAMA_URL = "https://yields.llama.fi/pools"
_DEFI_LLAMA_CACHE_TTL = 300.0  # 5 minutes


def fetch_yields(force_refresh: bool = False, top_n: int = 10) -> list[YieldItem]:
    """
    Fetch DeFi Llama yield pools, score and return top N.
    Cached for 5 minutes.
    """
    if not force_refresh:
        cached = _cache_get("yields", _DEFI_LLAMA_CACHE_TTL)
        if cached is not None:
            return cached[:top_n]  # type: ignore[return-value]

    t0 = time.time()
    try:
        with _http_client() as client:
            resp = client.get(_DEFI_LLAMA_URL)
            resp.raise_for_status()
            payload: dict[str, Any] = resp.json()

        raw_pools: list[dict[str, Any]] = payload.get("data", [])

        # Filter: stablecoin-friendly, TVL > $1M, APY > 0
        pools: list[YieldItem] = []
        for p in raw_pools:
            apy = float(p.get("apy", 0) or 0)
            tvl = float(p.get("tvlUsd", 0) or 0)
            if apy <= 0 or tvl < 1_000_000:
                continue

            score = _score_yield(apy, tvl)
            pools.append(
                YieldItem(
                    project=str(p.get("project", "Unknown")),
                    chain=str(p.get("chain", "Unknown")),
                    symbol=str(p.get("symbol", "?")),
                    apy=round(apy, 2),
                    tvl=round(tvl, 2),
                    score=score,
                )
            )

        pools.sort(key=lambda x: x["score"], reverse=True)
        elapsed = round(time.time() - t0, 3)
        logger.info("fetch_yields OK | %d pools (filtered) | %.3fs", len(pools), elapsed)
        _cache_set("yields", pools)
        return pools[:top_n]

    except Exception as exc:
        elapsed = round(time.time() - t0, 3)
        logger.warning("fetch_yields FALLBACK (%s) | %.3fs", exc, elapsed)
        _cache_set("yields", SAMPLE_YIELDS)
        return list(SAMPLE_YIELDS)[:top_n]


# ---------------------------------------------------------------------------
# TradingAgents signals (state.json)
# ---------------------------------------------------------------------------

_STATE_PATH = Path.home() / "cashcow" / "state.json"


def fetch_signals() -> list[SignalItem]:
    """Read TradingAgents signals from state.json, fallback to samples."""
    t0 = time.time()
    try:
        if not _STATE_PATH.exists():
            logger.info("fetch_signals: state.json not found, using samples")
            return list(SAMPLE_SIGNALS)

        raw = json.loads(_STATE_PATH.read_text(encoding="utf-8"))
        signals: list[SignalItem] = []

        raw_signals = raw if isinstance(raw, list) else raw.get("signals", [])
        for s in raw_signals:
            signals.append(
                SignalItem(
                    ticker=str(s.get("ticker", "?")),
                    signal=str(s.get("signal", "HOLD")),
                    confidence=float(s.get("confidence", 0.5)),
                    summary=str(s.get("summary", "")),
                )
            )

        elapsed = round(time.time() - t0, 3)
        logger.info("fetch_signals OK | %d signals | %.3fs", len(signals), elapsed)
        return signals if signals else list(SAMPLE_SIGNALS)

    except Exception as exc:
        elapsed = round(time.time() - t0, 3)
        logger.warning("fetch_signals FALLBACK (%s) | %.3fs", exc, elapsed)
        return list(SAMPLE_SIGNALS)


# ---------------------------------------------------------------------------
# MoneyPrinterTurbo interaction
# ---------------------------------------------------------------------------

_TURBO_BASE = "http://localhost:8080"


def generate_video_script(
    topic: str,
    vibe: str = "engaging",
    yes_pct: float = 50.0,
    no_pct: float = 50.0,
    volume: float = 0.0,
) -> str:
    """
    Generate a short-form video script using the prompts module.

    Maps vibes to dedicated script templates in ``app.prompts``.
    Falls back to a generic template when prompts import fails.
    """
    try:
        from app.prompts import breaking_news, countdown, deep_analysis, hot_take, explainer

        vibe_map = {
            "hype": lambda: breaking_news(topic, yes_pct, volume, "Smart money is moving fast."),
            "contrarian": lambda: hot_take(topic, yes_pct, volume),
            "analytical": lambda: deep_analysis(topic, yes_pct, no_pct, volume, "trending up"),
            "debate": lambda: countdown(topic, yes_pct, "TBD", volume),
            "engaging": lambda: explainer(topic, yes_pct, "A prediction market everyone is watching."),
        }
        generator = vibe_map.get(vibe, vibe_map["engaging"])
        return generator()

    except Exception:
        # Fallback if prompts module is unavailable
        return (
            f"Here's something you need to know about {topic}.\n\n"
            f"The prediction markets are pricing this in real time, "
            f"and smart money is paying attention.\n\n"
            f"Follow for more alpha. #crypto #predictions #defi"
        )


def submit_to_turbo(topic: str, script: str) -> dict[str, Any]:
    """
    Forward a video script to MoneyPrinterTurbo at localhost:8080.
    Returns task info or a mock response if Turbo is unreachable.
    """
    t0 = time.time()
    payload = {
        "video_subject": topic,
        "video_script": script,
        "video_language": "en",
    }

    try:
        with _http_client() as client:
            resp = client.post(f"{_TURBO_BASE}/api/v1/videos", json=payload)
            resp.raise_for_status()
            result = resp.json()
        elapsed = round(time.time() - t0, 3)
        logger.info("submit_to_turbo OK | %.3fs", elapsed)
        return {
            "task_id": result.get("task_id", "unknown"),
            "status": "submitted",
            "topic": topic,
            "script": script,
        }

    except Exception as exc:
        elapsed = round(time.time() - t0, 3)
        logger.warning("submit_to_turbo MOCK (%s) | %.3fs", exc, elapsed)
        return {
            "task_id": f"mock-{int(time.time())}",
            "status": "mock_queued",
            "topic": topic,
            "script": script,
            "note": "MoneyPrinterTurbo unavailable — script generated but video not submitted.",
        }


def fetch_turbo_status() -> dict[str, Any]:
    """Check if MoneyPrinterTurbo is reachable."""
    try:
        with _http_client() as client:
            resp = client.get(f"{_TURBO_BASE}/api/v1/health", timeout=2.0)
            resp.raise_for_status()
            return {"status": "online", "detail": resp.json()}
    except Exception:
        return {"status": "offline"}


# ---------------------------------------------------------------------------
# Convenience: fetch everything for the dashboard
# ---------------------------------------------------------------------------


def fetch_all_dashboard_data() -> dict[str, Any]:
    """Return all data sources in one call."""
    return {
        "markets": fetch_markets(),
        "yields": fetch_yields(),
        "signals": fetch_signals(),
        "videos": [],  # populated by API layer if needed
        "pipeline_status": {
            "turbo": fetch_turbo_status(),
        },
    }


# ---------------------------------------------------------------------------
# CLI test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import pprint

    print("=== Markets ===")
    pprint.pprint(fetch_markets()[:3])

    print("\n=== Yields ===")
    pprint.pprint(fetch_yields(top_n=3))

    print("\n=== Signals ===")
    pprint.pprint(fetch_signals())

    print("\n=== Turbo Status ===")
    pprint.pprint(fetch_turbo_status())

    print("\n=== Script Generation ===")
    script = generate_video_script("Bitcoin to $100k?", "hype")
    print(script)
