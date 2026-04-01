#!/usr/bin/env python3
"""TimesFM price forecaster for Polymarket markets.

Fetches historical price data from Polymarket CLOB API, runs TimesFM
200M model to forecast next 12-24 data points, and returns forecasts
with confidence intervals.

Usage:
    python -m bridge.forecaster
"""
from __future__ import annotations

import json
from typing import Any

import requests
from loguru import logger

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
CLOB_API = "https://clob.polymarket.com"


def fetch_price_history(
    condition_id: str,
    interval: str = "1d",
    fidelity: int = 60,
) -> list[float]:
    """Fetch historical price data for a Polymarket market from CLOB API.

    Args:
        condition_id: The market condition ID (from Gamma API market object).
        interval: Time interval for data points (e.g. "1d", "1h").
        fidelity: Number of data points to fetch.

    Returns:
        List of price floats, or empty list on failure.
    """
    try:
        r = requests.get(
            f"{CLOB_API}/prices-history",
            params={
                "market": condition_id,
                "interval": interval,
                "fidelity": fidelity,
            },
            timeout=10,
        )
        r.raise_for_status()
        data = r.json()
        # Extract prices from the response
        if isinstance(data, list):
            return [float(p.get("p", p.get("price", 0))) for p in data if isinstance(p, dict)]
        if isinstance(data, dict) and "history" in data:
            return [float(p.get("p", 0)) for p in data["history"]]
        return []
    except Exception as e:
        logger.warning(f"CLOB price history failed for {condition_id}: {e}")
        return []


def forecast_timesfm(
    prices: list[float],
    horizon: int = 12,
) -> dict[str, Any]:
    """Run TimesFM forecast on price history.

    Falls back to simple linear projection if TimesFM is not installed.

    Args:
        prices: List of historical prices.
        horizon: Number of future points to predict.

    Returns:
        Dict with forecast values, confidence intervals, and metadata.
    """
    if len(prices) < 10:
        return {
            "forecast": [],
            "lower": [],
            "upper": [],
            "model": "insufficient_data",
            "note": f"Need 10+ data points, got {len(prices)}",
        }

    try:
        import numpy as np
        import timesfm

        tfm = timesfm.TimesFm(
            hparams=timesfm.TimesFmHparams(
                backend="cpu",
                per_core_batch_size=32,
                horizon_len=horizon,
            ),
            checkpoint=timesfm.TimesFmCheckpoint(
                huggingface_repo_id="google/timesfm-1.0-200m-pytorch",
            ),
        )

        forecast_input = np.array(prices).reshape(1, -1)
        point_forecast, experimental_quantile_forecast = tfm.forecast(
            forecast_input,
            freq=[0],
        )

        return {
            "forecast": point_forecast[0].tolist(),
            "lower": experimental_quantile_forecast[0, :, 0].tolist() if experimental_quantile_forecast is not None else [],
            "upper": experimental_quantile_forecast[0, :, -1].tolist() if experimental_quantile_forecast is not None else [],
            "model": "timesfm-200m",
            "input_length": len(prices),
            "horizon": horizon,
        }

    except ImportError:
        logger.info("TimesFM not installed, using linear projection fallback")
        return _linear_fallback(prices, horizon)
    except Exception as e:
        logger.warning(f"TimesFM failed: {e}, using linear projection")
        return _linear_fallback(prices, horizon)


def _linear_fallback(prices: list[float], horizon: int) -> dict[str, Any]:
    """Simple linear projection when TimesFM is unavailable.

    Args:
        prices: Historical prices.
        horizon: Points to forecast.

    Returns:
        Forecast dict with linear projections.
    """
    n = len(prices)
    if n < 2:
        return {"forecast": [prices[-1]] * horizon if prices else [], "model": "constant"}

    # Simple linear regression
    x_mean = (n - 1) / 2
    y_mean = sum(prices) / n
    slope_num = sum((i - x_mean) * (p - y_mean) for i, p in enumerate(prices))
    slope_den = sum((i - x_mean) ** 2 for i in range(n))
    slope = slope_num / slope_den if slope_den != 0 else 0
    intercept = y_mean - slope * x_mean

    forecast = [intercept + slope * (n + i) for i in range(horizon)]
    # Clamp to [0, 1] for probability markets
    forecast = [max(0.0, min(1.0, f)) for f in forecast]

    # Simple confidence band (widening over time)
    std = (sum((p - (intercept + slope * i)) ** 2 for i, p in enumerate(prices)) / n) ** 0.5
    lower = [max(0, f - std * (1 + j * 0.1)) for j, f in enumerate(forecast)]
    upper = [min(1, f + std * (1 + j * 0.1)) for j, f in enumerate(forecast)]

    return {
        "forecast": forecast,
        "lower": lower,
        "upper": upper,
        "model": "linear_projection",
        "input_length": n,
        "horizon": horizon,
        "slope": round(slope, 6),
    }


def forecast_market(market: dict[str, Any], horizon: int = 12) -> dict[str, Any]:
    """Forecast a Polymarket market's price trajectory.

    Args:
        market: Raw market dict from Gamma API (needs conditionId).
        horizon: Number of future points to predict.

    Returns:
        Forecast dict including market context.
    """
    condition_id = market.get("conditionId", market.get("condition_id", ""))
    question = market.get("question", "Unknown")

    if not condition_id:
        return {
            "question": question,
            "forecast": [],
            "model": "no_condition_id",
            "note": "Market lacks conditionId for CLOB lookup",
        }

    prices = fetch_price_history(condition_id)
    forecast = forecast_timesfm(prices, horizon)
    forecast["question"] = question
    forecast["condition_id"] = condition_id

    logger.info(
        f"Forecast for '{question[:50]}': "
        f"model={forecast['model']}, points={len(forecast.get('forecast', []))}"
    )
    return forecast


if __name__ == "__main__":
    # Smoke test with synthetic data
    import random

    random.seed(42)
    test_prices = [0.5 + 0.01 * i + random.gauss(0, 0.02) for i in range(50)]

    result = forecast_timesfm(test_prices, horizon=12)
    assert result is not None, "Forecast returned None"
    assert len(result["forecast"]) > 0, "No forecast points"
    print(f"\n  {__file__} passed smoke test")
    print(f"  Model: {result['model']}")
    print(f"  Input: {result.get('input_length', '?')} points")
    print(f"  Forecast: {len(result['forecast'])} points")
    print(f"  Sample: {result['forecast'][:5]}")
