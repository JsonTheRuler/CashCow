"""HTTP fetch helpers for Polymarket Gamma and DeFi Llama (keyless public APIs)."""

from __future__ import annotations

import json
from typing import Any

import requests

GAMMA_MARKETS_URL = "https://gamma-api.polymarket.com/markets"
LLAMA_POOL_URLS = (
    "https://api.llama.fi/pools",
    "https://yields.llama.fi/pools",
)


def _coerce_float(value: Any, default: float = 0.0) -> float:
    try:
        if isinstance(value, str) and value.strip().startswith("["):
            parsed = json.loads(value)
            if isinstance(parsed, list) and parsed:
                return float(parsed[0])
        return float(value)
    except (TypeError, ValueError, json.JSONDecodeError):
        return default


def _extract_yes_no(item: dict[str, Any]) -> tuple[float, float]:
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


def fetch_gamma_markets(limit: int = 20, timeout: float = 25.0) -> list[dict[str, Any]]:
    """Return normalized prediction-market dicts for scoring."""
    params = {
        "limit": limit,
        "active": "true",
        "closed": "false",
        "archived": "false",
        "order": "volume24hr",
        "ascending": "false",
    }
    r = requests.get(GAMMA_MARKETS_URL, params=params, timeout=timeout)
    r.raise_for_status()
    payload = r.json()
    markets = payload if isinstance(payload, list) else payload.get("data", [])
    out: list[dict[str, Any]] = []
    for item in markets[:limit]:
        if not isinstance(item, dict):
            continue
        yes_pct, no_pct = _extract_yes_no(item)
        out.append(
            {
                "id": str(item.get("id") or item.get("slug") or item.get("conditionId") or ""),
                "question": str(item.get("question", "")).strip(),
                "yes_pct": yes_pct,
                "no_pct": no_pct,
                "volume_24h": _coerce_float(item.get("volume24hr", item.get("volume24h", item.get("volume")))),
                "description": str(item.get("description", "")).strip(),
                "created_at": item.get("createdAt") or item.get("startDate"),
                "raw": item,
            }
        )
    return out


def fetch_llama_pool_rows(timeout: float = 45.0) -> list[dict[str, Any]]:
    """Return raw pool dicts from first working Llama yields endpoint."""
    last_err: Exception | None = None
    for url in LLAMA_POOL_URLS:
        try:
            r = requests.get(url, timeout=timeout)
            r.raise_for_status()
            body = r.json()
            rows = body.get("data") if isinstance(body, dict) else body
            if isinstance(rows, list):
                return rows
        except Exception as e:
            last_err = e
            continue
    if last_err:
        raise last_err
    return []


if __name__ == "__main__":
    mk = fetch_gamma_markets(limit=2)
    assert mk is not None
    print(f"✓ {__file__} passed smoke test")
    print(f"  Result: {len(mk)} markets")
