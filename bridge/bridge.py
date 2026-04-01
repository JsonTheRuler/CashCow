#!/usr/bin/env python3
"""Cash Cow Bridge: Polymarket trending -> MoneyPrinterTurbo video generation.

This module fetches trending prediction markets from Polymarket's Gamma API,
optionally fetches DeFi yield data from DeFi Llama, and triggers short-form
video generation via MoneyPrinterTurbo's REST API.

Usage:
    python -m bridge.bridge                  # Full pipeline
    python -m bridge.bridge --dry-run        # Fetch data, skip video gen
    python -m bridge.bridge --dry-run 5      # Fetch top 5 markets
"""
from __future__ import annotations

import json
import math
import os
import sys
from datetime import datetime
from typing import Any

import requests
from loguru import logger

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
GAMMA_API = "https://gamma-api.polymarket.com"
TURBO_API = "http://127.0.0.1:8080"
DEFI_YIELDS_API = "https://yields.llama.fi"
LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")

SAMPLE_MARKETS: list[dict[str, Any]] = [
    {
        "question": "Will Bitcoin exceed $100,000 by June 2026?",
        "outcomePrices": '["0.62","0.38"]',
        "volume24hr": "5200000",
        "liquidity": "1200000",
        "description": "This market resolves YES if Bitcoin price exceeds $100,000.",
        "endDate": "2026-06-30",
        "slug": "will-bitcoin-exceed-100k-june-2026",
    },
    {
        "question": "Will the Fed cut rates in Q2 2026?",
        "outcomePrices": '["0.45","0.55"]',
        "volume24hr": "3100000",
        "liquidity": "800000",
        "description": "Resolves YES if federal funds rate is cut.",
        "endDate": "2026-06-30",
        "slug": "fed-rate-cut-q2-2026",
    },
    {
        "question": "Will Ethereum flip Bitcoin in market cap by 2027?",
        "outcomePrices": '["0.08","0.92"]',
        "volume24hr": "1500000",
        "liquidity": "400000",
        "description": "Resolves YES if ETH market cap exceeds BTC market cap.",
        "endDate": "2027-01-01",
        "slug": "eth-flippening-2027",
    },
]


# ---------------------------------------------------------------------------
# Data fetching
# ---------------------------------------------------------------------------
def get_trending_markets(n: int = 5) -> list[dict[str, Any]]:
    """Fetch top N markets by 24h volume from Polymarket Gamma API.

    Args:
        n: Number of markets to return (default 5).

    Returns:
        List of market dicts from Polymarket, or sample data on failure.
    """
    try:
        r = requests.get(
            f"{GAMMA_API}/markets",
            params={
                "active": "true",
                "limit": n,
                "order": "volume24hr",
                "ascending": "false",
            },
            timeout=10,
        )
        r.raise_for_status()
        return r.json()
    except Exception as e:
        logger.warning(f"Polymarket API failed: {e}, using sample data")
        return SAMPLE_MARKETS[:n]


def get_market_detail(market: dict[str, Any]) -> dict[str, Any]:
    """Extract clean structured data from a raw Polymarket market object.

    Args:
        market: Raw market dict from Gamma API.

    Returns:
        Cleaned dict with question, yes/no percentages, volume, etc.
    """
    prices = json.loads(market.get("outcomePrices", "[]"))
    yes_pct = float(prices[0]) * 100 if prices and len(prices) > 0 else 0
    no_pct = float(prices[1]) * 100 if prices and len(prices) > 1 else 0
    return {
        "question": market.get("question", "Unknown"),
        "yes": round(yes_pct, 1),
        "no": round(no_pct, 1),
        "volume_24h": float(market.get("volume24hr", 0)),
        "liquidity": float(market.get("liquidity", 0)),
        "description": market.get("description", "")[:200],
        "end_date": market.get("endDate", ""),
        "slug": market.get("slug", ""),
    }


def score_market(detail: dict[str, Any]) -> float:
    """Score a market 0-100 using the Cash Cow scoring algorithm.

    Formula from CLAUDE.md:
        controversy = 100 - abs(yes_pct - 50) * 2
        volume_score = min(100, log10(max(volume, 1)) * 15)
        clarity = max(0, 100 - len(question))
        raw = controversy * 0.35 + volume_score * 0.30 + clarity * 0.15
        score = min(100, raw * time_pressure)

    Args:
        detail: Cleaned market dict from get_market_detail().

    Returns:
        Score between 0 and 100.
    """
    controversy = 100 - abs(detail["yes"] - 50) * 2
    volume_score = min(100, math.log10(max(detail["volume_24h"], 1)) * 15)
    clarity = max(0, 100 - len(detail["question"]))

    # Time pressure multiplier
    time_pressure = 1.0
    if detail.get("end_date"):
        try:
            end = datetime.fromisoformat(detail["end_date"].replace("Z", "+00:00"))
            days_left = (end - datetime.now(end.tzinfo)).days
            if days_left <= 7:
                time_pressure = 1.5
            elif days_left <= 30:
                time_pressure = 1.2
        except (ValueError, TypeError):
            pass

    raw = (controversy * 0.35) + (volume_score * 0.30) + (clarity * 0.15)
    return min(100, raw * time_pressure)


