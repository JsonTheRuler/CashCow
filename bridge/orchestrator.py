#!/usr/bin/env python3
"""Cash Cow Orchestrator: runs the full pipeline on a loop.

Coordinates all bridge modules: market data, trading signals,
price forecasts, and video generation. Writes state to state.json
for the dashboard.

Usage:
    python -m bridge.orchestrator                    # Run once
    python -m bridge.orchestrator --loop             # Run every 15 min
    python -m bridge.orchestrator --loop --interval 5  # Every 5 min
    python -m bridge.orchestrator --dry-run          # No video gen
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime
from typing import Any

from loguru import logger

from bridge.bridge import get_trending_markets, get_market_detail, score_market
from bridge.bridge import market_to_video_topic, generate_video, get_top_yields
from bridge.trading_signal import get_signals_for_markets
from bridge.forecaster import forecast_market

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE_FILE = os.path.join(BASE_DIR, "state.json")
LOG_DIR = os.path.join(BASE_DIR, "logs")
DEFAULT_INTERVAL_MINUTES = 15


def write_state(state: dict[str, Any]) -> None:
    """Atomically write pipeline state to state.json.

    Args:
        state: Current pipeline state dict.
    """
    tmp = STATE_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(state, f, indent=2, default=str)
    os.replace(tmp, STATE_FILE)
    logger.info(f"State written to {STATE_FILE}")


def log_to_file(data: dict[str, Any], prefix: str = "orchestrator") -> str:
    """Write a timestamped JSON log file.

    Args:
        data: Data to log.
        prefix: Log filename prefix.

    Returns:
        Path to the log file.
    """
    os.makedirs(LOG_DIR, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(LOG_DIR, f"{prefix}_{ts}.json")
    with open(path, "w") as f:
        json.dump(data, f, indent=2, default=str)
    return path


def run_once(
    market_count: int = 5,
    generate_videos: bool = True,
) -> dict[str, Any]:
    """Execute one full pipeline cycle.

    Steps:
        1. Fetch trending Polymarket markets
        2. Score and rank them
        3. Get trading signals for detected tickers
        4. Run price forecasts
        5. Fetch top DeFi yields
        6. Generate videos for top markets
        7. Write state.json

    Args:
        market_count: Number of markets to fetch.
        generate_videos: Whether to trigger video generation.

    Returns:
        Complete pipeline state dict.
    """
    state: dict[str, Any] = {
        "last_run": datetime.now().isoformat(),
        "status": "running",
        "markets": [],
        "insider_alerts": [],
        "signals": [],
        "forecasts": [],
        "yields": [],
        "videos": [],
        "errors": [],
    }

    print(f"\n{'='*60}")
    print(f"  CASH COW ORCHESTRATOR @ {datetime.now().isoformat()}")
    print(f"{'='*60}\n")

    # 1. Markets
    print("[1/5] Fetching Polymarket markets...")
    try:
        raw_markets = get_trending_markets(market_count)
        details = [get_market_detail(m) for m in raw_markets]
        for d in details:
            d["score"] = score_market(d)
        details.sort(key=lambda x: x["score"], reverse=True)
        state["markets"] = details

        for i, d in enumerate(details, 1):
            print(
                f"  #{i}: [{d['score']:.0f}] {d['question'][:60]} | {d['yes']}% YES"
            )
    except Exception as e:
        logger.error(f"Market fetch failed: {e}")
        state["errors"].append({"stage": "markets", "error": str(e)})

    # 1b. Insider activity scan
    print("\n[1b/6] Scanning for insider activity...")
    try:
        from insider.scanner import scan_market as _insider_scan
        from insider.formatter import format_state_entry

        for d, raw_m in zip(details, raw_markets):
            cond_id = raw_m.get("conditionId", raw_m.get("condition_id", ""))
            if not cond_id:
                continue
            alerts = _insider_scan(
                condition_id=cond_id,
                market_slug=d.get("slug", ""),
                market_question=d.get("question", ""),
                market_volume_24h=d.get("volume_24h", 0),
                trade_limit=20,
            )
            for a in alerts:
                state["insider_alerts"].append(format_state_entry(a))
                d["score"] = min(100, d.get("score", 0) + 25)
                print(f"  [!] {a.risk_level.value}: {d.get('question', '')[:50]}")
        if not state["insider_alerts"]:
            print("  No suspicious activity detected")
        details.sort(key=lambda x: x.get("score", 0), reverse=True)
    except Exception as e:
        logger.warning(f"Insider scan failed: {e}")
        state["errors"].append({"stage": "insider", "error": str(e)})

    # 2. Trading signals
    print("\n[2/6] Getting trading signals...")
    try:
        signals = get_signals_for_markets(details)
        state["signals"] = signals
        for s in signals:
            print(f"  {s['ticker']}: {s['signal']} (conf: {s['confidence']})")
        if not signals:
            print("  (No tradeable tickers detected)")
    except Exception as e:
        logger.error(f"Trading signals failed: {e}")
        state["errors"].append({"stage": "signals", "error": str(e)})

    # 3. Forecasts
    print("\n[3/6] Running price forecasts...")
    try:
        for market in raw_markets[:3]:
            fc = forecast_market(market)
            state["forecasts"].append(fc)
            model = fc.get("model", "?")
            n_pts = len(fc.get("forecast", []))
            print(f"  {fc.get('question', '?')[:50]}: {model} ({n_pts} pts)")
    except Exception as e:
        logger.error(f"Forecasting failed: {e}")
        state["errors"].append({"stage": "forecasts", "error": str(e)})

    # 4. DeFi yields
    print("\n[4/6] Fetching DeFi yields...")
    try:
        yields = get_top_yields(5)
        state["yields"] = yields
        for y in yields[:3]:
            print(
                f"  {y.get('project','?')} | {y.get('symbol','?')} | "
                f"APY: {y.get('apy',0):.1f}%"
            )
    except Exception as e:
        logger.error(f"DeFi yields failed: {e}")
        state["errors"].append({"stage": "yields", "error": str(e)})

    # 5. Video generation
    if generate_videos and details:
        print("\n[5/6] Generating videos...")
        for d in details[:3]:
            topic = market_to_video_topic(d)
            try:
                result = generate_video(topic)
                task_id = result.get("task_id", "unknown")
                print(f"  -> Queued: {task_id} ({d['question'][:40]})")
                state["videos"].append({
                    "task_id": task_id,
                    "market": d["question"],
                    "score": d["score"],
                    "status": "queued",
                })
            except Exception as e:
                print(f"  x Failed: {e}")
                state["videos"].append({
                    "market": d["question"],
                    "error": str(e),
                })
    else:
        print("\n[5/5] Skipping video generation")

    # Write state
    state["status"] = "complete"
    state["error_count"] = len(state["errors"])
    write_state(state)
    log_path = log_to_file(state)

    print(f"\n{'='*60}")
    print(f"  Done. Errors: {state['error_count']}")
    print(f"  State: {STATE_FILE}")
    print(f"  Log: {log_path}")
    print(f"{'='*60}\n")

    return state


def run_loop(
    interval_minutes: int = DEFAULT_INTERVAL_MINUTES,
    market_count: int = 5,
    generate_videos: bool = True,
) -> None:
    """Run the pipeline in a loop.

    Args:
        interval_minutes: Minutes between pipeline runs.
        market_count: Markets per run.
        generate_videos: Whether to generate videos.
    """
    logger.info(f"Starting orchestrator loop (interval: {interval_minutes}m)")
    iteration = 0

    while True:
        iteration += 1
        logger.info(f"--- Iteration {iteration} ---")
        try:
            run_once(
                market_count=market_count,
                generate_videos=generate_videos,
            )
        except Exception as e:
            logger.error(f"Pipeline iteration {iteration} failed: {e}")

        next_run = datetime.now().isoformat()
        logger.info(f"Next run in {interval_minutes} minutes...")
        time.sleep(interval_minutes * 60)


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    loop_mode = "--loop" in sys.argv

    interval = DEFAULT_INTERVAL_MINUTES
    for i, arg in enumerate(sys.argv):
        if arg == "--interval" and i + 1 < len(sys.argv):
            interval = int(sys.argv[i + 1])

    if loop_mode:
        run_loop(
            interval_minutes=interval,
            generate_videos=not dry_run,
        )
    else:
        result = run_once(generate_videos=not dry_run)
        assert result is not None, "Orchestrator returned None"
        print(f"  {__file__} passed smoke test")
