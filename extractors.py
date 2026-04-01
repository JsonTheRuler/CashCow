"""Ticker extraction helpers for mapping market questions to tradeable symbols."""

from __future__ import annotations

import json
import os
import re
from typing import Iterable

import requests


CRYPTO_NAME_TO_TICKER: dict[str, str] = {
    "bitcoin": "BTC",
    "btc": "BTC",
    "ethereum": "ETH",
    "ether": "ETH",
    "eth": "ETH",
    "solana": "SOL",
    "sol": "SOL",
    "dogecoin": "DOGE",
    "doge": "DOGE",
    "ripple": "XRP",
    "xrp": "XRP",
    "cardano": "ADA",
    "ada": "ADA",
    "avalanche": "AVAX",
    "avax": "AVAX",
    "chainlink": "LINK",
    "link": "LINK",
}

EQUITY_NAME_TO_TICKER: dict[str, str] = {
    "nvidia": "NVDA",
    "tesla": "TSLA",
    "apple": "AAPL",
    "microsoft": "MSFT",
    "amazon": "AMZN",
    "meta": "META",
    "alphabet": "GOOGL",
    "google": "GOOGL",
    "netflix": "NFLX",
    "palantir": "PLTR",
    "coinbase": "COIN",
    "microstrategy": "MSTR",
    "strategy": "MSTR",
}

INDEX_PATTERNS: dict[str, list[str]] = {
    r"\bs&p\s*500\b": ["SPY"],
    r"\bsp500\b": ["SPY"],
    r"\bnasdaq(?:\s*100)?\b": ["QQQ"],
    r"\bdow jones\b": ["DIA"],
    r"\brussell\s*2000\b": ["IWM"],
    r"\bgold\b": ["GLD"],
    r"\boil\b": ["USO"],
    r"\btreasur(?:y|ies)\b": ["TLT"],
}

MACRO_EVENT_TO_TICKERS: dict[str, list[str]] = {
    "fed cut rates": ["SPY", "TLT", "GLD"],
    "fed rate cut": ["SPY", "TLT", "GLD"],
    "fed hike rates": ["SPY", "TLT", "UUP"],
    "interest rates": ["SPY", "TLT", "GLD"],
    "inflation": ["SPY", "TLT", "GLD"],
    "cpi": ["SPY", "TLT", "GLD"],
    "jobs report": ["SPY", "TLT", "DXY"],
    "recession": ["SPY", "TLT", "GLD"],
    "oil shock": ["USO", "XLE"],
}

GENERIC_TICKER_RE = re.compile(r"(?<![A-Z])\$([A-Z]{1,5})(?![A-Z])")
ALL_CAPS_RE = re.compile(r"\b([A-Z]{2,5})\b")


def _dedupe(items: Iterable[str]) -> list[str]:
    """Deduplicate values while preserving order."""
    seen: set[str] = set()
    ordered: list[str] = []
    for item in items:
        upper_item = item.upper()
        if upper_item not in seen:
            seen.add(upper_item)
            ordered.append(upper_item)
    return ordered


def _extract_symbol_patterns(question: str) -> list[str]:
    """Extract direct ticker patterns from the raw question."""
    matches = GENERIC_TICKER_RE.findall(question)
    if matches:
        return _dedupe(matches)

    contextual_matches: list[str] = []
    for candidate in ALL_CAPS_RE.findall(question):
        if candidate in {"YES", "NO", "USD", "ETF", "SEC", "FED", "USA", "EU", "UK"}:
            continue
        if len(candidate) <= 5:
            contextual_matches.append(candidate)
    return _dedupe(contextual_matches)


