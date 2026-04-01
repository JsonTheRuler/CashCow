"""Pydantic models shared by HTTP, SSE, and WebSocket entrypoints."""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class RunRequest(BaseModel):
    ticker: str = Field(..., min_length=1, max_length=32)
    analysis_date: str = Field(..., description="YYYY-MM-DD")
    llm_provider: str = "openai"
    quick_think_llm: Optional[str] = None
    deep_think_llm: Optional[str] = None
    backend_url: Optional[str] = None
    max_debate_rounds: int = Field(1, ge=1, le=5)
    analysts: List[str] = Field(
        default_factory=lambda: ["market", "social", "news", "fundamentals"]
    )
    output_language: str = "English"
    execution_mode: Literal["none", "paper", "alpaca", "tradier", "webhook"] = "paper"
    order_qty: float = Field(1.0, ge=0.01, le=1_000_000)
    alpaca_paper: bool = True


class RunResponse(BaseModel):
    ok: bool
    ticker: str
    analysis_date: str
    rating: str
    execution: Dict[str, Any]
    final_decision_excerpt: str
    error: Optional[str] = None
