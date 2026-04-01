"""Detection algorithms for insider trading signals.

Ported from polymarket-insider-tracker with the same thresholds and
scoring logic, but without Redis/Postgres dependencies.

Three detectors:
    - Fresh wallet: brand-new wallets making large trades
    - Size anomaly: trades disproportionately large for the market
    - Risk scorer: combines signals with weighted scoring
"""
from __future__ import annotations

from typing import Any

from loguru import logger

from insider.models import (
    InsiderSignal,
    RiskAssessment,
    RiskLevel,
    SignalType,
    TradeInfo,
    WalletProfile,
)

# ---------------------------------------------------------------------------
# Thresholds (from upstream polymarket-insider-tracker)
# ---------------------------------------------------------------------------
FRESH_WALLET_MAX_NONCE = 5
FRESH_WALLET_MAX_AGE_HOURS = 48
FRESH_WALLET_MIN_TRADE_USD = 1_000

SIZE_ANOMALY_VOLUME_IMPACT_THRESHOLD = 0.02  # 2% of daily volume
SIZE_ANOMALY_NICHE_VOLUME_THRESHOLD = 50_000  # < $50k daily = niche

# Scoring weights
WEIGHT_FRESH_WALLET = 0.40
WEIGHT_SIZE_ANOMALY = 0.35
WEIGHT_NICHE_MARKET = 0.25
MULTI_SIGNAL_BONUS_2 = 1.2
MULTI_SIGNAL_BONUS_3 = 1.3
ALERT_THRESHOLD = 0.6


def detect_fresh_wallet(
    trade: TradeInfo,
    profile: WalletProfile,
) -> InsiderSignal | None:
    """Detect if a trade comes from a suspiciously fresh wallet.

    A fresh wallet is one with very few transactions making a large trade,
    suggesting the trader created a new wallet to hide their identity.

    Args:
        trade: The trade event.
        profile: On-chain wallet profile.

    Returns:
        InsiderSignal if fresh wallet detected, None otherwise.
    """
    if profile.nonce < 0:
        return None  # profiling failed

    if profile.nonce > FRESH_WALLET_MAX_NONCE:
        return None

    if trade.size < FRESH_WALLET_MIN_TRADE_USD:
        return None

    # Calculate confidence
    confidence = 0.5  # base

    if profile.nonce == 0:
        confidence += 0.2  # brand new wallet
    elif profile.nonce <= 2:
        confidence += 0.1

    if profile.age_hours < 2:
        confidence += 0.1  # very recent
    elif profile.age_hours < 24:
        confidence += 0.05

    if trade.size > 10_000:
        confidence += 0.1  # large trade
    elif trade.size > 5_000:
        confidence += 0.05

    confidence = min(confidence, 1.0)

    logger.info(
        f"Fresh wallet signal: {trade.wallet_address[:10]}... "
        f"nonce={profile.nonce}, size=${trade.size:,.0f}, conf={confidence:.2f}"
    )

    return InsiderSignal(
        signal_type=SignalType.FRESH_WALLET,
        confidence=confidence,
        wallet_address=trade.wallet_address,
        market_id=trade.market_id,
        market_slug=trade.market_slug,
        details={
            "nonce": profile.nonce,
            "age_hours": round(profile.age_hours, 1),
            "trade_size": trade.size,
            "matic_balance": round(profile.matic_balance, 4),
        },
    )


def detect_size_anomaly(
    trade: TradeInfo,
    market_volume_24h: float,
) -> InsiderSignal | None:
    """Detect if a trade is anomalously large relative to market volume.

    Informed traders bet bigger when they have edge. This detector flags
    trades that consume a significant portion of market liquidity.

    Args:
        trade: The trade event.
        market_volume_24h: The market's 24-hour trading volume in USD.

    Returns:
        InsiderSignal if size anomaly detected, None otherwise.
    """
    if market_volume_24h <= 0:
        return None

    volume_impact = trade.size / market_volume_24h
    is_niche = market_volume_24h < SIZE_ANOMALY_NICHE_VOLUME_THRESHOLD

    if volume_impact < SIZE_ANOMALY_VOLUME_IMPACT_THRESHOLD and not is_niche:
        return None

    # Calculate confidence
    confidence = min(volume_impact * 10, 0.6)  # scale: 2% impact → 0.2 conf

    if is_niche:
        confidence *= 1.5  # niche market multiplier
        confidence = min(confidence, 0.95)

    if trade.size > 10_000:
        confidence = min(confidence + 0.1, 1.0)

    confidence = min(confidence, 1.0)

    if confidence < 0.2:
        return None  # below minimum signal threshold

    logger.info(
        f"Size anomaly signal: ${trade.size:,.0f} on {trade.market_slug[:30]} "
        f"impact={volume_impact:.1%}, niche={is_niche}, conf={confidence:.2f}"
    )

    return InsiderSignal(
        signal_type=SignalType.SIZE_ANOMALY,
        confidence=confidence,
        wallet_address=trade.wallet_address,
        market_id=trade.market_id,
        market_slug=trade.market_slug,
        details={
            "trade_size": trade.size,
            "market_volume_24h": market_volume_24h,
            "volume_impact": round(volume_impact, 4),
            "is_niche_market": is_niche,
        },
    )


