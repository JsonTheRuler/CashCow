"""Trading-style signals for tickers (orchestrator / state.json aware)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STATE_PATH = ROOT / "state.json"

RATINGS = ("BUY", "HOLD", "SELL")


def _from_state(ticker: str) -> dict | None:
    if not STATE_PATH.exists():
        return None
    try:
        data = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    upper = ticker.strip().upper()
    for sig in data.get("signals") or []:
        if str(sig.get("ticker", "")).upper() == upper:
            r = str(sig.get("rating", "HOLD")).upper()
            if r == "OVERWEIGHT":
                r = "BUY"
            elif r == "UNDERWEIGHT":
                r = "SELL"
            elif r not in RATINGS:
                r = "HOLD"
            conf = float(sig.get("confidence", 0.72))
            return {
                "ticker": upper,
                "signal": r,
                "confidence": min(0.99, max(0.35, conf)),
                "summary": sig.get("summary", ""),
                "source": "state.json",
            }
    return None


def get_signal(ticker: str) -> dict:
    """
    Return Buy/Hold/Sell with confidence.
    Uses state.json when present; otherwise deterministic demo heuristic from ticker hash.
    """
    hit = _from_state(ticker)
    if hit:
        hit["action"] = hit["signal"]
        hit["state_summary"] = {"summary": hit.get("summary", "")}
        return hit

    h = int(hashlib.sha256(ticker.upper().encode()).hexdigest()[:8], 16)
    idx = h % 3
    conf = 0.45 + (h % 50) / 100.0
    sig = RATINGS[idx]
    return {
        "ticker": ticker.strip().upper(),
        "signal": sig,
        "action": sig,
        "confidence": round(conf, 2),
        "summary": f"Heuristic demo signal for hackathon (no state.json entry for {ticker}).",
        "state_summary": {"summary": f"Heuristic demo signal for hackathon (no state.json entry for {ticker})."},
        "source": "heuristic",
    }


if __name__ == "__main__":
    result = get_signal("SPY")
    assert result is not None, "Function returned None"
    assert result.get("signal"), "Missing signal"
    print(f"✓ {__file__} passed smoke test")
    print(f"  Result: {result.get('signal')} conf={result.get('confidence')}")
