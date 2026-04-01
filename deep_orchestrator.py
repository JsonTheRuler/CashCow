"""DeepAgents orchestrator for the Cash Cow autonomous content pipeline."""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests
from deepagents import create_deep_agent
from langchain.chat_models import init_chat_model
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from prompts import build_video_subject
from scorer import rank_opportunities


DEFAULT_SYSTEM_PROMPT = (
    "You are Cash Cow, an autonomous market intelligence agent. Every 15 minutes, "
    "scan prediction markets for trending topics, score them for content potential, "
    "and generate short-form videos about the highest-scoring opportunities. "
    "Always begin by writing a plan with the built-in planning tool before executing steps, "
    "and log all actions."
)


def _setup_logger(log_path: Path) -> logging.Logger:
    """Create or reuse a file-backed logger for orchestrator actions."""
    logger = logging.getLogger("cash_cow")
    if logger.handlers:
        return logger

    log_path.parent.mkdir(parents=True, exist_ok=True)
    logger.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)
    return logger


def _requests_session() -> requests.Session:
    """Build a retry-enabled HTTP session."""
    retry = Retry(
        total=3,
        connect=3,
        read=3,
        status=3,
        backoff_factor=1.0,
        allowed_methods=frozenset({"GET", "POST"}),
        status_forcelist={408, 409, 429, 500, 502, 503, 504},
        raise_on_status=False,
    )
    session = requests.Session()
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update({"User-Agent": "CashCow/1.0"})
    return session


def _coerce_float(value: Any, default: float = 0.0) -> float:
    """Safely coerce API values into floats."""
    try:
        if isinstance(value, str) and value.strip().startswith("["):
            parsed = json.loads(value)
            if isinstance(parsed, list) and parsed:
                return float(parsed[0])
        return float(value)
    except (TypeError, ValueError, json.JSONDecodeError):
        return default


def _extract_yes_no(item: dict[str, Any]) -> tuple[float, float]:
    """Best-effort extraction of YES/NO percentages from Polymarket data."""
    yes_pct = _coerce_float(item.get("yes_pct", item.get("yesPrice")))
    no_pct = _coerce_float(item.get("no_pct", item.get("noPrice")))

    if yes_pct == 0.0 and "outcomePrices" in item:
        outcome_prices = item["outcomePrices"]
        if isinstance(outcome_prices, str):
            try:
                outcome_prices = json.loads(outcome_prices)
            except json.JSONDecodeError:
                outcome_prices = []
        if isinstance(outcome_prices, list) and outcome_prices:
            yes_pct = _coerce_float(outcome_prices[0]) * 100.0
            if len(outcome_prices) > 1:
                no_pct = _coerce_float(outcome_prices[1]) * 100.0

    if no_pct == 0.0 and yes_pct > 0.0:
        no_pct = max(0.0, 100.0 - yes_pct)
    return round(yes_pct, 2), round(no_pct, 2)


@dataclass(slots=True)
class CashCowConfig:
    """Runtime configuration for the Cash Cow orchestrator."""

    polymarket_base_url: str = os.getenv("POLYMARKET_GAMMA_API_URL", "https://gamma-api.polymarket.com")
    defillama_yields_url: str = os.getenv("DEFILLAMA_YIELDS_URL", "https://yields.llama.fi/pools")
    moneyprinterturbo_base_url: str = os.getenv("MONEYPRINTERTURBO_API_URL", "http://127.0.0.1:8080")
    log_path: Path = Path(os.getenv("CASH_COW_LOG_PATH", "logs/cash_cow.log"))
    request_timeout: float = float(os.getenv("CASH_COW_TIMEOUT_SECONDS", "30"))
    default_vibe: str = os.getenv("CASH_COW_DEFAULT_VIBE", "breaking_news")


