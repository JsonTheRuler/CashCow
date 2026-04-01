"""Social vs prediction-market divergence helpers (Grok-style intel files + fallbacks)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
DIVERGENCE_PATH = ROOT / "intel" / "divergence_alerts.json"

_DEFAULT_ALERTS: list[dict[str, Any]] = [
    {
        "id": "demo-btc-etf",
        "title_keywords": ["bitcoin", "btc", "crypto"],
        "divergence_index": 8.1,
        "social_sentiment": "very_bullish",
        "market_yes_implied": 44,
        "summary": "X/Twitter tone runs hotter than Polymarket YES odds—possible lag or contrarian entry.",
        "source": "demo_seed",
    },
    {
        "id": "demo-fed",
        "title_keywords": ["fed", "rate", "inflation", "cpi"],
        "divergence_index": 6.4,
        "social_sentiment": "bearish_news_cycle",
        "market_yes_implied": 62,
        "summary": "Headline fear is elevated while implied odds stay moderate; watch for volatility around prints.",
        "source": "demo_seed",
    },
]


def _load_raw_alerts() -> list[dict[str, Any]]:
    """Load divergence alerts from intel file or use embedded demo rows."""
    if not DIVERGENCE_PATH.exists():
        return list(_DEFAULT_ALERTS)
    try:
        raw = json.loads(DIVERGENCE_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return list(_DEFAULT_ALERTS)
    if isinstance(raw, list):
        return [a for a in raw if isinstance(a, dict)]
    if isinstance(raw, dict):
        inner = raw.get("alerts") or raw.get("divergences") or raw.get("items")
        if isinstance(inner, list):
            return [a for a in inner if isinstance(a, dict)]
    return list(_DEFAULT_ALERTS)


def get_top_divergences(limit: int = 12) -> list[dict[str, Any]]:
    """
    Return Grok-style divergence alerts, highest divergence_index first.

    Reads ``intel/divergence_alerts.json`` when present; otherwise uses defaults.
    """
    rows = _load_raw_alerts()

    def _key(row: dict[str, Any]) -> float:
        try:
            return float(row.get("divergence_index") or row.get("score") or 0.0)
        except (TypeError, ValueError):
            return 0.0

    ranked = sorted(rows, key=_key, reverse=True)
    return ranked[: max(1, limit)]


def social_divergence_for_market(market_question: str) -> str:
    """
    Short label for UI tables: best matching alert divergence index, else a stable heuristic.
    """
    q = (market_question or "").lower().strip()
    if not q:
        return "—"
    best_idx = 0.0
    best_label = ""
    for alert in _load_raw_alerts():
        kws = alert.get("title_keywords") or []
        if not kws:
            continue
        hits = sum(1 for k in kws if str(k).lower() in q)
        if hits == 0:
            continue
        try:
            idx = float(alert.get("divergence_index") or alert.get("score") or 0.0)
        except (TypeError, ValueError):
            idx = 0.0
        if idx >= best_idx:
            best_idx = idx
            soc = str(alert.get("social_sentiment") or "").replace("_", " ")[:16]
            best_label = f"{idx:.1f}" + (f" ({soc})" if soc else "")
    if best_label:
        return best_label
    # Deterministic mild divergence when no keyword match (hackathon demo)
    h = abs(hash(q)) % 70
    return f"~{h / 10:.1f}"


if __name__ == "__main__":
    divs = get_top_divergences(3)
    assert divs, "expected divergences"
    print(f"✓ {__file__} passed smoke test")
    print(f"  top: {divs[0].get('divergence_index')} — {divs[0].get('summary', '')[:60]}…")
    print(f"  label: {social_divergence_for_market('Will Bitcoin hit 200k this year?')}")