def market_to_video_topic(detail: dict[str, Any]) -> str:
    """Convert market data into an engaging video topic string.

    Args:
        detail: Cleaned market dict.

    Returns:
        Formatted topic string for MoneyPrinterTurbo.
    """
    return (
        f"{detail['question']} -- "
        f"Prediction markets currently price this at {detail['yes']}% YES. "
        f"${detail['volume_24h']:,.0f} has been traded in the last 24 hours. "
        f"Here's what you need to know."
    )


# ---------------------------------------------------------------------------
# MoneyPrinterTurbo integration
# ---------------------------------------------------------------------------
def generate_video(topic: str, aspect: str = "9:16") -> dict[str, Any]:
    """Trigger MoneyPrinterTurbo to generate a video from a topic.

    Args:
        topic: The video subject/topic string.
        aspect: Video aspect ratio (default 9:16 for shorts).

    Returns:
        Response dict from Turbo API with task_id.

    Raises:
        requests.RequestException: If the Turbo API call fails.
    """
    payload = {
        "video_subject": topic,
        "video_script": "",
        "video_terms": "",
        "video_aspect": aspect,
        "video_concat_mode": "random",
        "video_clip_duration": 5,
        "video_count": 1,
        "video_source": "pexels",
        "video_language": "en",
        "voice_name": "en-US-AndrewNeural",
        "voice_volume": 1.0,
        "voice_rate": 1.0,
        "bgm_type": "random",
        "bgm_volume": 0.2,
        "subtitle_enabled": True,
        "subtitle_position": "bottom",
        "font_name": "STHeitiMedium.ttc",
        "text_fore_color": "#FFFFFF",
        "font_size": 60,
        "stroke_color": "#000000",
        "stroke_width": 1.5,
        "n_threads": 2,
        "paragraph_number": 1,
    }
    r = requests.post(f"{TURBO_API}/api/v1/videos", json=payload, timeout=30)
    r.raise_for_status()
    return r.json()


def get_task_status(task_id: str) -> dict[str, Any]:
    """Check the status of a video generation task.

    Args:
        task_id: The task UUID from generate_video().

    Returns:
        Task status dict.
    """
    r = requests.get(f"{TURBO_API}/api/v1/tasks/{task_id}", timeout=10)
    r.raise_for_status()
    return r.json()


def get_all_tasks() -> dict[str, Any]:
    """Get all current video generation tasks from Turbo API."""
    r = requests.get(f"{TURBO_API}/api/v1/tasks", timeout=10)
    r.raise_for_status()
    return r.json()