class CashCowOrchestrator:
    """Operational wrapper around the Cash Cow data and video pipeline."""

    def __init__(self, config: CashCowConfig | None = None) -> None:
        self.config = config or CashCowConfig()
        self.logger = _setup_logger(self.config.log_path)
        self.session = _requests_session()

    def log_action(self, action: str, details: dict[str, Any] | None = None) -> None:
        """Write an action entry to the file log."""
        payload = {"action": action, "details": details or {}}
        self.logger.info(json.dumps(payload, default=str))

    def fetch_polymarket_trends(self, limit: int = 10) -> list[dict[str, Any]]:
        """Fetch top-trending Polymarket opportunities from the Gamma API."""
        params = {
            "limit": limit,
            "active": "true",
            "closed": "false",
            "archived": "false",
            "order": "volume24hr",
            "ascending": "false",
        }
        url = f"{self.config.polymarket_base_url.rstrip('/')}/markets"
        self.log_action("fetch_polymarket_trends_start", {"url": url, "limit": limit})
        response = self.session.get(url, params=params, timeout=self.config.request_timeout)
        response.raise_for_status()
        payload = response.json()
        markets = payload if isinstance(payload, list) else payload.get("data", [])

        normalized: list[dict[str, Any]] = []
        for item in markets[:limit]:
            if not isinstance(item, dict):
                continue
            yes_pct, no_pct = _extract_yes_no(item)
            normalized.append(
                {
                    "id": str(item.get("id") or item.get("slug") or item.get("conditionId") or item.get("question")),
                    "question": str(item.get("question", "")).strip(),
                    "yes_pct": yes_pct,
                    "no_pct": no_pct,
                    "volume_24h": _coerce_float(item.get("volume24hr", item.get("volume24h", item.get("volume")))),
                    "description": str(item.get("description", "")).strip(),
                    "created_at": item.get("createdAt") or item.get("created_at") or item.get("startDate"),
                    "source": "polymarket",
                    "raw": item,
                }
            )
        self.log_action("fetch_polymarket_trends_complete", {"count": len(normalized)})
        return normalized

    def fetch_defi_yields(self, limit: int = 10) -> list[dict[str, Any]]:
        """Fetch top yield opportunities from DeFi Llama."""
        self.log_action("fetch_defi_yields_start", {"url": self.config.defillama_yields_url, "limit": limit})
        response = self.session.get(self.config.defillama_yields_url, timeout=self.config.request_timeout)
        response.raise_for_status()
        payload = response.json()
        pools = payload.get("data", []) if isinstance(payload, dict) else []

        filtered = [
            pool
            for pool in pools
            if isinstance(pool, dict)
            and not bool(pool.get("ilRisk"))
            and _coerce_float(pool.get("tvlUsd")) > 0.0
            and _coerce_float(pool.get("apy")) > 0.0
        ]
        filtered.sort(key=lambda item: (_coerce_float(item.get("apy")), _coerce_float(item.get("tvlUsd"))), reverse=True)

        normalized = [
            {
                "id": str(item.get("pool") or item.get("project") or item.get("symbol")),
                "protocol": str(item.get("project", "")),
                "chain": str(item.get("chain", "")),
                "symbol": str(item.get("symbol", "")),
                "apy": _coerce_float(item.get("apy")),
                "tvl": _coerce_float(item.get("tvlUsd")),
                "stablecoin": bool(item.get("stablecoin") or item.get("stablecoins")),
                "source": "defillama",
                "raw": item,
            }
            for item in filtered[:limit]
        ]
        self.log_action("fetch_defi_yields_complete", {"count": len(normalized)})
        return normalized

    def score_opportunities(
        self,
        prediction_markets: list[dict[str, Any]],
        defi_yields: list[dict[str, Any]],
        top_k: int = 10,
    ) -> list[dict[str, Any]]:
        """Score and rank all candidate opportunities."""
        self.log_action(
            "score_opportunities_start",
            {"prediction_markets": len(prediction_markets), "defi_yields": len(defi_yields), "top_k": top_k},
        )
        ranked = rank_opportunities(prediction_markets, defi_yields)
        result = [
            {
                "rank": item.rank,
                "kind": item.kind,
                "id": item.id,
                "title": item.title,
                "raw_score": item.raw_score,
                "cash_cow_score": item.cash_cow_score,
                "score_breakdown": item.score_breakdown,
                "source_data": item.source_data,
            }
            for item in ranked[:top_k]
        ]
        self.log_action("score_opportunities_complete", {"returned": len(result)})
        return result

    def trigger_video_generation(
        self,
        title: str,
        source_data: dict[str, Any],
        vibe: str | None = None,
    ) -> dict[str, Any]:
        """Submit a new MoneyPrinterTurbo video-generation task."""
        selected_vibe = vibe or self.config.default_vibe
        video_subject = build_video_subject(
            selected_vibe,
            question=str(source_data.get("question", title)),
            yes_pct=float(source_data.get("yes_pct", 50.0)),
            no_pct=float(source_data.get("no_pct", 50.0)),
            volume_24h=float(source_data.get("volume_24h", 0.0)),
            description=str(source_data.get("description", title)),
        )
        payload = {
            "video_subject": video_subject,
            "video_language": "en",
            "aspect": "9:16",
            "metadata": {
                "cash_cow_title": title,
                "cash_cow_vibe": selected_vibe,
                "source_kind": source_data.get("source", "unknown"),
            },
        }
        url = f"{self.config.moneyprinterturbo_base_url.rstrip('/')}/videos"
        self.log_action("trigger_video_generation_start", {"url": url, "title": title, "vibe": selected_vibe})
        response = self.session.post(url, json=payload, timeout=self.config.request_timeout)
        response.raise_for_status()
        data = response.json()
        self.log_action("trigger_video_generation_complete", {"response": data})
        return data

    def check_video_status(self, task_id: str) -> dict[str, Any]:
        """Check the status of a MoneyPrinterTurbo task."""
        url = f"{self.config.moneyprinterturbo_base_url.rstrip('/')}/tasks/{task_id}"
        self.log_action("check_video_status_start", {"url": url, "task_id": task_id})
        response = self.session.get(url, timeout=self.config.request_timeout)
        response.raise_for_status()
        data = response.json()
        self.log_action("check_video_status_complete", {"task_id": task_id, "response": data})
        return data

    def run_cycle(self, top_k: int = 1, vibe: str | None = None, poll_interval_seconds: int = 10) -> list[dict[str, Any]]:
        """Run one complete fetch-score-generate cycle."""
        prediction_markets = self.fetch_polymarket_trends(limit=max(10, top_k * 3))
        defi_yields = self.fetch_defi_yields(limit=max(10, top_k * 3))
        ranked = self.score_opportunities(prediction_markets, defi_yields, top_k=top_k)

        results: list[dict[str, Any]] = []
        for item in ranked:
            if item["kind"] != "prediction_market":
                continue
            task = self.trigger_video_generation(title=item["title"], source_data=item["source_data"], vibe=vibe)
            task_id = str(task.get("task_id") or task.get("id") or task.get("uuid") or "")
            status = {"task_id": task_id, "status": "submitted"}
            if task_id:
                for _ in range(3):
                    time.sleep(poll_interval_seconds)
                    status = self.check_video_status(task_id)
                    current_status = str(status.get("status", "")).lower()
                    if current_status in {"done", "completed", "failed", "error"}:
                        break
            results.append({"opportunity": item, "task": task, "status": status})
        return results


