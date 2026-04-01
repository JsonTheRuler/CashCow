"""Ticker Extractor — maps Polymarket question strings to tradeable symbols.

Pure dictionary lookup, no LLM calls. Runs in microseconds.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Sequence

# ---------------------------------------------------------------------------
# Mapping tables
# ---------------------------------------------------------------------------

# Crypto: common name / symbol → canonical ticker
CRYPTO_MAP: dict[str, str] = {
    "bitcoin": "BTC",
    "btc": "BTC",
    "ethereum": "ETH",
    "ether": "ETH",
    "eth": "ETH",
    "solana": "SOL",
    "sol": "SOL",
    "cardano": "ADA",
    "ada": "ADA",
    "ripple": "XRP",
    "xrp": "XRP",
    "dogecoin": "DOGE",
    "doge": "DOGE",
    "polkadot": "DOT",
    "dot": "DOT",
    "avalanche": "AVAX",
    "avax": "AVAX",
    "chainlink": "LINK",
    "link": "LINK",
    "polygon": "MATIC",
    "matic": "MATIC",
    "litecoin": "LTC",
    "ltc": "LTC",
    "uniswap": "UNI",
    "uni": "UNI",
    "cosmos": "ATOM",
    "atom": "ATOM",
    "near protocol": "NEAR",
    "near": "NEAR",
    "arbitrum": "ARB",
    "arb": "ARB",
    "optimism": "OP",
    "aptos": "APT",
    "apt": "APT",
    "sui": "SUI",
    "pepe": "PEPE",
    "shiba inu": "SHIB",
    "shib": "SHIB",
    "toncoin": "TON",
    "ton": "TON",
    "stacks": "STX",
    "stx": "STX",
    "render": "RNDR",
    "rndr": "RNDR",
    "injective": "INJ",
    "inj": "INJ",
    "celestia": "TIA",
    "tia": "TIA",
    "bonk": "BONK",
    "jupiter": "JUP",
    "jup": "JUP",
    "wif": "WIF",
}

# Stocks: company name / common alias → ticker
STOCK_MAP: dict[str, str] = {
    "nvidia": "NVDA",
    "nvda": "NVDA",
    "tesla": "TSLA",
    "tsla": "TSLA",
    "apple": "AAPL",
    "aapl": "AAPL",
    "microsoft": "MSFT",
    "msft": "MSFT",
    "amazon": "AMZN",
    "amzn": "AMZN",
    "google": "GOOGL",
    "alphabet": "GOOGL",
    "googl": "GOOGL",
    "meta": "META",
    "facebook": "META",
    "netflix": "NFLX",
    "nflx": "NFLX",
    "amd": "AMD",
    "advanced micro devices": "AMD",
    "intel": "INTC",
    "intc": "INTC",
    "palantir": "PLTR",
    "pltr": "PLTR",
    "coinbase": "COIN",
    "coin": "COIN",
    "microstrategy": "MSTR",
    "mstr": "MSTR",
    "gamestop": "GME",
    "gme": "GME",
    "robinhood": "HOOD",
    "hood": "HOOD",
    "disney": "DIS",
    "dis": "DIS",
    "boeing": "BA",
    "ba": "BA",
    "jpmorgan": "JPM",
    "jpm": "JPM",
    "goldman sachs": "GS",
    "gs": "GS",
    "bank of america": "BAC",
    "bac": "BAC",
    "berkshire": "BRK.B",
    "walmart": "WMT",
    "wmt": "WMT",
    "coca cola": "KO",
    "coca-cola": "KO",
    "ko": "KO",
    "johnson & johnson": "JNJ",
    "jnj": "JNJ",
    "pfizer": "PFE",
    "pfe": "PFE",
    "moderna": "MRNA",
    "mrna": "MRNA",
    "uber": "UBER",
    "airbnb": "ABNB",
    "abnb": "ABNB",
    "snowflake": "SNOW",
    "snow": "SNOW",
    "crowdstrike": "CRWD",
    "crwd": "CRWD",
    "broadcom": "AVGO",
    "avgo": "AVGO",
    "arm holdings": "ARM",
    "arm": "ARM",
    "supermicro": "SMCI",
    "smci": "SMCI",
    "spotify": "SPOT",
    "spot": "SPOT",
}

# Macro themes: keyword phrase → list of proxy tickers
MACRO_MAP: dict[str, list[str]] = {
    "fed rate": ["SPY", "TLT", "GLD"],
    "federal reserve": ["SPY", "TLT", "GLD"],
    "interest rate": ["SPY", "TLT", "GLD"],
    "rate hike": ["SPY", "TLT", "GLD"],
    "rate cut": ["SPY", "TLT", "GLD"],
    "cut rates": ["SPY", "TLT", "GLD"],
    "raise rates": ["SPY", "TLT", "GLD"],
    "fomc": ["SPY", "TLT", "GLD"],
    "inflation": ["TIP", "GLD"],
    "cpi": ["TIP", "GLD", "SPY"],
    "consumer price index": ["TIP", "GLD", "SPY"],
    "recession": ["SPY", "VIX", "TLT"],
    "gdp": ["SPY", "VIX", "TLT"],
    "unemployment": ["SPY", "VIX", "TLT"],
    "jobs report": ["SPY", "VIX", "TLT"],
    "nonfarm payroll": ["SPY", "VIX", "TLT"],
    "non-farm payroll": ["SPY", "VIX", "TLT"],
    "treasury": ["TLT", "SHY", "IEF"],
    "bond yield": ["TLT", "SHY", "IEF"],
    "10-year yield": ["TLT", "IEF"],
    "debt ceiling": ["SPY", "TLT", "VIX"],
    "government shutdown": ["SPY", "TLT", "VIX"],
    "tariff": ["SPY", "EEM", "VIX"],
    "trade war": ["SPY", "EEM", "VIX"],
    "oil price": ["USO", "XLE"],
    "crude oil": ["USO", "XLE"],
    "gold price": ["GLD", "GDX"],
    "silver price": ["SLV"],
    "dollar index": ["UUP", "DXY"],
    "s&p 500": ["SPY"],
    "s&p500": ["SPY"],
    "sp500": ["SPY"],
    "dow jones": ["DIA"],
    "nasdaq": ["QQQ"],
    "russell 2000": ["IWM"],
    "vix": ["VIX"],
    "volatility index": ["VIX"],
}

# Patterns that signal a direct ticker mention: "$NVDA", "NVDA stock"
_TICKER_DOLLAR_RE = re.compile(r"\$([A-Z]{1,5})\b")
_TICKER_STOCK_RE = re.compile(r"\b([A-Z]{1,5})\s+stock\b", re.IGNORECASE)

# All known tickers (for validation of regex hits)
_KNOWN_TICKERS: frozenset[str] = frozenset(
    list(CRYPTO_MAP.values())
    + list(STOCK_MAP.values())
    + [t for group in MACRO_MAP.values() for t in group]
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ExtractionResult:
    """Immutable result of ticker extraction."""

    question: str
    tickers: tuple[str, ...]
    source: str  # "crypto" | "stock" | "macro" | "pattern" | "none"


def extract_tickers(question: str) -> ExtractionResult:
    """Extract tradeable ticker symbols from a Polymarket question.

    Returns an ``ExtractionResult`` with deduplicated, sorted tickers.
    No LLM calls — pure dictionary + regex lookup.
    """
    if not question or not question.strip():
        return ExtractionResult(question=question, tickers=(), source="none")

    lower = question.lower()
    tickers: list[str] = []
    source = "none"

    # 1. Check macro themes first (longer phrases take priority)
    for phrase, symbols in sorted(MACRO_MAP.items(), key=lambda kv: -len(kv[0])):
        if phrase in lower:
            tickers.extend(symbols)
            source = "macro"

    # 2. Check crypto names / symbols
    for name, symbol in CRYPTO_MAP.items():
        if _word_match(name, lower):
            tickers.append(symbol)
            if source == "none":
                source = "crypto"

    # 3. Check stock names / symbols
    for name, symbol in STOCK_MAP.items():
        if _word_match(name, lower):
            tickers.append(symbol)
            if source in ("none", "crypto"):
                source = "stock"

    # 4. Regex: "$NVDA" or "NVDA stock"
    for match in _TICKER_DOLLAR_RE.finditer(question):
        candidate = match.group(1).upper()
        if candidate in _KNOWN_TICKERS:
            tickers.append(candidate)
            if source == "none":
                source = "pattern"

    for match in _TICKER_STOCK_RE.finditer(question):
        candidate = match.group(1).upper()
        if candidate in _KNOWN_TICKERS:
            tickers.append(candidate)
            if source == "none":
                source = "pattern"

    # Deduplicate while preserving rough insertion order, then sort
    seen: set[str] = set()
    unique: list[str] = []
    for t in tickers:
        if t not in seen:
            seen.add(t)
            unique.append(t)
    unique.sort()

    return ExtractionResult(
        question=question,
        tickers=tuple(unique),
        source=source if unique else "none",
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _word_match(term: str, text: str) -> bool:
    """Check if *term* appears as a whole word (or phrase) in *text*.

    Both inputs must already be lowered.
    """
    pattern = r"(?<![a-z])" + re.escape(term) + r"(?![a-z])"
    return bool(re.search(pattern, text))


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    test_cases: list[tuple[str, list[str]]] = [
        # Crypto
        ("Will Bitcoin reach $100k by end of 2025?", ["BTC"]),
        ("Will Ethereum flip Bitcoin in market cap?", ["BTC", "ETH"]),
        ("Solana TVL above $10B?", ["SOL"]),
        # Stocks
        ("Will NVIDIA stock hit $200?", ["NVDA"]),
        ("Tesla deliveries above 500k in Q4?", ["TSLA"]),
        ("Will $AAPL announce a foldable iPhone?", ["AAPL"]),
        # Macro
        ("Will the Fed cut rates in June?", ["GLD", "SPY", "TLT"]),
        ("US inflation above 3% in April CPI?", ["GLD", "SPY", "TIP"]),
        ("Will there be a US recession in 2025?", ["SPY", "TLT", "VIX"]),
        # Non-financial — should return empty
        ("Will the Lakers win the NBA Finals?", []),
        ("Will Trump win the 2028 election?", []),
        ("Will Taylor Swift announce a new album?", []),
        # Mixed / edge cases
        ("Coinbase stock above $300?", ["COIN"]),
        ("Gold price above $3000?", ["GDX", "GLD"]),
    ]

    print("=" * 70)
    print("EXTRACTOR SELF-TEST")
    print("=" * 70)

    passed = 0
    for question, expected in test_cases:
        result = extract_tickers(question)
        expected_sorted = sorted(expected)
        ok = list(result.tickers) == expected_sorted
        status = "PASS" if ok else "FAIL"
        if ok:
            passed += 1
        print(f"  [{status}] {question}")
        if not ok:
            print(f"         expected: {expected_sorted}")
            print(f"         got:      {list(result.tickers)}")
        print(f"         source={result.source}  tickers={list(result.tickers)}")

    print("-" * 70)
    print(f"Results: {passed}/{len(test_cases)} passed")
    print("=" * 70)
