"""Map agent ratings to actions: paper ledger, Alpaca, Tradier, or webhook."""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

import requests

VALID_RATINGS = frozenset({"BUY", "OVERWEIGHT", "HOLD", "UNDERWEIGHT", "SELL"})


def normalize_rating(raw: str | None) -> str:
    if not raw or not str(raw).strip():
        return "HOLD"
    text = str(raw).strip().upper()
    m = re.search(r"\b(BUY|OVERWEIGHT|HOLD|UNDERWEIGHT|SELL)\b", text)
    if m:
        return m.group(1)
    for word in VALID_RATINGS:
        if word in text:
            return word
    return "HOLD"


def rating_to_side(rating: str) -> Optional[str]:
    if rating in ("BUY", "OVERWEIGHT"):
        return "buy"
    if rating in ("SELL", "UNDERWEIGHT"):
        return "sell"
    return None


def append_paper_ledger(
    results_dir: Path,
    entry: Dict[str, Any],
) -> Path:
    results_dir.mkdir(parents=True, exist_ok=True)
    path = results_dir / "trading_ledger.jsonl"
    line = json.dumps(entry, ensure_ascii=False) + "\n"
    path.open("a", encoding="utf-8").write(line)
    return path


def submit_alpaca_order(
    symbol: str,
    side: str,
    qty: float,
    *,
    paper: bool = True,
) -> Dict[str, Any]:
    key = os.getenv("ALPACA_API_KEY_ID") or os.getenv("ALPACA_API_KEY")
    secret = os.getenv("ALPACA_API_SECRET_KEY") or os.getenv("ALPACA_SECRET_KEY")
    if not key or not secret:
        return {"ok": False, "error": "Missing ALPACA_API_KEY_ID / ALPACA_API_SECRET_KEY"}

    base = os.getenv(
        "ALPACA_BASE_URL",
        "https://paper-api.alpaca.markets" if paper else "https://api.alpaca.markets",
    ).rstrip("/")

    url = f"{base}/v2/orders"
    headers = {
        "APCA-API-KEY-ID": key,
        "APCA-API-SECRET-KEY": secret,
        "Content-Type": "application/json",
    }
    sym = symbol.upper().split(".")[0][:10]
    body: Dict[str, Any] = {
        "symbol": sym,
        "side": side,
        "type": "market",
        "time_in_force": "day",
    }
    q = float(qty)
    if q >= 1 and abs(q - int(q)) < 1e-9:
        body["qty"] = int(q)
    else:
        body["notional"] = str(max(1.0, round(q, 2)))

    try:
        r = requests.post(url, headers=headers, json=body, timeout=60)
        data = r.json() if r.content else {}
        if r.status_code >= 400:
            return {
                "ok": False,
                "error": data.get("message", r.text) or f"HTTP {r.status_code}",
                "details": data,
            }
        return {"ok": True, "order": data}
    except requests.RequestException as e:
        return {"ok": False, "error": str(e)}


def submit_tradier_order(
    symbol: str,
    side: str,
    qty: float,
) -> Dict[str, Any]:
    token = os.getenv("TRADIER_ACCESS_TOKEN")
    account = os.getenv("TRADIER_ACCOUNT_ID")
    if not token or not account:
        return {
            "ok": False,
            "error": "Missing TRADIER_ACCESS_TOKEN or TRADIER_ACCOUNT_ID",
        }
    sym = symbol.upper().split(".")[0][:8]
    q = float(qty)
    quantity = int(q) if q >= 1 and abs(q - int(q)) < 1e-9 else max(1, int(q) or 1)

    url = f"https://api.tradier.com/v1/accounts/{account}/orders"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }
    data = {
        "class": "equity",
        "symbol": sym,
        "side": side,
        "quantity": str(quantity),
        "type": "market",
        "duration": "day",
    }
    try:
        r = requests.post(url, data=data, headers=headers, timeout=60)
        try:
            body = r.json()
        except Exception:
            body = {"raw": r.text}
        if r.status_code >= 400:
            return {
                "ok": False,
                "error": str(body.get("fault", body)) if isinstance(body, dict) else r.text,
                "details": body,
            }
        return {"ok": True, "order": body}
    except requests.RequestException as e:
        return {"ok": False, "error": str(e)}


