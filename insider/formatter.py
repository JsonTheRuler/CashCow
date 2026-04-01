"""Format insider alerts for video scripts, logs, and display.

Generates both human-readable alert text and viral video hooks
that can be injected into MoneyPrinterTurbo video topics.
"""
from __future__ import annotations

from insider.models import RiskAssessment, RiskLevel


def format_alert_text(assessment: RiskAssessment) -> str:
    """Format a risk assessment as a human-readable alert.

    Args:
        assessment: The risk assessment to format.

    Returns:
        Multi-line alert string suitable for logging or display.
    """
    risk_emoji = {
        RiskLevel.LOW: "[LOW]",
        RiskLevel.MEDIUM: "[MEDIUM]",
        RiskLevel.HIGH: "[HIGH]",
        RiskLevel.CRITICAL: "[CRITICAL]",
    }
    header = f"SUSPICIOUS ACTIVITY DETECTED {risk_emoji.get(assessment.risk_level, '')}"

    lines = [
        header,
        "",
        f"Wallet: {assessment.wallet_address[:10]}...{assessment.wallet_address[-4:]}",
        f"Market: {assessment.market_question[:80]}",
        f"Action: {assessment.trade_side} {'YES' if assessment.trade_price > 0.5 else 'NO'} @ ${assessment.trade_price:.3f}",
        f"Size: ${assessment.trade_size:,.0f} USDC",
        "",
        "Risk Signals:",
    ]

    for signal in assessment.signals:
        details_str = ", ".join(f"{k}={v}" for k, v in signal.details.items())
        lines.append(f"  [x] {signal.signal_type.value} (conf: {signal.confidence:.2f}) {details_str}")

    lines.extend([
        "",
        f"Confidence: {assessment.risk_level.value.upper()} ({assessment.signals_triggered}/{3} signals triggered)",
        f"Weighted Score: {assessment.weighted_score:.2f}",
    ])

    return "\n".join(lines)


def format_video_hook(assessment: RiskAssessment) -> str:
    """Generate a viral video hook sentence from an insider alert.

    This hook gets prepended to the video topic to make the content
    more engaging and clickable.

    Args:
        assessment: The risk assessment to generate a hook for.

    Returns:
        Single attention-grabbing sentence for the video intro.
    """
    wallet_short = f"{assessment.wallet_address[:6]}...{assessment.wallet_address[-4:]}"
    size_str = f"${assessment.trade_size:,.0f}"

    if assessment.risk_level == RiskLevel.CRITICAL:
        return (
            f"ALERT: A brand-new wallet just dropped {size_str} on this market. "
            f"Insider trading or someone who knows something we don't?"
        )

    if assessment.risk_level == RiskLevel.HIGH:
        return (
            f"Suspicious activity detected: wallet {wallet_short} placed a "
            f"{size_str} bet. This wallet has almost no transaction history."
        )

    # MEDIUM
    return (
        f"Whale alert: a {size_str} trade just hit this market "
        f"from a low-activity wallet. Smart money is moving."
    )


def format_state_entry(assessment: RiskAssessment) -> dict:
    """Format a risk assessment for state.json persistence.

    Args:
        assessment: The risk assessment to serialize.

    Returns:
        Dict suitable for JSON serialization.
    """
    return {
        "wallet": assessment.wallet_address,
        "market_id": assessment.market_id,
        "market_slug": assessment.market_slug,
        "market_question": assessment.market_question[:100],
        "trade_size": assessment.trade_size,
        "trade_side": assessment.trade_side,
        "trade_price": assessment.trade_price,
        "risk_level": assessment.risk_level.value,
        "weighted_score": round(assessment.weighted_score, 3),
        "signals": assessment.signal_types,
        "should_alert": assessment.should_alert,
        "assessed_at": assessment.assessed_at.isoformat(),
    }


if __name__ == "__main__":
    from datetime import datetime, timezone
    from insider.models import InsiderSignal, SignalType

    assessment = RiskAssessment(
        wallet_address="0x7a3b8c9d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a91",
        market_id="0xabc123",
        market_slug="will-x-announce-y",
        market_question="Will X announce Y by March 2026?",
        signals=[
            InsiderSignal(
                signal_type=SignalType.FRESH_WALLET,
                confidence=0.8,
                wallet_address="0x7a3b8c9d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a91",
                market_id="0xabc123",
                market_slug="will-x-announce-y",
                details={"nonce": 2, "age_hours": 1.5, "trade_size": 15000},
            ),
        ],
        weighted_score=0.72,
        risk_level=RiskLevel.HIGH,
        should_alert=True,
        trade_size=15_000,
        trade_side="BUY",
        trade_price=0.075,
        assessed_at=datetime.now(timezone.utc),
    )

    print(format_alert_text(assessment))
    print()
    print("Video hook:", format_video_hook(assessment))
    print()
    print(f"  {__file__} passed smoke test")
