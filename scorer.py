"""Unified scoring logic for Cash Cow opportunity ranking."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from math import log10
from typing import Any, Iterable, Literal, Sequence


UTC = timezone.utc


@dataclass(slots=True)
class PredictionMarketOpportunity:
    """A prediction-market opportunity with features needed for scoring."""

    id: str
    question: str
    yes_pct: float
    no_pct: float
    volume_24h: float
    description: str
    created_at: datetime | None = None
    age_hours: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class DefiYieldOpportunity:
    """A DeFi yield opportunity with features needed for scoring."""

    id: str
    protocol: str
    chain: str
    symbol: str
    apy: float
    tvl: float
    stablecoin: bool
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class RankedOpportunity:
    """A scored and normalized opportunity entry."""

    rank: int
    kind: Literal["prediction_market", "defi_yield"]
    id: str
    title: str
    raw_score: float
    cash_cow_score: float
    score_breakdown: dict[str, float]
    source_data: dict[str, Any]


@dataclass(slots=True)
class ScoredMarket:
    """Compatibility wrapper for ranked prediction markets used by orchestrators."""

    id: str
    question: str
    yes_pct: float
    no_pct: float
    volume_24h: float
    score: float
    rank: int = 0
    description: str = ""
    score_breakdown: dict[str, float] = field(default_factory=dict)
    source_data: dict[str, Any] = field(default_factory=dict)
    raw_polymarket: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Return a dashboard- and CLI-friendly serialized representation."""
        return {
            "rank": self.rank,
            "id": self.id,
            "question": self.question,
            "yes_pct": self.yes_pct,
            "no_pct": self.no_pct,
            "volume_24h": self.volume_24h,
            "description": self.description,
            "score": self.score,
            "cash_cow_score": self.score,
            "score_breakdown": self.score_breakdown,
            "source_data": self.source_data,
            "raw_polymarket": self.raw_polymarket,
        }


