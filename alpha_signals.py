"""
Divergence-triggered copy-trade style signals — **Cash Cow Alpha Signal**.

Educational framing only (not financial advice). Pairs social/divergence intel with Polymarket rows
for dashboard + video descriptions. Monetization hooks (Whop / performance fee) are out of scope here.
"""

from __future__ import annotations

import os
from typing import Any

import sentiment

PRODUCT_NAME = "Cash Cow Alpha Signal"

ALPHA_DIVERGENCE_MIN = float(os.getenv("CASH_COW_ALPHA_DIVERGENCE_MIN", "5.0"))

# X follow — default "No Limits"; override with CASH_COW_X_SCREEN_NAME or full CASH_COW_X_FOLLOW_URL
_X_SCREEN = os.getenv("CASH_COW_X_SCREEN_NAME", "NoLimits").lstrip("@")
X_FOLLOW_URL = os.getenv(
    "CASH_COW_X_FOLLOW_URL",
    f"https://x.com/intent/follow?screen_name={_X_SCREEN}",
)
X_DISPLAY_NAME = os.getenv("CASH_COW_X_DISPLAY_NAME", "No Limits")

DISCLAIMER_SHORT = (
    "Educational signal only — not investment advice. Paper-trade at least 7 days before real capital."
)


def polymarket_link_for_market(market: dict[str, Any]) -> str:
    """Best-effort deep link for copy-flow; falls back to site root."""
    raw = market.get("raw_polymarket") if isinstance(market.get("raw_polymarket"), dict) else {}
    slug = raw.get("slug") or raw.get("eventSlug") or market.get("slug")
    if slug and isinstance(slug, str) and slug.strip():
        return f"https://polymarket.com/event/{slug.strip()}"
    return "https://polymarket.com"


def build_alpha_signal_row(market: dict[str, Any]) -> dict[str, Any]:
    """One structured alpha row for API / dashboard."""
    q = str(market.get("question") or "")
    detail = sentiment.get_market_divergence_detail(q)
    idx = detail.get("index")
    return {
        "product": PRODUCT_NAME,
        "market_id": market.get("id"),
        "question": q,
        "yes_pct": float(market.get("yes_pct") or 50),
        "no_pct": float(market.get("no_pct") or 50),
        "cash_cow_score": float(market.get("cash_cow_score") or market.get("score") or 0),
        "divergence_display": detail.get("display"),
        "divergence_index": idx,
        "matched_intel_alert": bool(detail.get("matched_alert")),
        "intel_summary": (detail.get("alert_summary") or "")[:240],
        "social_sentiment": detail.get("social_sentiment") or "",
        "polymarket_url": polymarket_link_for_market(market),
        "copy_frame": (
            "Social/X hype vs Polymarket implied odds diverged — smart-copy style watchlist item "
            "(observe only; align with your own research)."
        ),
        "disclaimer": DISCLAIMER_SHORT,
        "x_follow_url": X_FOLLOW_URL,
        "x_display_name": X_DISPLAY_NAME,
    }


def list_alpha_copy_signals(markets: list[dict[str, Any]], limit: int = 10) -> list[dict[str, Any]]:
    """
    Markets ranked by divergence index (numeric), filtered by minimum threshold when matched_alert
    OR heuristic index still above threshold.
    """
    rows: list[dict[str, Any]] = []
    for m in markets:
        row = build_alpha_signal_row(m)
        idx = row.get("divergence_index")
        if idx is None:
            continue
        if float(idx) < ALPHA_DIVERGENCE_MIN and not row.get("matched_intel_alert"):
            continue
        rows.append(row)

    rows.sort(key=lambda r: float(r.get("divergence_index") or 0), reverse=True)
    if rows:
        return rows[:limit]

    # Fallback: top markets by score still get a soft alpha row (demo / low divergence day)
    soft: list[dict[str, Any]] = []
    for m in sorted(
        markets,
        key=lambda x: float(x.get("cash_cow_score") or x.get("score") or 0),
        reverse=True,
    )[:limit]:
        row = build_alpha_signal_row(m)
        row["soft_tier"] = True
        row["copy_frame"] = (
            "Lower divergence threshold today — still flagged for Cash Cow Alpha watchlist (paper only)."
        )
        soft.append(row)
    return soft


if __name__ == "__main__":
    demo_m = [
        {
            "id": "x",
            "question": "Will Bitcoin exceed 100k in 2026?",
            "yes_pct": 55,
            "no_pct": 45,
            "cash_cow_score": 72,
            "raw_polymarket": {"slug": "btc-100k-2026"},
        }
    ]
    sigs = list_alpha_copy_signals(demo_m, limit=3)
    assert sigs
    print(f"✓ {__file__} smoke OK — {len(sigs)} signal(s)")
    print(sigs[0].get("product"), sigs[0].get("divergence_display"))
