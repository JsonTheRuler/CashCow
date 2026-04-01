"""Smoke tests - verify each module loads and runs without crashing."""


def test_scorer_loads() -> None:
    from scorer import fetch_and_score, top_markets

    markets = top_markets(3)
    assert len(markets) > 0
    assert "score" in markets[0]
    assert "question" in markets[0]
    assert len(fetch_and_score(limit=2)) > 0


def test_defi_loads() -> None:
    from defi_pipeline import get_top_yield_pools

    pools = get_top_yield_pools(limit=3)
    assert len(pools) > 0
    assert "apy" in pools[0]


def test_bridge_scoring() -> None:
    from bridge import score_market

    mock = {"volume24hr": "500000", "outcomePrices": '["0.65","0.35"]'}
    score = score_market(mock)
    assert 0 <= score <= 1


def test_forecaster_linear() -> None:
    from forecaster import linear_forecast

    history = [0.4, 0.45, 0.5, 0.55, 0.6]
    result = linear_forecast(history, steps=6)
    assert len(result) == 6
    assert all(0 < value < 1 for value in result)


def test_trading_signal_mock() -> None:
    from trading_signal import get_signal

    result = get_signal("BTC-USD")
    assert result["ticker"] == "BTC-USD"
    assert result["action"] in ("BUY", "SELL", "HOLD")


def test_market_analytics() -> None:
    from market_analytics import full_analytics

    data = full_analytics(10)
    assert data["status"] == "ok"
    assert len(data["top_markets"]) > 0
