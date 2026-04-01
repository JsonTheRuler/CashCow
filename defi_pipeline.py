"""DeFi Llama yield pipeline — top stablecoin pools by APY."""

from __future__ import annotations

from typing import Any

import pandas as pd

from data_sources import fetch_llama_pool_rows


def get_top_yield_pools(
    min_tvl_usd: float = 1_000_000.0,
    top_n: int = 10,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """Return top stablecoin pools by APY with TVL above threshold."""
    if limit is not None:
        top_n = limit
    rows = fetch_llama_pool_rows()
    if not rows:
        return []

    df = pd.DataFrame(rows)
    if df.empty or "tvlUsd" not in df.columns or "apy" not in df.columns:
        return []

    if "stablecoin" in df.columns:
        df = df[df["stablecoin"] == True]  # noqa: E712
    elif "symbol" in df.columns:
        sy = df["symbol"].astype(str).str.upper()
        df = df[sy.str.contains("USD|DAI|FRAX|GUSD|LUSD|USDT|USDC", regex=True, na=False)]

    df = df[df["tvlUsd"].astype(float) > min_tvl_usd]
    df = df.sort_values("apy", ascending=False).head(top_n)

    results: list[dict[str, Any]] = []
    for _, row in df.iterrows():
        results.append(
            {
                "project": str(row.get("project", "")),
                "chain": str(row.get("chain", "")),
                "symbol": str(row.get("symbol", "")),
                "apy": float(row.get("apy", 0.0)),
                "tvlUsd": float(row.get("tvlUsd", 0.0)),
                "tvl_usd": float(row.get("tvlUsd", 0.0)),
                "apyBase": float(row["apyBase"]) if pd.notna(row.get("apyBase")) else None,
                "apyReward": float(row["apyReward"]) if pd.notna(row.get("apyReward")) else None,
                "pool": row.get("pool"),
            }
        )
    return results


def get_defi_summary(limit: int = 5) -> dict[str, Any]:
    """Return a small summary bundle for dashboards and orchestration."""
    pools = get_top_yield_pools(limit=limit)
    best = max(pools, key=lambda row: float(row.get("apy", 0.0)), default=None)
    avg_apy = sum(float(row.get("apy", 0.0)) for row in pools) / len(pools) if pools else 0.0
    total_tvl = sum(float(row.get("tvl_usd", 0.0)) for row in pools)
    return {
        "status": "ok",
        "count": len(pools),
        "avg_apy": round(avg_apy, 2),
        "total_tvl_usd": round(total_tvl, 2),
        "best_pool": best,
        "pools": pools,
    }


if __name__ == "__main__":
    pools = get_top_yield_pools(top_n=3)
    assert pools is not None
    print(f"✓ {__file__} passed smoke test")
    print(f"  Result: {len(pools)} pools")
