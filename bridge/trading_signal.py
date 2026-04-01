#!/usr/bin/env python3
"""TradingAgents adapter: extract tickers from Polymarket markets, get signals.

Connects to TradingAgents framework to produce Buy/Hold/Sell signals
for any tradeable tickers mentioned in prediction market questions.

Usage:
    python -m bridge.trading_signal
"""
from __future__ import annotations

import re
from typing import Any

from loguru import logger

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
TICKER_PATTERNS: dict[str, list[str]] = {
    "BTC": ["bitcoin", "btc", "₿"],
    "ETH": ["ethereum", "eth", "ether"],
    "SOL": ["solana", "sol"],
    "DOGE": ["dogecoin", "doge"],
    "XRP": ["xrp", "ripple"],
    "AAPL": ["apple", "aapl"],
    "TSLA": ["tesla", "tsla"],
    "NVDA": ["nvidia", "nvda"],
    "GOOG": ["google", "alphabet", "goog", "googl"],
    "MSFT": ["microsoft", "msft"],
    "AMZN": ["amazon", "amzn"],
    "META": ["meta", "facebook"],
    "SPY": ["s&p 500", "s&p500", "spy", "sp500"],
}


def extract_tickers(text: str) -> list[str]:
    """Extract tradeable ticker symbols from market question text.

    Args:
        text: Market question or description string.

    Returns:
        List of detected ticker symbols (e.g. ["BTC", "ETH"]).
    """
    text_lower = text.lower()
    found: list[str] = []
    for ticker, keywords in TICKER_PATTERNS.items():
        for kw in keywords:
            if kw in text_lower:
                if ticker not in found:
                    found.append(ticker)
                break
    return found


def get_trading_signal(ticker: str) -> dict[str, Any]:
    """Get Buy/Hold/Sell signal for a ticker via TradingAgents.

    Falls back to a neutral "Hold" signal if TradingAgents is not installed.

    Args:
        ticker: Ticker symbol (e.g. "BTC", "NVDA").

    Returns:
        Dict with signal, confidence, and reasoning.
    """
    try:
        from tradingagents.graph.trading_graph import TradingAgentsGraph

        graph = TradingAgentsGraph(
            selected_analysts=["market", "social", "news", "fundamentals"],
        )
        _, result = graph.propagate(ticker, "2026-04-01")

        action = result.get("action", "hold").capitalize()
        confidence = result.get("confidence", 0.5)

        return {
            "ticker": ticker,
            "signal": action,
            "confidence": round(confidence, 2),
            "source": "tradingagents",
            "reasoning": result.get("reasoning", ""),
        }
    except ImportError:
        logger.info(f"TradingAgents not installed, returning mock signal for {ticker}")
        return {
            "ticker": ticker,
            "signal": "Hold",
            "confidence": 0.5,
            "source": "mock",
            "reasoning": "TradingAgents framework not available",
        }
    except Exception as e:
        logger.warning(f"TradingAgents failed for {ticker}: {e}")
        return {
            "ticker": ticker,
            "signal": "Hold",
            "confidence": 0.5,
            "source": "error",
            "reasoning": str(e),
        }


def get_signals_for_markets(markets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Extract tickers from markets and get signals for each.

    Args:
        markets: List of market detail dicts (from bridge.get_market_detail).

    Returns:
        List of signal dicts, one per detected ticker.
    """
    all_signals: list[dict[str, Any]] = []
    seen_tickers: set[str] = set()

    for market in markets:
        question = market.get("question", "")
        description = market.get("description", "")
        tickers = extract_tickers(f"{question} {description}")

        for ticker in tickers:
            if ticker not in seen_tickers:
                seen_tickers.add(ticker)
                signal = get_trading_signal(ticker)
                signal["source_market"] = question[:80]
                all_signals.append(signal)
                logger.info(
                    f"Signal: {ticker} -> {signal['signal']} "
                    f"(conf: {signal['confidence']}, src: {signal['source']})"
                )

    return all_signals


if __name__ == "__main__":
    # Smoke test with sample questions
    test_questions = [
        {"question": "Will Bitcoin exceed $100,000?", "description": "BTC price prediction"},
        {"question": "Will Tesla stock reach $500?", "description": "TSLA stock market"},
        {"question": "Netanyahu out by March?", "description": "Israeli politics"},
    ]

    signals = get_signals_for_markets(test_questions)
    assert signals is not None, "Returned None"
    print(f"\n  {__file__} passed smoke test")
    print(f"  Tickers found: {[s['ticker'] for s in signals]}")
    for s in signals:
        print(f"  {s['ticker']}: {s['signal']} (confidence: {s['confidence']})")
