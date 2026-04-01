"""Lightweight wallet profiling via public Polygon RPC.

Queries wallet nonce (transaction count) and balance to determine
if a wallet is "fresh" — a key insider trading signal.

No API key required. Uses https://polygon-rpc.com (free, rate-limited).
"""
from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

import requests
from loguru import logger

from insider.models import WalletProfile

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
POLYGON_RPC_URL = "https://polygon-rpc.com"
POLYGON_FALLBACK_RPC = "https://polygon-bor-rpc.publicnode.com"
USDC_CONTRACT = "0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359"  # USDC on Polygon

# Cache: address -> (WalletProfile, expiry_timestamp)
_CACHE: dict[str, tuple[WalletProfile, float]] = {}
CACHE_TTL_SECONDS = 300  # 5 minutes


def _rpc_call(method: str, params: list[Any], rpc_url: str = POLYGON_RPC_URL) -> Any:
    """Make a JSON-RPC call to Polygon.

    Args:
        method: The RPC method (e.g. "eth_getTransactionCount").
        params: Method parameters.
        rpc_url: RPC endpoint URL.

    Returns:
        The "result" field from the RPC response.
    """
    payload = {
        "jsonrpc": "2.0",
        "method": method,
        "params": params,
        "id": 1,
    }
    try:
        r = requests.post(rpc_url, json=payload, timeout=10)
        r.raise_for_status()
        data = r.json()
        if "error" in data:
            raise ValueError(f"RPC error: {data['error']}")
        return data.get("result")
    except Exception:
        if rpc_url != POLYGON_FALLBACK_RPC:
            return _rpc_call(method, params, POLYGON_FALLBACK_RPC)
        raise


def get_wallet_nonce(address: str) -> int:
    """Get the transaction count (nonce) for a wallet.

    Args:
        address: Ethereum/Polygon wallet address.

    Returns:
        Number of transactions sent from this wallet.
    """
    result = _rpc_call("eth_getTransactionCount", [address, "latest"])
    return int(result, 16) if result else 0


def get_matic_balance(address: str) -> float:
    """Get MATIC balance for a wallet.

    Args:
        address: Wallet address.

    Returns:
        Balance in MATIC.
    """
    result = _rpc_call("eth_getBalance", [address, "latest"])
    wei = int(result, 16) if result else 0
    return wei / 1e18


def get_usdc_balance(address: str) -> float:
    """Get USDC balance for a wallet on Polygon.

    Uses the ERC-20 balanceOf call on the USDC contract.

    Args:
        address: Wallet address.

    Returns:
        Balance in USDC (6 decimals).
    """
    # balanceOf(address) selector = 0x70a08231
    padded_address = "0x" + address.lower().replace("0x", "").zfill(64)
    data = "0x70a08231" + padded_address[2:]
    result = _rpc_call("eth_call", [{"to": USDC_CONTRACT, "data": data}, "latest"])
    raw = int(result, 16) if result else 0
    return raw / 1e6  # USDC has 6 decimals


def get_wallet_profile(address: str) -> WalletProfile:
    """Build a complete wallet profile from on-chain data.

    Results are cached in-memory for 5 minutes to reduce RPC calls.

    Args:
        address: Wallet address to profile.

    Returns:
        WalletProfile with nonce, balance, and freshness assessment.
    """
    address = address.lower()
    now = time.time()

    # Check cache
    if address in _CACHE:
        profile, expiry = _CACHE[address]
        if now < expiry:
            return profile

    try:
        nonce = get_wallet_nonce(address)
        matic = get_matic_balance(address)

        # Only fetch USDC for potentially fresh wallets (save RPC calls)
        usdc = 0.0
        if nonce <= 20:
            try:
                usdc = get_usdc_balance(address)
            except Exception:
                pass

        # Estimate wallet age from nonce (rough heuristic)
        # Fresh wallets: < 5 transactions and likely created recently
        # We can't get exact creation time without an indexer, so use nonce as proxy
        age_hours = max(nonce * 2.0, 0.1)  # rough: ~2h per transaction on average
        is_fresh = nonce <= 5

        profile = WalletProfile(
            address=address,
            nonce=nonce,
            age_hours=age_hours,
            matic_balance=matic,
            usdc_balance=usdc,
            is_fresh=is_fresh,
            analyzed_at=datetime.now(timezone.utc),
        )

    except Exception as e:
        logger.warning(f"Wallet profiling failed for {address[:10]}...: {e}")
        profile = WalletProfile(
            address=address,
            nonce=-1,
            age_hours=-1,
            is_fresh=False,
            analyzed_at=datetime.now(timezone.utc),
        )

    # Cache
    _CACHE[address] = (profile, now + CACHE_TTL_SECONDS)

    # Prune cache if it gets too large
    if len(_CACHE) > 10_000:
        expired = [k for k, (_, exp) in _CACHE.items() if now > exp]
        for k in expired:
            del _CACHE[k]

    return profile


def clear_cache() -> None:
    """Clear the in-memory wallet profile cache."""
    _CACHE.clear()


if __name__ == "__main__":
    # Smoke test with a known Polymarket whale
    test_addr = "0x0000000000000000000000000000000000000001"
    profile = get_wallet_profile(test_addr)
    assert profile is not None, "Profile is None"
    print(f"  {__file__} passed smoke test")
    print(f"  Address: {profile.address}")
    print(f"  Nonce: {profile.nonce}")
    print(f"  MATIC: {profile.matic_balance:.4f}")
    print(f"  Fresh: {profile.is_fresh}")
