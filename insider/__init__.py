"""Insider Tracker: detect suspicious trading activity on Polymarket.

Lightweight adaptation of polymarket-insider-tracker that runs without
PostgreSQL or Redis. Uses public Polygon RPC for wallet profiling and
in-memory caching for deduplication.

Usage:
    from insider.scanner import scan_trending
    alerts = scan_trending(n=5)
"""
from __future__ import annotations

__all__ = ["detectors", "formatter", "models", "scanner", "wallet_profiler"]
