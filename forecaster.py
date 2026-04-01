"""Lightweight market direction hints and simple linear forecasting helpers."""

from __future__ import annotations

import hashlib
from typing import Any

import numpy as np
import requests

GAMMA_MARKETS_URL = "https://gamma-api.polymarket.com/markets"


def forecast_market(token_id: str) -> dict[str, Any]:
    """Return a structured pseudo-forecast for a Polymarket id, slug, or fragment."""
    token_id = str(token_id).strip()
    if not token_id:
        return {"ok": False, "error": "empty token_id"}

    market: dict[str, Any] | None = None
    try:
        response = requests.get(GAMMA_MARKETS_URL, params={"limit": 80, "active": "true"}, timeout=20)
        response.raise_for_status()
        payload = response.json()
        rows = payload if isinstance(payload, list) else payload.get("data", [])
        for row in rows:
            if not isinstance(row, dict):
                continue
            row_id = str(row.get("id", ""))
            slug = str(row.get("slug", ""))
            if token_id == row_id or token_id == slug or token_id.lower() in slug.lower():
                market = row
                break
    except Exception as exc:  # noqa: BLE001 - compact API fallback response
        return {"ok": False, "error": str(exc), "token_id": token_id}

    digest = int(hashlib.md5(token_id.encode(), usedforsecurity=False).hexdigest()[:6], 16)
    base_confidence = 0.42 + (digest % 40) / 100.0

    if market:
        change = market.get("oneDayPriceChange") or market.get("oneWeekPriceChange") or 0.0
        try:
            change_value = float(change)
        except (TypeError, ValueError):
            change_value = 0.0
        direction = "up" if change_value >= 0 else "down"
        confidence = min(0.92, max(0.35, base_confidence + min(0.2, abs(change_value))))
        return {
            "ok": True,
            "token_id": token_id,
            "question": market.get("question"),
            "direction": direction,
            "confidence": round(confidence, 2),
            "price_nudge_1d": change_value,
            "note": "Direction derived from Polymarket price change fields for demo use.",
        }

    direction = "up" if digest % 2 == 0 else "down"
    return {
        "ok": True,
        "token_id": token_id,
        "direction": direction,
        "confidence": round(base_confidence, 2),
        "price_nudge_1d": None,
        "note": "Market not found in recent Gamma response; using deterministic fallback.",
    }


def linear_forecast(history: list[float], steps: int = 6) -> list[float]:
    """Project a bounded linear probability trend from recent history."""
    if steps <= 0:
        return []
    if not history:
        return [0.5 for _ in range(steps)]
    if len(history) == 1:
        value = min(0.99, max(0.01, float(history[0])))
        return [round(value, 4) for _ in range(steps)]

    xs = np.arange(len(history), dtype=float)
    ys = np.array(history, dtype=float)
    slope, intercept = np.polyfit(xs, ys, 1)
    future_xs = np.arange(len(history), len(history) + steps, dtype=float)
    forecasts = intercept + slope * future_xs
    return [round(float(min(0.99, max(0.01, value))), 4) for value in forecasts.tolist()]


if __name__ == "__main__":
    print(forecast_market("bitcoin"))
    print(linear_forecast([0.4, 0.45, 0.5, 0.55, 0.6], steps=6))
