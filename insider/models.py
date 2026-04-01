"""Data models for the insider tracker.

Pure dataclasses — no Pydantic, no SQLAlchemy, no external deps.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any


class SignalType(StrEnum):
    """Types of insider trading signals."""

    FRESH_WALLET = "fresh_wallet"
    SIZE_ANOMALY = "size_anomaly"
    NICHE_MARKET = "niche_market"


class RiskLevel(StrEnum):
    """Risk level classification."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass(frozen=True)
class TradeInfo:
    """A single trade event from the CLOB API."""

    trade_id: str
    market_id: str
    market_slug: str
    wallet_address: str
    side: str  # "BUY" or "SELL"
    outcome: str  # "Yes" or "No"
    price: float  # 0.0 to 1.0
    size: float  # USDC amount
    timestamp: datetime


@dataclass
class WalletProfile:
    """On-chain profile of a wallet address."""

    address: str
    nonce: int  # transaction count
    age_hours: float  # wallet age in hours
    matic_balance: float = 0.0
    usdc_balance: float = 0.0
    is_fresh: bool = False  # nonce <= 5 and age <= 48h
    analyzed_at: datetime = field(default_factory=datetime.now)


@dataclass(frozen=True)
class InsiderSignal:
    """A single detection signal from one of the detectors."""

    signal_type: SignalType
    confidence: float  # 0.0 to 1.0
    wallet_address: str
    market_id: str
    market_slug: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class RiskAssessment:
    """Combined risk assessment for a trade/wallet on a market."""

    wallet_address: str
    market_id: str
    market_slug: str
    market_question: str
    signals: list[InsiderSignal] = field(default_factory=list)
    weighted_score: float = 0.0
    risk_level: RiskLevel = RiskLevel.LOW
    should_alert: bool = False
    trade_size: float = 0.0
    trade_side: str = ""
    trade_price: float = 0.0
    assessed_at: datetime = field(default_factory=datetime.now)

    @property
    def signals_triggered(self) -> int:
        """Number of signals that fired."""
        return len(self.signals)

    @property
    def signal_types(self) -> list[str]:
        """List of signal type names."""
        return [s.signal_type.value for s in self.signals]