def create_cash_cow_agent(
    config: CashCowConfig | None = None,
    system_prompt: str = DEFAULT_SYSTEM_PROMPT,
):
    """Create a DeepAgents Cash Cow agent with custom tools and Gemini."""
    orchestrator = CashCowOrchestrator(config)
    model = init_chat_model("google_genai:gemini-2.0-flash")

    def fetch_polymarket_trends(limit: int = 10) -> list[dict[str, Any]]:
        """Fetch the top trending Polymarket markets."""
        return orchestrator.fetch_polymarket_trends(limit=limit)

    def fetch_defi_yields(limit: int = 10) -> list[dict[str, Any]]:
        """Fetch the top DeFi yield opportunities."""
        return orchestrator.fetch_defi_yields(limit=limit)

    def score_opportunities(
        prediction_markets: list[dict[str, Any]],
        defi_yields: list[dict[str, Any]],
        top_k: int = 10,
    ) -> list[dict[str, Any]]:
        """Score and rank opportunities across prediction markets and DeFi yields."""
        return orchestrator.score_opportunities(prediction_markets=prediction_markets, defi_yields=defi_yields, top_k=top_k)

    def trigger_video_generation(
        title: str,
        source_data: dict[str, Any],
        vibe: str = "breaking_news",
    ) -> dict[str, Any]:
        """Trigger video generation in MoneyPrinterTurbo for a selected opportunity."""
        return orchestrator.trigger_video_generation(title=title, source_data=source_data, vibe=vibe)

    def check_video_status(task_id: str) -> dict[str, Any]:
        """Check whether a MoneyPrinterTurbo task has completed."""
        return orchestrator.check_video_status(task_id=task_id)

    return create_deep_agent(
        model=model,
        tools=[
            fetch_polymarket_trends,
            fetch_defi_yields,
            score_opportunities,
            trigger_video_generation,
            check_video_status,
        ],
        system_prompt=system_prompt,
    )


if __name__ == "__main__":
    orchestrator = CashCowOrchestrator()
    try:
        sample_markets = orchestrator.fetch_polymarket_trends(limit=3)
        sample_yields = orchestrator.fetch_defi_yields(limit=3)
        ranked = orchestrator.score_opportunities(sample_markets, sample_yields, top_k=5)
        print("Top opportunities:")
        print(json.dumps(ranked, indent=2, default=str))
    except requests.RequestException as exc:
        print(f"Network test skipped due to request error: {exc}")

    try:
        agent = create_cash_cow_agent()
        print(f"Deep agent created successfully: {type(agent).__name__}")
    except Exception as exc:  # noqa: BLE001
        print(f"Agent creation skipped due to environment issue: {exc}")