# ---------------------------------------------------------------------------
# DeFi yields
# ---------------------------------------------------------------------------
def get_top_yields(n: int = 5) -> list[dict[str, Any]]:
    """Fetch top stablecoin yields from DeFi Llama.

    Args:
        n: Number of top yields to return.

    Returns:
        List of pool dicts sorted by APY, or empty list on failure.
    """
    try:
        r = requests.get(f"{DEFI_YIELDS_API}/pools", timeout=15)
        r.raise_for_status()
        pools = r.json().get("data", [])
        stable = [
            p
            for p in pools
            if p.get("stablecoin")
            and p.get("apy", 0) > 0
            and p.get("tvlUsd", 0) > 1_000_000
        ]
        return sorted(stable, key=lambda x: x["apy"], reverse=True)[:n]
    except Exception as e:
        logger.warning(f"DeFi Llama API failed: {e}")
        return []


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
def log_run(data: dict[str, Any]) -> str:
    """Log a pipeline run to the logs directory as JSON.

    Args:
        data: Run data dict to persist.

    Returns:
        Path to the log file.
    """
    os.makedirs(LOG_DIR, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(LOG_DIR, f"run_{ts}.json")
    with open(path, "w") as f:
        json.dump(data, f, indent=2, default=str)
    return path


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------
def run_pipeline(market_count: int = 3, generate: bool = True) -> dict[str, Any]:
    """Main Cash Cow pipeline: fetch markets, score them, generate videos.

    Args:
        market_count: How many trending markets to fetch.
        generate: Whether to actually trigger video generation.

    Returns:
        Dict with run data including markets, yields, and video tasks.
    """
    run_data: dict[str, Any] = {
        "timestamp": datetime.now().isoformat(),
        "markets": [],
        "insider_alerts": [],
        "yields": [],
        "videos": [],
    }

    print(f"\n{'='*60}")
    print(f"  CASH COW -- Pipeline Run @ {datetime.now().isoformat()}")
    print(f"{'='*60}\n")

    # 1. Fetch trending markets
    print("[1/3] Fetching trending Polymarket markets...")
    markets = get_trending_markets(market_count)
    details = [get_market_detail(m) for m in markets]

    # Score and sort
    for d in details:
        d["score"] = score_market(d)
    details.sort(key=lambda x: x["score"], reverse=True)

    for i, d in enumerate(details, 1):
        print(
            f"  #{i}: {d['question'][:65]} | "
            f"{d['yes']}% YES | ${d['volume_24h']:,.0f} vol | Score: {d['score']:.0f}"
        )
    run_data["markets"] = details

    # 1b. Insider activity scan
    print("\n[1b/4] Scanning for insider activity...")
    insider_hooks: dict[str, str] = {}  # slug -> video hook
    try:
        from insider.scanner import scan_market as _scan_market
        from insider.formatter import format_video_hook, format_state_entry

        for d, raw_m in zip(details, markets):
            cond_id = raw_m.get("conditionId", raw_m.get("condition_id", ""))
            if not cond_id:
                continue
            alerts = _scan_market(
                condition_id=cond_id,
                market_slug=d.get("slug", ""),
                market_question=d["question"],
                market_volume_24h=d["volume_24h"],
                trade_limit=20,
            )
            if alerts:
                best = max(alerts, key=lambda a: a.weighted_score)
                d["score"] = min(100, d["score"] + 25)  # insider boost
                d["insider_alert"] = True
                insider_hooks[d.get("slug", "")] = format_video_hook(best)
                run_data["insider_alerts"].append(format_state_entry(best))
                print(
                    f"  [!] {d['question'][:50]} — "
                    f"{best.risk_level.value} risk (score +25)"
                )
        if not insider_hooks:
            print("  No suspicious activity detected")

        # Re-sort after insider boosts
        details.sort(key=lambda x: x["score"], reverse=True)
    except Exception as e:
        logger.warning(f"Insider scan failed (non-fatal): {e}")
        print(f"  (Insider scan unavailable: {e})")

    # 2. Fetch top yields
    print("\n[2/4] Fetching top DeFi yields...")
    yields = get_top_yields(3)
    if yields:
        for y in yields:
            print(
                f"  {y.get('project','?')} | {y.get('chain','?')} | "
                f"{y.get('symbol','?')} | APY: {y.get('apy',0):.1f}% | "
                f"TVL: ${y.get('tvlUsd',0):,.0f}"
            )
        run_data["yields"] = yields
    else:
        print("  (No yield data available)")

    # 3. Generate videos for top markets
    if generate:
        print("\n[3/4] Generating videos...")
        for i, d in enumerate(details, 1):
            slug = d.get("slug", "")
            hook = insider_hooks.get(slug, "")
            topic = (hook + " " if hook else "") + market_to_video_topic(d)
            print(f"\n  Generating video #{i}: {d['question'][:50]}...")
            try:
                result = generate_video(topic)
                task_id = result.get("task_id", "unknown")
                print(f"  -> Task queued: {task_id}")
                run_data["videos"].append(
                    {"task_id": task_id, "topic": topic, "status": "queued"}
                )
            except Exception as e:
                print(f"  x Failed: {e}")
                run_data["videos"].append(
                    {"task_id": None, "topic": topic, "error": str(e)}
                )
    else:
        print("\n[3/4] Skipping video generation (--dry-run)")

    # Log
    log_path = log_run(run_data)
    print(f"\n{'='*60}")
    print(f"  Pipeline complete. Log: {log_path}")
    print(f"  Check MoneyPrinterTurbo UI: http://localhost:8501")
    print(f"{'='*60}\n")

    return run_data


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv or "--no-generate" in sys.argv
    count = 3
    for arg in sys.argv[1:]:
        if arg.isdigit():
            count = int(arg)

    result = run_pipeline(market_count=count, generate=not dry_run)
    assert result is not None, "Pipeline returned None"
    print(f"  {__file__} passed smoke test")
    print(f"  Markets fetched: {len(result['markets'])}")
    print(f"  Videos queued: {len(result['videos'])}")
