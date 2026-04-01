"""Build config and TradingAgentsGraph from a RunRequest."""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.graph.trading_graph import TradingAgentsGraph

from webapp.schemas import RunRequest


def build_config(req: RunRequest) -> Dict[str, Any]:
    cfg = DEFAULT_CONFIG.copy()
    cfg["llm_provider"] = req.llm_provider.lower()
    cfg["quick_think_llm"] = req.quick_think_llm or DEFAULT_CONFIG["quick_think_llm"]
    cfg["deep_think_llm"] = req.deep_think_llm or DEFAULT_CONFIG["deep_think_llm"]
    cfg["max_debate_rounds"] = req.max_debate_rounds
    cfg["max_risk_discuss_rounds"] = req.max_debate_rounds
    cfg["output_language"] = req.output_language
    if req.backend_url:
        cfg["backend_url"] = req.backend_url
    cfg["data_vendors"] = {
        "core_stock_apis": "yfinance",
        "technical_indicators": "yfinance",
        "fundamental_data": "yfinance",
        "news_data": "yfinance",
    }
    return cfg


def selected_analysts(req: RunRequest) -> List[str]:
    valid = {"market", "social", "news", "fundamentals"}
    analysts = [a.lower() for a in req.analysts if a.lower() in valid]
    if not analysts:
        analysts = ["market", "news"]
    return analysts


def create_trading_graph(req: RunRequest) -> TradingAgentsGraph:
    cfg = build_config(req)
    return TradingAgentsGraph(selected_analysts(req), debug=False, config=cfg)


def propagate_request(req: RunRequest) -> Tuple[Dict[str, Any], str]:
    ta = create_trading_graph(req)
    return ta.propagate(req.ticker.strip(), req.analysis_date.strip())