def post_execution_webhook(
    payload: Dict[str, Any],
) -> Dict[str, Any]:
    url = os.getenv("EXECUTION_WEBHOOK_URL", "").strip()
    if not url:
        return {"ok": False, "error": "EXECUTION_WEBHOOK_URL is not set"}
    secret = os.getenv("EXECUTION_WEBHOOK_SECRET", "").strip()
    headers = {"Content-Type": "application/json"}
    if secret:
        headers["X-TradingAgents-Secret"] = secret
    try:
        r = requests.post(url, json=payload, headers=headers, timeout=45)
        text = r.text[:2000] if r.text else ""
        if r.status_code >= 400:
            return {
                "ok": False,
                "error": f"HTTP {r.status_code}",
                "body_preview": text,
            }
        return {"ok": True, "status_code": r.status_code, "body_preview": text}
    except requests.RequestException as e:
        return {"ok": False, "error": str(e)}


def execute_decision(
    *,
    ticker: str,
    rating_raw: str,
    execution_mode: str,
    order_qty: float,
    results_dir: Path,
    paper_trading: bool = True,
) -> Dict[str, Any]:
    rating = normalize_rating(rating_raw)
    side = rating_to_side(rating)
    ts = datetime.now(timezone.utc).isoformat()

    ledger_entry: Dict[str, Any] = {
        "ts": ts,
        "ticker": ticker,
        "rating": rating,
        "side": side,
        "execution_mode": execution_mode,
    }

    if execution_mode == "none":
        ledger_entry["note"] = "Analysis only; no execution requested."
        append_paper_ledger(results_dir, ledger_entry)
        return {"mode": "none", "rating": rating, "ledger": True}

    if execution_mode == "paper":
        ledger_entry["order_simulated"] = bool(side)
        if side:
            ledger_entry["simulated"] = {
                "side": side,
                "qty": order_qty,
                "message": "Recorded as simulated fill at next open (not a real broker).",
            }
        append_paper_ledger(results_dir, ledger_entry)
        return {"mode": "paper", "rating": rating, "side": side, "ledger": True}

    if execution_mode == "alpaca":
        if not side:
            ledger_entry["note"] = "HOLD — no Alpaca order sent."
            append_paper_ledger(results_dir, ledger_entry)
            return {"mode": "alpaca", "rating": rating, "skipped": True, "ledger": True}
        alpaca = submit_alpaca_order(ticker, side, order_qty, paper=paper_trading)
        ledger_entry["alpaca"] = alpaca
        append_paper_ledger(results_dir, ledger_entry)
        return {
            "mode": "alpaca",
            "rating": rating,
            "side": side,
            "alpaca": alpaca,
            "ledger": True,
        }

    if execution_mode == "tradier":
        if not side:
            ledger_entry["note"] = "HOLD — no Tradier order sent."
            append_paper_ledger(results_dir, ledger_entry)
            return {"mode": "tradier", "rating": rating, "skipped": True, "ledger": True}
        td = submit_tradier_order(ticker, side, order_qty)
        ledger_entry["tradier"] = td
        append_paper_ledger(results_dir, ledger_entry)
        return {
            "mode": "tradier",
            "rating": rating,
            "side": side,
            "tradier": td,
            "ledger": True,
        }

    if execution_mode == "webhook":
        hook_payload = {
            "ts": ts,
            "ticker": ticker,
            "rating": rating,
            "side": side,
            "order_qty": order_qty,
            "execution_mode": "webhook",
        }
        wh = post_execution_webhook(hook_payload)
        ledger_entry["webhook"] = wh
        ledger_entry["webhook_payload"] = hook_payload
        append_paper_ledger(results_dir, ledger_entry)
        return {
            "mode": "webhook",
            "rating": rating,
            "side": side,
            "webhook": wh,
            "ledger": True,
        }

    append_paper_ledger(results_dir, {**ledger_entry, "error": "unknown execution_mode"})
    return {"mode": execution_mode, "error": "unknown execution_mode", "rating": rating}
