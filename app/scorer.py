"""Cash Cow Score -- unified 0-100 ranking for prediction markets and DeFi yields.

Ranks both asset classes on a single scale so the content team always knows
what to cover next.  Higher score = more video-worthy.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from enum import Enum
from typing import Literal, Sequence

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MAX_APY_CAP = 50.0  # APY above this is treated as suspicious
_URGENCY_DAYS = 7
_URGENCY_MULTIPLIER = 1.5
_CHAIN_DIVERSITY_PENALTY = 0.20  # -20 % for overrepresented chain
_CHAIN_DIVERSITY_THRESHOLD = 2  # trigger after this many same-chain picks
_STABLECOIN_BONUS = 15.0
_MAX_QUESTION_LEN = 120  # chars -- shorter is better for video titles


# ---------------------------------------------------------------------------
# Enums & value objects
# ---------------------------------------------------------------------------

class Priority(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class VideoVibe(str, Enum):
    BREAKING_NEWS = "Breaking News"
    DEEP_ANALYSIS = "Deep Analysis"
    HOT_TAKE = "Hot Take"
    EXPLAINER = "Explainer"


Category = Literal["prediction", "yield"]


# ---------------------------------------------------------------------------
# Input dataclasses (frozen / immutable)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PredictionMarket:
    """Raw prediction-market data coming from upstream fetchers."""
    question: str
    yes_pct: float  # 0-100
    volume_24h: float  # USD
    end_date: datetime  # timezone-aware
    source: str = "polymarket"


@dataclass(frozen=True)
class DeFiYield:
    """Raw DeFi yield opportunity."""
    protocol: str
    asset: str
    apy: float  # percentage, e.g. 14.2
    tvl: float  # USD
    chain: str
    is_stablecoin: bool = False


# ---------------------------------------------------------------------------
# Scored output
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ScoredItem:
    """Unified scored item ready for the content pipeline."""
    title: str
    score: float  # 0-100
    category: Category
    priority: Priority
    vibe: VideoVibe
    raw_components: dict[str, float]  # transparency: show sub-scores
    social_score: float = 5.0  # neutral default, overridden by sentiment.py
    forecast_trend: float | None = None  # from TimesFM integration


# ---------------------------------------------------------------------------
# Scoring helpers (pure functions)
# ---------------------------------------------------------------------------

def _controversy_score(yes_pct: float) -> float:
    """50/50 splits score 100; extreme outcomes score near 0."""
    distance = abs(yes_pct - 50.0)
    # distance 0 -> 100, distance 50 -> 0
    return max(0.0, 100.0 - distance * 2.0)


def _volume_score(volume_24h: float) -> float:
    """Log-scaled volume so whales don't dominate.

    $1M  -> ~60, $10M -> ~70, $100M -> ~80.
    """
    if volume_24h <= 0:
        return 0.0
    raw = math.log10(volume_24h)
    # normalize: log10(1k)=3 -> 0, log10(1B)=9 -> 100
    return max(0.0, min(100.0, (raw - 3.0) / 6.0 * 100.0))


def _time_pressure(end_date: datetime, now: datetime | None = None) -> float:
    """Markets ending within 7 days get a 1.5x multiplier on a base of 50."""
    now = now or datetime.now(timezone.utc)
    days_left = (end_date - now).total_seconds() / 86400.0
    if days_left <= 0:
        return 100.0  # already expired -- extremely urgent
    if days_left <= _URGENCY_DAYS:
        # linear ramp inside the 7-day window, then apply multiplier
        base = (1.0 - days_left / _URGENCY_DAYS) * 66.7  # max base ~67
        return min(100.0, base * _URGENCY_MULTIPLIER)
    # gentle decay for longer-dated markets
    return max(0.0, 50.0 * math.exp(-0.05 * (days_left - _URGENCY_DAYS)))


def _clarity_score(question: str) -> float:
    """Shorter, punchier questions score higher."""
    length = len(question)
    if length <= 30:
        return 100.0
    if length >= _MAX_QUESTION_LEN:
        return 20.0
    # linear interpolation
    return 100.0 - (length - 30) / (_MAX_QUESTION_LEN - 30) * 80.0


def _apy_score(apy: float) -> float:
    """Log-scaled APY, capped at 50 %."""
    capped = min(apy, _MAX_APY_CAP)
    if capped <= 0:
        return 0.0
    # log1p to handle small values; normalize so 50 % -> 100
    return min(100.0, math.log1p(capped) / math.log1p(_MAX_APY_CAP) * 100.0)


def _tvl_score(tvl: float) -> float:
    """log10(tvl) normalized.  $100M -> ~73, $1B -> ~82."""
    if tvl <= 0:
        return 0.0
    raw = math.log10(tvl)
    # normalize: log10(1M)=6 -> 0, log10(100B)=11 -> 100
    return max(0.0, min(100.0, (raw - 6.0) / 5.0 * 100.0))


def _chain_diversity_penalty(
    chain: str,
    chain_counts: dict[str, int],
) -> float:
    """Returns a multiplier (0.0-1.0).  Penalizes overrepresented chains."""
    count = chain_counts.get(chain.lower(), 0)
    if count >= _CHAIN_DIVERSITY_THRESHOLD:
        return 1.0 - _CHAIN_DIVERSITY_PENALTY
    return 1.0


# ---------------------------------------------------------------------------
# Priority & vibe assignment (pure)
# ---------------------------------------------------------------------------

def _assign_priority(score: float) -> Priority:
    if score >= 80:
        return Priority.CRITICAL
    if score >= 60:
        return Priority.HIGH
    if score >= 40:
        return Priority.MEDIUM
    return Priority.LOW


def _assign_vibe_prediction(
    controversy: float,
    time_pressure_val: float,
) -> VideoVibe:
    if time_pressure_val >= 70:
        return VideoVibe.BREAKING_NEWS
    if controversy >= 80:
        return VideoVibe.HOT_TAKE
    if controversy >= 50:
        return VideoVibe.DEEP_ANALYSIS
    return VideoVibe.EXPLAINER


def _assign_vibe_yield(apy: float, tvl: float) -> VideoVibe:
    if apy >= 30:
        return VideoVibe.HOT_TAKE
    if tvl >= 1_000_000_000:
        return VideoVibe.DEEP_ANALYSIS
    if apy >= 10:
        return VideoVibe.BREAKING_NEWS
    return VideoVibe.EXPLAINER


# ---------------------------------------------------------------------------
# Main scoring functions
# ---------------------------------------------------------------------------

def score_prediction_market(
    market: PredictionMarket,
    now: datetime | None = None,
) -> ScoredItem:
    """Score a single prediction market on 0-100."""
    controversy = _controversy_score(market.yes_pct)
    volume = _volume_score(market.volume_24h)
    pressure = _time_pressure(market.end_date, now=now)
    clarity = _clarity_score(market.question)

    raw = (
        controversy * 0.35
        + volume * 0.30
        + pressure * 0.20
        + clarity * 0.15
    )
    score = max(0.0, min(100.0, raw))

    return ScoredItem(
        title=market.question,
        score=round(score, 2),
        category="prediction",
        priority=_assign_priority(score),
        vibe=_assign_vibe_prediction(controversy, pressure),
        raw_components={
            "controversy": round(controversy, 2),
            "volume": round(volume, 2),
            "time_pressure": round(pressure, 2),
            "clarity": round(clarity, 2),
        },
    )


def score_defi_yield(
    pool: DeFiYield,
    chain_counts: dict[str, int] | None = None,
) -> ScoredItem:
    """Score a single DeFi yield opportunity on 0-100."""
    chain_counts = chain_counts or {}

    apy_s = _apy_score(pool.apy)
    tvl_s = _tvl_score(pool.tvl)
    stable_bonus = _STABLECOIN_BONUS if pool.is_stablecoin else 0.0
    diversity_mult = _chain_diversity_penalty(pool.chain, chain_counts)

    raw = (
        apy_s * 0.35
        + tvl_s * 0.30
        + stable_bonus * 0.20
        + 100.0 * diversity_mult * 0.15  # full marks if no penalty
    )
    score = max(0.0, min(100.0, raw))

    return ScoredItem(
        title=f"{pool.protocol} {pool.asset} ({pool.chain})",
        score=round(score, 2),
        category="yield",
        priority=_assign_priority(score),
        vibe=_assign_vibe_yield(pool.apy, pool.tvl),
        raw_components={
            "apy_score": round(apy_s, 2),
            "tvl_score": round(tvl_s, 2),
            "stable_bonus": round(stable_bonus, 2),
            "chain_diversity_mult": round(diversity_mult, 2),
        },
    )


# ---------------------------------------------------------------------------
# Unified ranking
# ---------------------------------------------------------------------------

def rank_all(
    markets: Sequence[PredictionMarket],
    yields: Sequence[DeFiYield],
    now: datetime | None = None,
) -> list[ScoredItem]:
    """Score everything, normalize to 0-100, and return a sorted list.

    Chain diversity is computed incrementally: yields are pre-sorted by raw
    score (without penalty), then the penalty is applied as each chain
    accumulates picks.
    """
    scored: list[ScoredItem] = []

    # -- prediction markets (no inter-item dependency) --
    for m in markets:
        scored.append(score_prediction_market(m, now=now))

    # -- DeFi yields (chain diversity is cumulative) --
    # First pass: score without diversity penalty to get a rough ordering
    raw_yield_scores: list[tuple[float, DeFiYield]] = []
    for pool in yields:
        preliminary = score_defi_yield(pool, chain_counts={})
        raw_yield_scores.append((preliminary.score, pool))
    raw_yield_scores.sort(key=lambda t: t[0], reverse=True)

    # Second pass: apply chain diversity penalty in rank order
    chain_counts: dict[str, int] = {}
    for _, pool in raw_yield_scores:
        item = score_defi_yield(pool, chain_counts=chain_counts)
        scored.append(item)
        chain_counts[pool.chain.lower()] = chain_counts.get(pool.chain.lower(), 0) + 1

    # -- normalize across both categories --
    if scored:
        max_score = max(item.score for item in scored)
        min_score = min(item.score for item in scored)
        spread = max_score - min_score if max_score != min_score else 1.0
        scored = [
            replace(
                item,
                score=round((item.score - min_score) / spread * 100.0, 2),
                priority=_assign_priority((item.score - min_score) / spread * 100.0),
            )
            for item in scored
        ]

    scored.sort(key=lambda item: item.score, reverse=True)
    return scored


# ---------------------------------------------------------------------------
# Pretty printer
# ---------------------------------------------------------------------------

def print_rankings(items: Sequence[ScoredItem]) -> None:
    """Human-readable ranking table for the terminal."""
    print(f"\n{'='*80}")
    print(f"{'CASH COW RANKINGS':^80}")
    print(f"{'='*80}")
    print(
        f"{'#':<4} {'Score':<8} {'Priority':<10} {'Category':<12} "
        f"{'Vibe':<18} {'Title'}"
    )
    print(f"{'-'*80}")
    for i, item in enumerate(items, 1):
        print(
            f"{i:<4} {item.score:<8.1f} {item.priority.value:<10} "
            f"{item.category:<12} {item.vibe.value:<18} {item.title}"
        )
    print(f"{'='*80}\n")


# ---------------------------------------------------------------------------
# Test block
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    now = datetime(2026, 4, 1, tzinfo=timezone.utc)

    sample_markets = [
        PredictionMarket(
            question="Will Bitcoin reach $150k?",
            yes_pct=42.0,
            volume_24h=8_200_000,
            end_date=datetime(2026, 12, 31, tzinfo=timezone.utc),
        ),
        PredictionMarket(
            question="Will Fed cut rates in June?",
            yes_pct=67.0,
            volume_24h=5_100_000,
            end_date=datetime(2026, 6, 30, tzinfo=timezone.utc),
        ),
    ]

    sample_yields = [
        DeFiYield(
            protocol="Aave",
            asset="USDC",
            apy=14.2,
            tvl=890_000_000,
            chain="Ethereum",
            is_stablecoin=True,
        ),
        DeFiYield(
            protocol="Morpho",
            asset="USDC",
            apy=18.5,
            tvl=340_000_000,
            chain="Base",
            is_stablecoin=True,
        ),
    ]

    rankings = rank_all(sample_markets, sample_yields, now=now)
    print_rankings(rankings)

    # detailed breakdown
    for item in rankings:
        print(f"\n{item.title}")
        print(f"  Final Score : {item.score}")
        print(f"  Priority    : {item.priority.value}")
        print(f"  Vibe        : {item.vibe.value}")
        print(f"  Components  : {item.raw_components}")