def score_risk(
    signals: list[InsiderSignal],
    trade: TradeInfo,
    market_question: str = "",
) -> RiskAssessment:
    """Combine multiple signals into a unified risk assessment.

    Applies weighted scoring with multi-signal bonuses, matching the
    upstream polymarket-insider-tracker formula.

    Args:
        signals: List of detected InsiderSignals for this trade.
        trade: The original trade event.
        market_question: Human-readable market question.

    Returns:
        RiskAssessment with combined score and alert decision.
    """
    if not signals:
        return RiskAssessment(
            wallet_address=trade.wallet_address,
            market_id=trade.market_id,
            market_slug=trade.market_slug,
            market_question=market_question,
            trade_size=trade.size,
            trade_side=trade.side,
            trade_price=trade.price,
        )

    score = 0.0
    has_niche = False

    for signal in signals:
        if signal.signal_type == SignalType.FRESH_WALLET:
            score += signal.confidence * WEIGHT_FRESH_WALLET
        elif signal.signal_type == SignalType.SIZE_ANOMALY:
            score += signal.confidence * WEIGHT_SIZE_ANOMALY
            if signal.details.get("is_niche_market"):
                has_niche = True
                score += signal.confidence * WEIGHT_NICHE_MARKET

    # Multi-signal bonus
    n = len(signals)
    if n >= 3:
        score *= MULTI_SIGNAL_BONUS_3
    elif n >= 2:
        score *= MULTI_SIGNAL_BONUS_2

    score = min(score, 1.0)

    # Determine risk level
    if score >= 0.8:
        risk_level = RiskLevel.CRITICAL
    elif score >= 0.6:
        risk_level = RiskLevel.HIGH
    elif score >= 0.4:
        risk_level = RiskLevel.MEDIUM
    else:
        risk_level = RiskLevel.LOW

    should_alert = score >= ALERT_THRESHOLD

    return RiskAssessment(
        wallet_address=trade.wallet_address,
        market_id=trade.market_id,
        market_slug=trade.market_slug,
        market_question=market_question,
        signals=signals,
        weighted_score=score,
        risk_level=risk_level,
        should_alert=should_alert,
        trade_size=trade.size,
        trade_side=trade.side,
        trade_price=trade.price,
    )


if __name__ == "__main__":
    from datetime import datetime, timezone

    # Smoke test
    trade = TradeInfo(
        trade_id="test-1",
        market_id="0xabc",
        market_slug="test-market",
        wallet_address="0x1234567890abcdef",
        side="BUY",
        outcome="Yes",
        price=0.075,
        size=15_000,
        timestamp=datetime.now(timezone.utc),
    )
    profile = WalletProfile(
        address="0x1234567890abcdef",
        nonce=2,
        age_hours=1.5,
        matic_balance=0.1,
        is_fresh=True,
    )

    sig1 = detect_fresh_wallet(trade, profile)
    sig2 = detect_size_anomaly(trade, market_volume_24h=40_000)
    signals = [s for s in [sig1, sig2] if s is not None]
    assessment = score_risk(signals, trade, "Will X happen?")

    assert assessment is not None
    print(f"  {__file__} passed smoke test")
    print(f"  Signals: {assessment.signals_triggered}")
    print(f"  Score: {assessment.weighted_score:.2f}")
    print(f"  Risk: {assessment.risk_level}")
    print(f"  Alert: {assessment.should_alert}")
