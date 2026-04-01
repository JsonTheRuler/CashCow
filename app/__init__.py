"""
Cash Cow -- Trending market intelligence + AI video generation.

Package layout:
    data.py       -- Fetch Polymarket markets and DeFi Llama yields (with TTL cache)
    scorer.py     -- Unified 0-100 scoring algorithm (prediction markets + DeFi yields)
    extractor.py  -- Extract tradeable tickers from market questions (pure dict + regex)
    prompts.py    -- Generate short-form video scripts (5 templates)
    sentiment.py  -- Merge Grok social intel + TimesFM forecasts into scores
    demo.py       -- Demo mode with theatrical Rich terminal output
    logger.py     -- JSON-formatted logging + atomic state.json management
    api.py        -- FastAPI application (port 8090)
    cli.py        -- CLI entry point (click)

Usage:
    from app import data, scorer, extractor, prompts, api
    from app.scorer import rank_all, PredictionMarket, DeFiYield, ScoredItem
    from app.data import fetch_markets, fetch_yields
    from app.extractor import extract_tickers
    from app.prompts import TEMPLATES
"""

from __future__ import annotations

__version__ = "0.1.0"
__all__ = [
    "api",
    "cli",
    "data",
    "demo",
    "extractor",
    "logger",
    "prompts",
    "scorer",
    "sentiment",
]


def _lazy_import(name: str):
    """Lazy-import a submodule to avoid import side effects at package load time.

    This matters because:
    - api.py imports uvicorn/fastapi (heavy)
    - sentiment.py tries `from scorer import ScoredItem` (needs path setup)
    - Demo mode should not trigger real API clients
    """
    import importlib

    return importlib.import_module(f".{name}", __package__)


def __getattr__(name: str):
    """Support `from app import scorer` without eagerly loading all modules."""
    if name in __all__:
        return _lazy_import(name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
