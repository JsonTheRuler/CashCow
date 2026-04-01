"""Background graph streaming for SSE/WebSocket (CLI-style chunk updates)."""

from __future__ import annotations

import json
import queue
import threading
import traceback
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from webapp.execution import execute_decision, normalize_rating
from webapp.graph_runner import create_trading_graph
from webapp.schemas import RunRequest


def _preview(text: Any, max_len: int = 180) -> str:
    if text is None:
        return ""
    s = str(text).strip()
    if len(s) <= max_len:
        return s
    return s[: max_len - 1] + "…"


def _extract_message_content(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, dict):
        t = content.get("text", "")
        return str(t).strip() if t else ""
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                parts.append(str(item.get("text", "")))
            elif isinstance(item, str):
                parts.append(item)
        return " ".join(p for p in parts if p).strip()
    return str(content).strip()


def _serialize_message(msg: Any) -> Dict[str, Any]:
    cls_name = msg.__class__.__name__
    out: Dict[str, Any] = {
        "class": cls_name,
        "preview": _preview(_extract_message_content(getattr(msg, "content", None)), 220),
    }
    tcs = getattr(msg, "tool_calls", None) or []
    names: List[str] = []
    for tc in tcs:
        if isinstance(tc, dict):
            n = tc.get("name")
        else:
            n = getattr(tc, "name", None)
        if n:
            names.append(str(n))
    if names:
        out["tool_calls"] = names
    return out


REPORT_KEYS = (
    "market_report",
    "sentiment_report",
    "news_report",
    "fundamentals_report",
    "investment_plan",
    "trader_investment_plan",
    "final_trade_decision",
)


def summarize_chunk(chunk: Dict[str, Any]) -> Dict[str, Any]:
    summary: Dict[str, Any] = {}
    msgs = chunk.get("messages") or []
    summary["message_count"] = len(msgs)
    if msgs:
        summary["last_message"] = _serialize_message(msgs[-1])

    for key in REPORT_KEYS:
        val = chunk.get(key)
        if val:
            summary[key] = _preview(val, 200)

    inv = chunk.get("investment_debate_state")
    if inv:
        if isinstance(inv, dict):
            inv_d = inv
        else:
            inv_d = dict(inv)
        for k in ("bull_history", "bear_history", "judge_decision"):
            if inv_d.get(k):
                summary[f"invest_{k}"] = _preview(inv_d[k], 160)

    risk = chunk.get("risk_debate_state")
    if risk:
        if isinstance(risk, dict):
            risk_d = risk
        else:
            risk_d = dict(risk)
        for k in ("aggressive_history", "conservative_history", "neutral_history", "judge_decision"):
            if risk_d.get(k):
                summary[f"risk_{k}"] = _preview(risk_d[k], 160)

    return summary


def _results_dir() -> Path:
    from tradingagents.default_config import DEFAULT_CONFIG

    import os

    return Path(os.getenv("TRADINGAGENTS_RESULTS_DIR", DEFAULT_CONFIG["results_dir"])).resolve()


def run_graph_stream_worker(
    req: RunRequest,
    q: "queue.Queue[Optional[Tuple[str, Any]]]",
) -> None:
    """Push (kind, payload) then None. kinds: step | complete | error."""
    try:
        ta = create_trading_graph(req)
        ticker = req.ticker.strip()
        date_s = req.analysis_date.strip()
        init = ta.propagator.create_initial_state(ticker, date_s)
        args = ta.propagator.get_graph_args()
        trace: List[Dict[str, Any]] = []
        for i, chunk in enumerate(ta.graph.stream(init, **args)):
            trace.append(chunk)
            q.put(
                (
                    "step",
                    {"index": i, "summary": summarize_chunk(chunk)},
                )
            )
        if not trace:
            q.put(("error", "Graph produced no output."))
            return

        final = trace[-1]
        raw_rating = ta.process_signal(final.get("final_trade_decision") or "")
        rating = normalize_rating(str(raw_rating).strip())

        full_decision = final.get("final_trade_decision") or ""
        fd = str(full_decision)
        excerpt = (fd[:8000] + "…") if len(fd) > 8000 else fd

        execution = execute_decision(
            ticker=ticker,
            rating_raw=rating,
            execution_mode=req.execution_mode,
            order_qty=req.order_qty,
            results_dir=_results_dir(),
            paper_trading=req.alpaca_paper,
        )

        q.put(
            (
                "complete",
                {
                    "ticker": ticker,
                    "analysis_date": date_s,
                    "rating": rating,
                    "execution": execution,
                    "final_decision_excerpt": excerpt,
                },
            )
        )
    except Exception:
        q.put(("error", traceback.format_exc()))
    finally:
        q.put(None)


def start_stream_thread(req: RunRequest) -> Tuple[threading.Thread, queue.Queue]:
    q: queue.Queue[Optional[Tuple[str, Any]]] = queue.Queue(maxsize=200)
    th = threading.Thread(target=run_graph_stream_worker, args=(req, q), daemon=True)
    th.start()
    return th, q


def sse_json_dumps(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, default=str)
