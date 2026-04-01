"""Sentiment integration -- merges Grok's social intel into Cash Cow scores.

Reads ``social_intel_report.md`` (produced by Grok), extracts divergence
alerts and hook templates, and produces a per-market social score that gets
folded into the main ranking.

Also contains a concrete integration sketch for Google's TimesFM forecasting
model to add a ``forecast_trend`` signal to each market.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Sequence

from app.scorer import ScoredItem

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_DEFAULT_SOCIAL_SCORE = 5.0  # neutral when no intel is available
_REPORT_FILENAME = "social_intel_report.md"
_REPORT_SEARCH_DIRS = (
    Path.home() / "cashcow",
    Path.home() / "cashcow" / "data",
    Path.home() / "cashcow" / "app",
    Path.cwd(),
)


# ---------------------------------------------------------------------------
# Parsed data structures (frozen / immutable)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class DivergenceAlert:
    """A market where X sentiment diverges from the prediction-market price."""
    market_title: str
    market_pct: float  # prediction-market YES %
    social_pct: float  # X crowd sentiment %
    divergence: float  # absolute difference
    direction: str  # "bullish" | "bearish"
    confidence: float  # 0-1


@dataclass(frozen=True)
class HookTemplate:
    """A ready-to-use video hook parsed from the social intel report."""
    market_title: str
    hook_text: str
    tone: str  # "controversial", "urgent", "explainer", etc.


@dataclass(frozen=True)
class SocialIntelReport:
    """Complete parsed social intelligence report."""
    divergence_alerts: list[DivergenceAlert]
    hook_templates: list[HookTemplate]
    raw_text: str


# ---------------------------------------------------------------------------
# Report locator
# ---------------------------------------------------------------------------

def _find_report() -> Path | None:
    """Search known directories for the social intel report."""
    for directory in _REPORT_SEARCH_DIRS:
        candidate = directory / _REPORT_FILENAME
        if candidate.is_file():
            logger.info("Found social intel report at %s", candidate)
            return candidate
    return None


# ---------------------------------------------------------------------------
# Parsers (pure functions operating on text)
# ---------------------------------------------------------------------------

_DIVERGENCE_PATTERN = re.compile(
    r"(?i)\*?\*?divergence\*?\*?[:\s]+"
    r"(?P<title>.+?)\s*"
    r"[-–—]\s*"
    r"market\s*:?\s*(?P<market_pct>[\d.]+)%?\s*"
    r"(?:vs\.?|versus)\s*"
    r"(?:social|x|twitter)\s*:?\s*(?P<social_pct>[\d.]+)%?\s*"
    r"(?:\((?P<direction>bullish|bearish)\))?\s*"
    r"(?:confidence\s*:?\s*(?P<confidence>[\d.]+))?",
)

_HOOK_PATTERN = re.compile(
    r"(?i)(?:\*\*hook\*\*|hook)[:\s]+\"(?P<hook>.+?)\"\s*"
    r"(?:\((?P<tone>\w+)\))?\s*"
    r"(?:[-–—]\s*(?:for|market)[:\s]*(?P<title>.+?))?$",
    re.MULTILINE,
)


def _parse_divergence_alerts(text: str) -> list[DivergenceAlert]:
    """Extract divergence alerts from markdown text."""
    alerts: list[DivergenceAlert] = []
    for match in _DIVERGENCE_PATTERN.finditer(text):
        market_pct = float(match.group("market_pct"))
        social_pct = float(match.group("social_pct"))
        alerts.append(
            DivergenceAlert(
                market_title=match.group("title").strip(),
                market_pct=market_pct,
                social_pct=social_pct,
                divergence=abs(market_pct - social_pct),
                direction=match.group("direction") or (
                    "bullish" if social_pct > market_pct else "bearish"
                ),
                confidence=float(match.group("confidence") or 0.7),
            )
        )
    return alerts


def _parse_hook_templates(text: str) -> list[HookTemplate]:
    """Extract video hook templates from markdown text."""
    hooks: list[HookTemplate] = []
    for match in _HOOK_PATTERN.finditer(text):
        hooks.append(
            HookTemplate(
                market_title=(match.group("title") or "").strip(),
                hook_text=match.group("hook").strip(),
                tone=(match.group("tone") or "neutral").strip().lower(),
            )
        )
    return hooks


def parse_social_intel(text: str) -> SocialIntelReport:
    """Parse the complete social intel report."""
    return SocialIntelReport(
        divergence_alerts=_parse_divergence_alerts(text),
        hook_templates=_parse_hook_templates(text),
        raw_text=text,
    )


# ---------------------------------------------------------------------------
# Social scoring
# ---------------------------------------------------------------------------

def _social_score_from_divergence(
    title: str,
    alerts: Sequence[DivergenceAlert],
) -> float:
    """Compute a 0-10 social score for a market title.

    Higher divergence + higher confidence = higher score (more video-worthy).
    Returns the default neutral score if no matching alert is found.
    """
    title_lower = title.lower()
    best_score = _DEFAULT_SOCIAL_SCORE

    for alert in alerts:
        # fuzzy title match: check if key words overlap
        alert_words = set(alert.market_title.lower().split())
        title_words = set(title_lower.split())
        overlap = len(alert_words & title_words)
        if overlap < 2 and alert.market_title.lower() not in title_lower:
            continue

        # divergence 0 -> 5, divergence 30+ -> 10
        div_component = min(10.0, 5.0 + alert.divergence / 6.0)
        # weight by confidence
        score = div_component * alert.confidence
        best_score = max(best_score, score)

    return round(min(10.0, best_score), 2)


def compute_social_scores(
    items: Sequence[ScoredItem],
    report: SocialIntelReport | None = None,
) -> list[ScoredItem]:
    """Attach social_score to each scored item.

    If no report is available, every item gets the neutral default (5.0).
    """
    if report is None:
        return [replace(item, social_score=_DEFAULT_SOCIAL_SCORE) for item in items]

    return [
        replace(
            item,
            social_score=_social_score_from_divergence(
                item.title, report.divergence_alerts
            ),
        )
        for item in items
    ]


# ---------------------------------------------------------------------------
# Full pipeline: load report -> merge into rankings
# ---------------------------------------------------------------------------

def load_and_merge(
    items: Sequence[ScoredItem],
    report_path: Path | str | None = None,
) -> list[ScoredItem]:
    """End-to-end: find/load the social intel report, score, and merge.

    The social score is blended into the final score with a 10 % weight,
    re-scaling the original score to 90 % so the total stays at 100.
    """
    path = Path(report_path) if report_path else _find_report()
    report: SocialIntelReport | None = None

    if path and path.is_file():
        logger.info("Loading social intel from %s", path)
        text = path.read_text(encoding="utf-8")
        report = parse_social_intel(text)
        logger.info(
            "Parsed %d divergence alerts, %d hook templates",
            len(report.divergence_alerts),
            len(report.hook_templates),
        )
    else:
        logger.info(
            "social_intel_report.md not found -- using neutral scores"
        )

    scored = compute_social_scores(items, report)

    # blend: 90% original score + 10% social (scaled to 0-100)
    blended: list[ScoredItem] = []
    for item in scored:
        new_score = round(item.score * 0.90 + item.social_score * 10.0 * 0.10, 2)
        new_score = max(0.0, min(100.0, new_score))
        blended.append(replace(item, score=new_score))

    blended.sort(key=lambda x: x.score, reverse=True)
    return blended


# ---------------------------------------------------------------------------
# TimesFM integration sketch
# ---------------------------------------------------------------------------

def _timesfm_forecast_stub(
    historical_prices: Sequence[float],
    horizon: int = 7,
) -> dict[str, object]:
    """Concrete integration sketch for TimesFM 2.5.

    This function shows exactly how to wire up the locally-installed
    TimesFM (~/timesfm) to produce a forecast_trend signal for each market.

    Returns a dict with:
      - point_forecast: list of predicted values
      - quantiles: uncertainty bands
      - trend_signal: float in [-1, 1] where positive = bullish

    USAGE (when TimesFM dependencies are satisfied):
    -----------------------------------------------
    import sys
    sys.path.insert(0, str(Path.home() / "timesfm" / "src"))

    import numpy as np
    from timesfm import TimesFM_2p5_200M_torch, ForecastConfig

    # 1. Load pre-trained model from HuggingFace Hub cache
    model = TimesFM_2p5_200M_torch.from_pretrained(
        "google/timesfm-2.5-200m-pytorch"
    )

    # 2. Compile for inference (patch-aligned context & horizon)
    config = ForecastConfig(
        max_context=512,   # must be multiple of 32 (patch size)
        max_horizon=128,   # must be multiple of 128 (output patch)
        normalize_inputs=True,
        force_flip_invariance=True,
    )
    model.compile(config)

    # 3. Prepare inputs: list of 1-D numpy arrays (one per market)
    inputs = [np.array(historical_prices, dtype=np.float32)]

    # 4. Forecast -- returns (point_forecasts, quantile_spreads)
    #    point_forecasts: np.ndarray of shape (n_series, horizon)
    #    quantile_spreads: np.ndarray of shape (n_series, horizon, n_quantiles)
    point_forecasts, quantile_spreads = model.forecast(
        horizon=horizon,
        inputs=inputs,
    )

    forecast = point_forecasts[0]  # first (only) series
    quantiles = quantile_spreads[0]

    # 5. Derive a trend signal
    #    Compare the mean of the last 3 forecast points to the last known price.
    last_known = historical_prices[-1]
    forecast_mean = float(np.mean(forecast[-3:]))
    if last_known != 0:
        trend_signal = (forecast_mean - last_known) / abs(last_known)
        trend_signal = max(-1.0, min(1.0, trend_signal))
    else:
        trend_signal = 0.0

    return {
        "point_forecast": forecast.tolist(),
        "quantiles": quantiles.tolist(),
        "trend_signal": trend_signal,
    }
    """
    # Stub: return neutral when TimesFM is not loaded
    logger.info(
        "TimesFM stub called with %d data points, horizon=%d. "
        "Install timesfm dependencies for real forecasts.",
        len(historical_prices),
        horizon,
    )
    return {
        "point_forecast": [float(historical_prices[-1])] * horizon if historical_prices else [0.0] * horizon,
        "quantiles": [],
        "trend_signal": 0.0,
    }


def enrich_with_forecast(
    items: Sequence[ScoredItem],
    price_histories: dict[str, Sequence[float]] | None = None,
    horizon: int = 7,
) -> list[ScoredItem]:
    """Attach forecast_trend to each item using TimesFM (or stub).

    Parameters
    ----------
    items:
        Scored items to enrich.
    price_histories:
        Mapping of item title -> list of historical daily prices/values.
        If None or a title is missing, trend defaults to 0.0 (neutral).
    horizon:
        Number of future time steps to forecast.
    """
    price_histories = price_histories or {}
    enriched: list[ScoredItem] = []

    for item in items:
        history = price_histories.get(item.title)
        if history and len(history) >= 10:
            result = _timesfm_forecast_stub(history, horizon=horizon)
            trend = float(result["trend_signal"])
        else:
            trend = 0.0

        enriched.append(replace(item, forecast_trend=trend))

    return enriched


# ---------------------------------------------------------------------------
# Test block
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    from app.scorer import (
        DeFiYield,
        PredictionMarket,
        print_rankings,
        rank_all,
    )
    from datetime import datetime, timezone

    now = datetime(2026, 4, 1, tzinfo=timezone.utc)

    # -- sample data (same as scorer.py test block) --
    markets = [
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
    yields = [
        DeFiYield("Aave", "USDC", 14.2, 890_000_000, "Ethereum", True),
        DeFiYield("Morpho", "USDC", 18.5, 340_000_000, "Base", True),
    ]

    # 1. Base rankings from scorer
    ranked = rank_all(markets, yields, now=now)

    # 2. Merge social scores (no report file -> neutral)
    with_social = load_and_merge(ranked)

    # 3. Enrich with TimesFM forecast (stub)
    fake_btc_history = [42000 + i * 100 for i in range(60)]
    fake_fed_history = [0.65 + i * 0.002 for i in range(60)]
    price_map = {
        "Will Bitcoin reach $150k?": fake_btc_history,
        "Will Fed cut rates in June?": fake_fed_history,
    }
    final = enrich_with_forecast(with_social, price_histories=price_map)

    print_rankings(final)

    # -- detailed output --
    for item in final:
        print(f"\n{item.title}")
        print(f"  Score          : {item.score}")
        print(f"  Social Score   : {item.social_score}")
        print(f"  Forecast Trend : {item.forecast_trend}")
        print(f"  Components     : {item.raw_components}")

    # -- test the parser with synthetic markdown --
    sample_report = """
# Social Intel Report

## Divergence Alerts

**Divergence**: Will Bitcoin reach 150k - market: 42% vs social: 58% (bullish) confidence: 0.85

**Divergence**: Will Fed cut rates in June - market: 67% vs social: 55% (bearish) confidence: 0.72

## Hook Templates

Hook: "Everyone on X thinks BTC is hitting 150k but the market says otherwise" (controversial) - for Will Bitcoin reach 150k

Hook: "The Fed rate cut that nobody is talking about" (urgent) - for Will Fed cut rates in June
"""

    print("\n\n--- Testing parser with synthetic report ---")
    report = parse_social_intel(sample_report)
    print(f"Divergence alerts found: {len(report.divergence_alerts)}")
    for alert in report.divergence_alerts:
        print(f"  {alert.market_title}: {alert.divergence:.1f}pp divergence ({alert.direction})")

    print(f"Hook templates found: {len(report.hook_templates)}")
    for hook in report.hook_templates:
        print(f"  [{hook.tone}] {hook.hook_text}")

    # re-merge with the parsed report
    with_real_social = compute_social_scores(ranked, report)
    for item in with_real_social:
        print(f"\n{item.title}")
        print(f"  Social Score (with report): {item.social_score}")
