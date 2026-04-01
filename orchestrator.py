"""Cash Cow pipeline orchestrator with direct root imports only."""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from bridge import poll_task, submit_video
from defi_pipeline import get_defi_summary
from scorer import fetch_and_score

ROOT = Path(__file__).resolve().parent
LOGS_DIR = ROOT / "logs"
PLAN_PATH = LOGS_DIR / "last_plan.json"
STATE_PATH = ROOT / "state.json"


def _ensure_dirs() -> None:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)


def _write_plan(plan: dict[str, Any]) -> None:
    _ensure_dirs()
    PLAN_PATH.write_text(json.dumps(plan, indent=2), encoding="utf-8")


def _load_state() -> dict[str, Any]:
    if not STATE_PATH.exists():
        return {}
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _save_state(data: dict[str, Any]) -> None:
    STATE_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")


def get_last_plan() -> dict[str, Any]:
    """Return the last persisted plan, or a helpful placeholder."""
    if PLAN_PATH.exists():
        try:
            data = json.loads(PLAN_PATH.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return {"ok": True, "plan": data}
        except json.JSONDecodeError:
            pass
    return {
        "ok": True,
        "plan": {
            "steps": [
                {"id": 1, "name": "Fetch Polymarket Gamma", "status": "ready"},
                {"id": 2, "name": "Score markets with Cash Cow", "status": "ready"},
                {"id": 3, "name": "Submit top videos to MoneyPrinterTurbo", "status": "ready"},
                {"id": 4, "name": "Scan DeFi yields", "status": "ready"},
            ]
        },
    }


def pipeline_diagram_mermaid() -> str:
    """Return a mermaid diagram for docs and dashboards."""
    return """
flowchart LR
  Gamma[Polymarket Gamma] --> Score[Cash Cow scorer]
  Score --> Video[MoneyPrinterTurbo]
  Score --> Signals[state.json signals]
  Llama[DeFi Llama] --> Yields[Yield summary]
  Video --> Dashboard[Dashboard]
  Signals --> Dashboard
  Yields --> Dashboard
"""


def run_once(max_videos: int = 3) -> dict[str, Any]:
    """Run a single end-to-end pipeline cycle."""
    scored_markets = fetch_and_score(limit=max(5, max_videos * 2))
    defi_summary = get_defi_summary(limit=5)

    plan = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "steps": [
            {"id": 1, "name": "Fetch Polymarket Gamma", "status": "completed", "count": len(scored_markets)},
            {"id": 2, "name": "Score markets with Cash Cow", "status": "completed"},
            {"id": 3, "name": "Submit top videos to MoneyPrinterTurbo", "status": "in_progress"},
            {"id": 4, "name": "Scan DeFi yields", "status": "completed", "count": defi_summary.get("count", 0)},
        ],
    }
    _write_plan(plan)

    video_results: list[dict[str, Any]] = []
    for market in scored_markets[:max_videos]:
        payload = market.to_dict()
        submission = submit_video(payload)
        status = poll_task(str(submission.get("task_id", "")))
        video_results.append(
            {
                "question": market.question,
                "score": market.score,
                "task_id": submission.get("task_id"),
                "status": status.get("status", "completed"),
                "video_path": status.get("video_path") or f"demo://{market.id}.mp4",
            }
        )

    plan["steps"][2]["status"] = "completed"
    _write_plan(plan)

    state = _load_state()
    state["pipeline_status"] = "completed"
    state["last_orchestrator_run"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    state["top_markets"] = [market.to_dict() for market in scored_markets[:5]]
    state["video_runs"] = video_results
    _save_state(state)

    return {
        "status": "ok",
        "markets": [market.to_dict() for market in scored_markets],
        "videos": video_results,
        "defi": defi_summary,
        "plan": plan,
    }


def run_loop(interval_seconds: int = 900, max_cycles: int | None = None) -> None:
    """Run the orchestrator repeatedly with a sleep interval between cycles."""
    cycles = 0
    while True:
        run_once()
        cycles += 1
        if max_cycles is not None and cycles >= max_cycles:
            return
        time.sleep(interval_seconds)


if __name__ == "__main__":
    print(json.dumps(run_once(), indent=2))
