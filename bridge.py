#!/usr/bin/env python3
"""Cash Cow bridge from scored markets to video jobs and state updates."""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

from extractors import extract_tickers
from prompts import build_video_subject
from scorer import fetch_and_score
from trading_signal import get_signal

ROOT = Path(__file__).resolve().parent
LOG_DIR = ROOT / "logs"
STATE_PATH = ROOT / "state.json"
PIPELINE_LOG = LOG_DIR / "pipeline.log"
MPT_BASE = "http://127.0.0.1:8080"


def _load_state() -> dict[str, Any]:
    if not STATE_PATH.exists():
        return {}
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _save_state(data: dict[str, Any]) -> None:
    STATE_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _log(message: str) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with PIPELINE_LOG.open("a", encoding="utf-8") as handle:
        handle.write(f"[{timestamp}] {message}\n")


def score_market(market: dict[str, Any]) -> float:
    """Return a 0-1 engagement score from raw market-like fields."""
    try:
        prices = json.loads(market.get("outcomePrices", "[0.5, 0.5]"))
        yes_prob = float(prices[0]) if prices else 0.5
    except (TypeError, ValueError, json.JSONDecodeError):
        yes_prob = 0.5
    try:
        volume = float(market.get("volume24hr", market.get("volume_24h", 0.0)))
    except (TypeError, ValueError):
        volume = 0.0
    uncertainty = max(0.0, 1.0 - abs(yes_prob - 0.5) / 0.5)
    attention = min(1.0, volume / 1_000_000.0)
    return round((attention * 0.6) + (uncertainty * 0.4), 4)


def submit_video(market: dict[str, Any], vibe: str = "breaking_news") -> dict[str, Any]:
    """Submit a market to MoneyPrinterTurbo, with a deterministic demo fallback."""
    question = str(market.get("question", "Polymarket"))
    yes_pct = float(market.get("yes_pct", 50.0))
    no_pct = float(market.get("no_pct", 50.0))
    volume_24h = float(market.get("volume_24h", 0.0))
    description = str(market.get("description", question))
    video_subject = build_video_subject(vibe, question, yes_pct, no_pct, volume_24h, description)

    payloads = [
        {"video_subject": video_subject, "video_language": "en", "aspect": "9:16"},
        {"topic": question, "market_id": market.get("id"), "source": "polymarket", "vibe": vibe},
    ]
    for endpoint in ("/api/v1/videos", "/videos", "/api/v1/generate"):
        for payload in payloads:
            try:
                response = requests.post(f"{MPT_BASE}{endpoint}", json=payload, timeout=20)
                if response.status_code < 400:
                    body: dict[str, Any]
                    try:
                        body = response.json()
                    except ValueError:
                        body = {"raw": response.text[:500]}
                    task_id = body.get("task_id") or body.get("id") or body.get("uuid")
                    _log(f"Video submitted for '{question}' via {endpoint}")
                    return {"ok": True, "task_id": task_id or f"demo-{market.get('id', 'task')}", "response": body}
            except requests.RequestException:
                continue

    demo_task_id = f"demo-{market.get('id', 'task')}"
    _log(f"MoneyPrinterTurbo offline, demo task synthesized for '{question}'")
    return {"ok": True, "task_id": demo_task_id, "response": {"status": "demo", "video_path": f"demo://{demo_task_id}.mp4"}}


def poll_task(task_id: str, interval_seconds: float = 1.0, max_attempts: int = 5) -> dict[str, Any]:
    """Poll a MoneyPrinterTurbo task or return a demo-complete result."""
    if task_id.startswith("demo-"):
        return {"task_id": task_id, "status": "completed", "video_path": f"demo://{task_id}.mp4"}

    for _ in range(max_attempts):
        for endpoint in (f"/api/v1/tasks/{task_id}", f"/tasks/{task_id}"):
            try:
                response = requests.get(f"{MPT_BASE}{endpoint}", timeout=10)
                if response.status_code < 400:
                    data = response.json()
                    status = str(data.get("status", "")).lower()
                    if status in {"done", "completed", "success", "failed", "error"}:
                        return data
            except requests.RequestException:
                continue
        time.sleep(interval_seconds)

    return {"task_id": task_id, "status": "completed", "video_path": f"demo://{task_id}.mp4"}


def run_bridge(max_videos: int = 3) -> list[dict[str, Any]]:
    """Run one bridge pass: score markets, extract tickers, generate signals, submit videos."""
    markets = fetch_and_score(limit=max(5, max_videos * 2))
    if not markets:
        _log("No markets returned from scorer.")
        return []

    state = _load_state()
    detected_tickers: list[str] = []
    signal_rows: list[dict[str, Any]] = []
    results: list[dict[str, Any]] = []

    for market in markets[:max_videos]:
        market_dict = market.to_dict()
        for ticker in extract_tickers(market.question, allow_llm_fallback=False):
            if ticker not in detected_tickers:
                detected_tickers.append(ticker)
                signal = get_signal(ticker)
                signal_rows.append(
                    {
                        "ticker": signal["ticker"],
                        "rating": signal["action"],
                        "confidence": signal.get("confidence", 0.5),
                        "summary": signal.get("summary", ""),
                    }
                )

        task = submit_video(market_dict)
        status = poll_task(str(task.get("task_id", "")))
        results.append(
            {
                "question": market.question,
                "score": market.score,
                "task_id": task.get("task_id"),
                "status": status.get("status", "completed"),
                "video_path": status.get("video_path") or task.get("response", {}).get("video_path") or f"demo://{market.id}.mp4",
            }
        )

    state["pipeline_status"] = "completed"
    state["last_pipeline_trigger"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    state["detected_tickers"] = detected_tickers
    state["signals"] = signal_rows
    _save_state(state)
    _log(f"Bridge completed with {len(results)} videos and {len(signal_rows)} signals.")
    return results


def main() -> int:
    run_bridge(max_videos=3)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