def _extract_from_mappings(question: str) -> list[str]:
    """Extract tickers using hardcoded asset and macro mappings."""
    lowered = question.lower()
    results: list[str] = []

    for name, ticker in CRYPTO_NAME_TO_TICKER.items():
        if re.search(rf"\b{re.escape(name)}\b", lowered):
            results.append(ticker)

    for name, ticker in EQUITY_NAME_TO_TICKER.items():
        if re.search(rf"\b{re.escape(name)}\b", lowered):
            results.append(ticker)

    for pattern, tickers in INDEX_PATTERNS.items():
        if re.search(pattern, lowered):
            results.extend(tickers)

    for phrase, tickers in MACRO_EVENT_TO_TICKERS.items():
        if phrase in lowered:
            results.extend(tickers)

    if "federal reserve" in lowered or "fed" in lowered:
        if "cut" in lowered or "cuts" in lowered:
            results.extend(["SPY", "TLT", "GLD"])
        elif "raise" in lowered or "hike" in lowered:
            results.extend(["SPY", "TLT", "UUP"])

    return _dedupe(results)


def _should_use_llm_fallback(question: str, current_results: list[str]) -> bool:
    """Decide when it is worth asking Gemini for ambiguous ticker inference."""
    lowered = question.lower()
    ambiguous_signals = [
        "company",
        "stock",
        "shares",
        "etf",
        "crypto",
        "token",
        "fed",
        "central bank",
        "inflation",
        "treasury",
    ]
    has_ambiguous_signal = any(signal in lowered for signal in ambiguous_signals)
    return not current_results and has_ambiguous_signal


def infer_tickers_with_gemini(
    question: str,
    api_key: str | None = None,
    model: str = "gemini-2.0-flash",
    timeout: float = 20.0,
) -> list[str]:
    """Use Gemini to infer tradeable tickers for ambiguous market questions."""
    resolved_key = api_key or os.getenv("GOOGLE_API_KEY")
    if not resolved_key:
        return []

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={resolved_key}"
    prompt = (
        "You extract tradeable tickers from market questions.\n"
        "Return only a JSON array of uppercase ticker strings.\n"
        "Use ETFs for macro topics when appropriate.\n"
        "If there is no clear tradeable ticker, return [].\n"
        f"Question: {question}"
    )
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.1,
            "maxOutputTokens": 80,
            "responseMimeType": "application/json",
        },
    }

    response = requests.post(url, json=payload, timeout=timeout)
    response.raise_for_status()
    data = response.json()

    texts: list[str] = []
    for candidate in data.get("candidates", []):
        for part in candidate.get("content", {}).get("parts", []):
            text = part.get("text")
            if text:
                texts.append(text)
    combined = "\n".join(texts).strip()
    if not combined:
        return []

    try:
        parsed = json.loads(combined)
        if isinstance(parsed, list):
            return _dedupe(str(item) for item in parsed if str(item).strip())
    except json.JSONDecodeError:
        pass

    bracket_match = re.search(r"\[.*\]", combined, flags=re.DOTALL)
    if bracket_match:
        try:
            parsed = json.loads(bracket_match.group(0))
            if isinstance(parsed, list):
                return _dedupe(str(item) for item in parsed if str(item).strip())
        except json.JSONDecodeError:
            pass

    return _dedupe(ALL_CAPS_RE.findall(combined))


def extract_tickers(question: str, allow_llm_fallback: bool = True) -> list[str]:
    """Extract tradeable tickers from a Polymarket question."""
    direct_matches = _extract_symbol_patterns(question)
    mapping_matches = _extract_from_mappings(question)
    combined = _dedupe([*direct_matches, *mapping_matches])

    if allow_llm_fallback and _should_use_llm_fallback(question, combined):
        try:
            llm_matches = infer_tickers_with_gemini(question)
        except requests.RequestException:
            llm_matches = []
        combined = _dedupe([*combined, *llm_matches])

    return combined


if __name__ == "__main__":
    examples = {
        "Will Bitcoin reach $200k?": ["BTC"],
        "Will NVIDIA stock hit $200?": ["NVDA"],
        "Will Tesla deliver 2M cars?": ["TSLA"],
        "Will the S&P 500 reach 6000?": ["SPY"],
        "Will the Fed cut rates?": ["SPY", "TLT", "GLD"],
        "Will France win the World Cup?": [],
    }
    for prompt, expected in examples.items():
        actual = extract_tickers(prompt, allow_llm_fallback=False)
        print(f"{prompt}\n  expected={expected}\n  actual={actual}\n")
