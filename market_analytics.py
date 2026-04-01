"""Aggregate analytics over trending Polymarket markets."""

from __future__ import annotations

from collections import Counter
from typing import Any

from data_sources import fetch_gamma_markets


def full_analytics(limit: int = 25) -> dict[str, Any]:
    """
    Category-style breakdown, simple momentum proxy, and volume stats.
    All derived from free Gamma API data (no keys).
    """
    try:
        markets = fetch_gamma_markets(limit=limit)
    except Exception as e:
        return {"ok": False, "error": str(e), "markets_analyzed": 0}

    vols: list[float] = []
    yes_skew: list[float] = []
    momentum_hints: list[float] = []

    for m in markets:
        raw = m.get("raw") or {}
        v = float(m.get("volume_24h") or 0.0)
        vols.append(v)
        y = float(m.get("yes_pct") or 50.0)
        yes_skew.append(y)
        ch = raw.get("oneDayPriceChange") or raw.get("oneHourPriceChange")
        if ch is not None:
            try:
                momentum_hints.append(float(ch))
            except (TypeError, ValueError):
                pass

    # crude "category" from question keywords
    cats = Counter()
    keywords = {
        "politics": ("trump", "biden", "election", "president", "congress", "senate", "minister", "parliament"),
        "crypto": ("bitcoin", "btc", "ethereum", "eth", "solana", "crypto"),
        "macro": ("fed", "cpi", "inflation", "recession", "gdp", "rates"),
        "geopolitics": ("iran", "china", "russia", "nato", "war", "military"),
        "sports": ("nba", "nfl", "world cup", "olympics", "super bowl"),
    }
    for m in markets:
        q = (m.get("question") or "").lower()
        tagged = False
        for cat, terms in keywords.items():
            if any(t in q for t in terms):
                cats[cat] += 1
                tagged = True
        if not tagged:
            cats["other"] += 1

    return {
        "status": "ok",
        "ok": True,
        "markets_analyzed": len(markets),
        "total_volume_24h": sum(vols),
        "avg_yes_pct": sum(yes_skew) / len(yes_skew) if yes_skew else 0.0,
        "category_counts": dict(cats),
        "momentum": {
            "sample_size": len(momentum_hints),
            "avg_price_nudge": sum(momentum_hints) / len(momentum_hints) if momentum_hints else None,
        },
        "top_volume_preview": sorted(
            (
                {
                    "question": m.get("question", "")[:120],
                    "volume_24h": m.get("volume_24h", 0),
                    "yes_pct": m.get("yes_pct"),
                }
                for m in markets
            ),
            key=lambda x: float(x["volume_24h"] or 0),
            reverse=True,
        )[:5],
        "top_markets": sorted(
            (
                {
                    "question": m.get("question", "")[:120],
                    "volume_24h": m.get("volume_24h", 0),
                    "yes_pct": m.get("yes_pct"),
                }
                for m in markets
            ),
            key=lambda x: float(x["volume_24h"] or 0),
            reverse=True,
        )[:5],
    }


if __name__ == "__main__":
    result = full_analytics(5)
    assert result is not None, "Function returned None"
    print(f"✓ {__file__} passed smoke test")
    print(f"  Result: ok={result.get('ok')}, markets={result.get('markets_analyzed')}")