def parse_datetime(value: str | datetime | None) -> datetime | None:
    """Parse a flexible datetime value into an aware UTC datetime."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    parsed = datetime.fromisoformat(text)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _bounded(value: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
    """Clamp a numeric score to a bounded interval."""
    return max(minimum, min(maximum, float(value)))


def _log_scale(value: float, ceiling: float) -> float:
    """Convert a positive metric into a smoothed 0-1 score."""
    safe_value = max(0.0, float(value))
    safe_ceiling = max(1.0, float(ceiling))
    return _bounded(log10(safe_value + 1.0) / log10(safe_ceiling + 1.0))


def _description_richness(description: str) -> float:
    """Estimate content richness based on description length."""
    target = 400.0
    length = len(" ".join(description.split()))
    return _bounded(length / target)


def _market_uncertainty_score(yes_pct: float) -> float:
    """Reward prices close to 50% because they tend to be more engaging."""
    pct = _bounded(yes_pct / 100.0)
    return _bounded(1.0 - abs(pct - 0.5) / 0.5)


def _recency_score(created_at: datetime | None, age_hours: float | None) -> float:
    """Reward newer markets while keeping older but active markets viable."""
    if age_hours is None and created_at is not None:
        age_hours = max(0.0, (datetime.now(UTC) - created_at.astimezone(UTC)).total_seconds() / 3600.0)
    if age_hours is None:
        return 0.5
    return _bounded(1.0 - min(float(age_hours), 168.0) / 168.0)


def score_prediction_market(opportunity: PredictionMarketOpportunity) -> tuple[float, dict[str, float]]:
    """Score a prediction market on a 0-1 raw scale with interpretable features."""
    breakdown = {
        "volume": _log_scale(opportunity.volume_24h, 10_000_000),
        "volatility": _market_uncertainty_score(opportunity.yes_pct),
        "recency": _recency_score(opportunity.created_at, opportunity.age_hours),
        "description_richness": _description_richness(opportunity.description),
    }
    raw = (
        breakdown["volume"] * 0.35
        + breakdown["volatility"] * 0.30
        + breakdown["recency"] * 0.20
        + breakdown["description_richness"] * 0.15
    )
    return _bounded(raw), breakdown


def _chain_diversity_scores(opportunities: Sequence[DefiYieldOpportunity]) -> dict[str, float]:
    """Reward chains that appear less frequently in the candidate set."""
    if not opportunities:
        return {}
    counts: dict[str, int] = {}
    for item in opportunities:
        counts[item.chain] = counts.get(item.chain, 0) + 1
    max_count = max(counts.values())
    if max_count <= 1:
        return {chain: 1.0 for chain in counts}
    return {chain: _bounded(1.0 - (count - 1) / (max_count - 1)) for chain, count in counts.items()}


def score_defi_yield(
    opportunity: DefiYieldOpportunity,
    chain_diversity_score: float,
) -> tuple[float, dict[str, float]]:
    """Score a DeFi yield on a 0-1 raw scale with interpretable features."""
    breakdown = {
        "apy": _log_scale(opportunity.apy, 200),
        "tvl": _log_scale(opportunity.tvl, 1_000_000_000),
        "stablecoin": 1.0 if opportunity.stablecoin else 0.35,
        "chain_diversity": _bounded(chain_diversity_score),
    }
    raw = (
        breakdown["apy"] * 0.35
        + breakdown["tvl"] * 0.30
        + breakdown["stablecoin"] * 0.20
        + breakdown["chain_diversity"] * 0.15
    )
    return _bounded(raw), breakdown


def _normalize_to_100(raw_scores: Sequence[float]) -> list[float]:
    """Min-max normalize a list of scores to 0-100."""
    if not raw_scores:
        return []
    minimum = min(raw_scores)
    maximum = max(raw_scores)
    if maximum == minimum:
        return [100.0 for _ in raw_scores]
    return [round(((score - minimum) / (maximum - minimum)) * 100.0, 2) for score in raw_scores]


def _prediction_from_dict(item: dict[str, Any]) -> PredictionMarketOpportunity:
    """Create a prediction market model from a generic dictionary."""
    return PredictionMarketOpportunity(
        id=str(item.get("id") or item.get("slug") or item.get("question")),
        question=str(item["question"]),
        yes_pct=float(item.get("yes_pct", item.get("yesPrice", 0.0))),
        no_pct=float(item.get("no_pct", item.get("noPrice", 0.0))),
        volume_24h=float(item.get("volume_24h", item.get("volume24hr", item.get("volume", 0.0)))),
        description=str(item.get("description", "")),
        created_at=parse_datetime(item.get("created_at") or item.get("createdAt") or item.get("startDate")),
        age_hours=float(item["age_hours"]) if item.get("age_hours") is not None else None,
        metadata={
            k: v
            for k, v in item.items()
            if k
            not in {
                "id",
                "slug",
                "question",
                "yes_pct",
                "yesPrice",
                "no_pct",
                "noPrice",
                "volume_24h",
                "volume24hr",
                "volume",
                "description",
                "created_at",
                "createdAt",
                "startDate",
                "age_hours",
            }
        },
    )


def _defi_from_dict(item: dict[str, Any]) -> DefiYieldOpportunity:
    """Create a DeFi yield model from a generic dictionary."""
    stablecoin = item.get("stablecoin")
    if stablecoin is None:
        stablecoin = item.get("stablecoins")
    if stablecoin is None:
        stablecoin = False
    return DefiYieldOpportunity(
        id=str(item.get("id") or item.get("pool") or item.get("symbol")),
        protocol=str(item.get("protocol", item.get("project", "Unknown Protocol"))),
        chain=str(item.get("chain", "Unknown Chain")),
        symbol=str(item.get("symbol", "")),
        apy=float(item.get("apy", 0.0)),
        tvl=float(item.get("tvl", item.get("tvlUsd", item.get("tvl_usd", 0.0)))),
        stablecoin=bool(stablecoin),
        metadata={
            k: v
            for k, v in item.items()
            if k
            not in {
                "id",
                "pool",
                "protocol",
                "project",
                "chain",
                "symbol",
                "apy",
                "tvl",
                "tvlUsd",
                "tvl_usd",
                "stablecoin",
                "stablecoins",
            }
        },
    )


def rank_opportunities(
    prediction_markets: Iterable[PredictionMarketOpportunity | dict[str, Any]],
    defi_yields: Iterable[DefiYieldOpportunity | dict[str, Any]],
) -> list[RankedOpportunity]:
    """Score and rank prediction markets and DeFi yields in one normalized list."""
    pm_items = [item if isinstance(item, PredictionMarketOpportunity) else _prediction_from_dict(item) for item in prediction_markets]
    defi_items = [item if isinstance(item, DefiYieldOpportunity) else _defi_from_dict(item) for item in defi_yields]
    diversity_scores = _chain_diversity_scores(defi_items)

    provisional: list[tuple[str, str, str, float, dict[str, float], dict[str, Any]]] = []
    for item in pm_items:
        raw, breakdown = score_prediction_market(item)
        provisional.append(("prediction_market", item.id, item.question, raw, breakdown, asdict(item)))
    for item in defi_items:
        raw, breakdown = score_defi_yield(item, diversity_scores.get(item.chain, 0.5))
        provisional.append(("defi_yield", item.id, f"{item.protocol} {item.symbol} on {item.chain}", raw, breakdown, asdict(item)))

    provisional.sort(key=lambda row: row[3], reverse=True)
    normalized_scores = _normalize_to_100([row[3] for row in provisional])

    ranked: list[RankedOpportunity] = []
    for index, ((kind, item_id, title, raw, breakdown, source_data), normalized) in enumerate(
        zip(provisional, normalized_scores, strict=False),
        start=1,
    ):
        ranked.append(
            RankedOpportunity(
                rank=index,
                kind=kind,  # type: ignore[arg-type]
                id=item_id,
                title=title,
                raw_score=round(raw * 100.0, 2),
                cash_cow_score=normalized,
                score_breakdown={key: round(value * 100.0, 2) for key, value in breakdown.items()},
                source_data=source_data,
            )
        )
    return ranked


def score_single(item: dict[str, Any]) -> dict[str, Any]:
    """Score a single Polymarket-style market dictionary."""
    pm = _prediction_from_dict(item)
    raw_score, breakdown = score_prediction_market(pm)
    scored = ScoredMarket(
        id=pm.id,
        question=pm.question,
        yes_pct=pm.yes_pct,
        no_pct=pm.no_pct,
        volume_24h=pm.volume_24h,
        description=pm.description,
        score=round(raw_score * 100.0, 2),
        score_breakdown={k: round(v * 100.0, 2) for k, v in breakdown.items()},
        source_data=asdict(pm),
        raw_polymarket=item.get("raw") if isinstance(item.get("raw"), dict) else item,
    )
    return scored.to_dict()


def fetch_and_score(limit: int = 10) -> list[ScoredMarket]:
    """Fetch Polymarket markets and return ranked ``ScoredMarket`` objects."""
    try:
        from data_sources import fetch_gamma_markets
    except ImportError:
        return []

    try:
        raw_rows = fetch_gamma_markets(limit=max(25, limit * 3))
    except Exception:
        return []

    rows: list[tuple[PredictionMarketOpportunity, float, dict[str, float], dict[str, Any]]] = []
    for item in raw_rows:
        pm = _prediction_from_dict(item)
        raw_score, breakdown = score_prediction_market(pm)
        gamma_raw = item.get("raw") if isinstance(item.get("raw"), dict) else item
        rows.append((pm, raw_score, breakdown, gamma_raw if isinstance(gamma_raw, dict) else {}))

    rows.sort(key=lambda r: r[1], reverse=True)
    normalized = _normalize_to_100([r[1] for r in rows])

    result: list[ScoredMarket] = []
    for i, (((pm, raw_score, breakdown, gamma_raw), cc_score)) in enumerate(
        zip(rows, normalized, strict=False),
        start=1,
    ):
        if i > limit:
            break
        result.append(
            ScoredMarket(
                rank=i,
                id=pm.id,
                question=pm.question,
                yes_pct=pm.yes_pct,
                no_pct=pm.no_pct,
                volume_24h=pm.volume_24h,
                description=pm.description,
                score=cc_score,
                score_breakdown={k: round(v * 100.0, 2) for k, v in breakdown.items()},
                source_data=asdict(pm),
                raw_polymarket=gamma_raw,
            )
        )
    return result


def top_markets(n: int = 10) -> list[dict[str, Any]]:
    """Return serialized top-ranked markets for dashboards, CLIs, and APIs."""
    return [market.to_dict() for market in fetch_and_score(limit=n)]


if __name__ == "__main__":
    prediction_samples = [
        {
            "id": "btc-200k",
            "question": "Will Bitcoin reach $200k by year end?",
            "yes_pct": 52.0,
            "no_pct": 48.0,
            "volume_24h": 3_500_000,
            "description": "A high-attention crypto market driven by ETF demand, macro liquidity, and trader sentiment.",
            "age_hours": 12,
        },
        {
            "id": "fed-cut",
            "question": "Will the Fed cut rates in June?",
            "yes_pct": 74.0,
            "no_pct": 26.0,
            "volume_24h": 950_000,
            "description": "A macro policy market that reacts to CPI, labor data, and central bank signaling.",
            "age_hours": 48,
        },
    ]
    defi_samples = [
        {
            "id": "aave-usdc",
            "protocol": "Aave",
            "chain": "Ethereum",
            "symbol": "USDC",
            "apy": 9.8,
            "tvl": 420_000_000,
            "stablecoin": True,
        },
        {
            "id": "pendle-eth",
            "protocol": "Pendle",
            "chain": "Arbitrum",
            "symbol": "ETH",
            "apy": 18.4,
            "tvl": 58_000_000,
            "stablecoin": False,
        },
    ]
    for item in rank_opportunities(prediction_samples, defi_samples):
        print(item)
