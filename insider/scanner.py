"""Market scanner: fetch recent trades and run insider detection.

Main entry point for the insider tracker module. Scans trending
Polymarket markets for suspicious trading activity.

Usage:
    python -m insider.scanner              # Scan top 5 markets
    python -m insider.scanner --dry-run    # Print results only
    python -m insider.scanner 10           # Scan top 10 markets
"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from typing import Any

import requests
from loguru import logger

from insider.detectors import detect_fresh_wallet, detect_size_anomaly, score_risk
from insider.formatter import format_alert_text, format_state_entry
from insider.models import InsiderSignal, RiskAssessment, TradeInfo
from insider.wallet_profiler import get_wallet_profile

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
GAMMA_API = "https://gamma-api.polymarket.com"
DATA_API = "https://data-api.polymarket.com"

# In-memory dedup: (wallet, market_id) -> timestamp
_DEDUP: dict[tuple[str, str], float] = {}
DEDUP_WINDOW_SECONDS = 3600  # 1 hour


def _is_duplicate(wallet: str, market_id: str) -> bool:
    """Check if this wallet/market combo was recently flagged."""
    key = (wallet.lower(), market_id)
    now = time.time()
    if key in _DEDUP and now - _DEDUP[key] < DEDUP_WINDOW_SECONDS:
        return True
    _DEDUP[key] = now
    return False


def _prune_dedup() -> None:
    """Remove expired dedup entries."""
    now = time.time()
    expired = [k for k, ts in _DEDUP.items() if now - ts > DEDUP_WINDOW_SECONDS]
    for k in expired:
        del _DEDUP[k]


def fetch_recent_trades(condition_id: str, limit: int = 50) -> list[dict[str, Any]]:
    """Fetch recent trades for a market from the CLOB API.

    Args:
        condition_id: The market's condition ID.
        limit: Max number of trades to fetch.

    Returns:
        List of trade dicts from the CLOB API.
    """
    try:
        r = requests.get(
            f"{DATA_API}/trades",
            params={"market": condition_id, "limit": limit},
            timeout=10,
        )
        r.raise_for_status()
        data = r.json()
        return data if isinstance(data, list) else data.get("trades", data.get("data", []))
    except Exception as e:
        logger.warning(f"Failed to fetch trades for {condition_id[:10]}...: {e}")
        return []


def parse_trade(raw: dict[str, Any], market_slug: str = "") -> TradeInfo | None:
    """Parse a raw CLOB trade dict into a TradeInfo object.

    Args:
        raw: Raw trade dict from the API.
        market_slug: The market slug for context.

    Returns:
        TradeInfo or None if parsing fails.
    """
    try:
        wallet = str(
            raw.get("proxyWallet",
            raw.get("maker_address",
            raw.get("taker_address",
            raw.get("owner", ""))))
        )
        price = float(raw.get("price", 0))
        size_shares = float(raw.get("size", 0))
        size_usd = size_shares * price  # convert shares to USD value

        return TradeInfo(
            trade_id=str(raw.get("transactionHash", raw.get("id", ""))),
            market_id=str(raw.get("conditionId", raw.get("market", raw.get("asset_id", "")))),
            market_slug=market_slug or str(raw.get("slug", "")),
            wallet_address=wallet,
            side=str(raw.get("side", "BUY")).upper(),
            outcome=str(raw.get("outcome", "Yes")),
            price=price,
            size=size_usd,
            timestamp=datetime.now(timezone.utc),
        )
    except (ValueError, KeyError, TypeError) as e:
        logger.debug(f"Failed to parse trade: {e}")
        return None


def scan_market(
    condition_id: str,
    market_slug: str = "",
    market_question: str = "",
    market_volume_24h: float = 0.0,
    trade_limit: int = 30,
) -> list[RiskAssessment]:
    """Scan a single market for insider trading activity.

    Fetches recent trades, profiles each unique wallet, runs detectors,
    and returns risk assessments for any suspicious activity.

    Args:
        condition_id: The market's condition ID from the Gamma API.
        market_slug: Human-readable market slug.
        market_question: The market question text.
        market_volume_24h: 24-hour volume for size anomaly detection.
        trade_limit: Max trades to analyze.

    Returns:
        List of RiskAssessments with should_alert=True.
    """
    raw_trades = fetch_recent_trades(condition_id, limit=trade_limit)
    if not raw_trades:
        return []

    trades = [parse_trade(t, market_slug) for t in raw_trades]
    trades = [t for t in trades if t is not None and t.wallet_address]

    assessments: list[RiskAssessment] = []
    seen_wallets: set[str] = set()

    for trade in trades:
        wallet = trade.wallet_address.lower()
        if wallet in seen_wallets:
            continue
        seen_wallets.add(wallet)

        if _is_duplicate(wallet, trade.market_id):
            continue

        # Profile wallet
        profile = get_wallet_profile(wallet)

        # Run detectors
        signals: list[InsiderSignal] = []

        fresh_signal = detect_fresh_wallet(trade, profile)
        if fresh_signal:
            signals.append(fresh_signal)

        size_signal = detect_size_anomaly(trade, market_volume_24h)
        if size_signal:
            signals.append(size_signal)

        if not signals:
            continue

        # Score
        assessment = score_risk(signals, trade, market_question)
        if assessment.should_alert:
            assessments.append(assessment)
            logger.info(
                f"ALERT: {assessment.risk_level.value} risk on "
                f"{market_slug[:30]} | wallet={wallet[:10]}... "
                f"score={assessment.weighted_score:.2f}"
            )

    _prune_dedup()
    return assessments


def scan_trending(n: int = 5) -> dict[str, list[RiskAssessment]]:
    """Scan top N trending Polymarket markets for insider activity.

    Args:
        n: Number of markets to scan.

    Returns:
        Dict mapping market_slug to list of alerts for that market.
    """
    logger.info(f"Scanning top {n} trending markets for insider activity...")

    # Fetch trending markets
    try:
        r = requests.get(
            f"{GAMMA_API}/markets",
            params={"active": "true", "limit": n, "order": "volume24hr", "ascending": "false"},
            timeout=10,
        )
        r.raise_for_status()
        markets = r.json()
    except Exception as e:
        logger.error(f"Failed to fetch trending markets: {e}")
        return {}

    results: dict[str, list[RiskAssessment]] = {}

    for market in markets:
        slug = market.get("slug", "unknown")
        question = market.get("question", "")
        condition_id = market.get("conditionId", market.get("condition_id", ""))
        volume_24h = float(market.get("volume24hr", 0))

        if not condition_id:
            logger.debug(f"Skipping {slug}: no conditionId")
            continue

        logger.info(f"Scanning: {question[:60]}...")
        alerts = scan_market(
            condition_id=condition_id,
            market_slug=slug,
            market_question=question,
            market_volume_24h=volume_24h,
        )

        if alerts:
            results[slug] = alerts
            for a in alerts:
                print(f"\n{format_alert_text(a)}\n")

    total_alerts = sum(len(v) for v in results.values())
    logger.info(f"Scan complete: {total_alerts} alerts across {len(results)} markets")
    return results


if __name__ == "__main__":
    count = 5
    for arg in sys.argv[1:]:
        if arg.isdigit():
            count = int(arg)

    print(f"\n{'='*60}")
    print(f"  CASH COW INSIDER TRACKER — Scanning top {count} markets")
    print(f"{'='*60}\n")

    results = scan_trending(count)

    print(f"\n{'='*60}")
    total = sum(len(v) for v in results.values())
    print(f"  Scan complete: {total} alerts across {len(results)} markets")
    if not results:
        print("  No suspicious activity detected (this is normal)")
    print(f"{'='*60}\n")

    assert results is not None, "Scanner returned None"
    print(f"  {__file__} passed smoke test")
