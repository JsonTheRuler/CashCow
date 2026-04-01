# CLAUDE.md

Guidance for Claude Code and other AI assistants working in **JsonTheRuler/CashCow**.

## Project overview

**Cash Cow** is a hackathon-style monorepo that combines:

1. **TradingAgents** — upstream [TauricResearch/TradingAgents](https://github.com/TauricResearch/TradingAgents) multi-agent LLM trading framework (`tradingagents/`, `cli/`, `main.py`).
2. **FastAPI web console** — `webapp/` (`ta-web`, `/api/run`, SSE `/api/run/stream`, WebSocket `/ws/run`, optional Alpaca / Tradier / webhook execution).
3. **Streamlit dashboard** — `dashboard.py` (Polymarket, DeFi Llama yields, `state.json` signals, MoneyPrinterTurbo hooks on `:8080`, pipeline log).
4. **Pipeline bridge** — `bridge.py` (sidebar trigger; appends `logs/pipeline.log`, updates `state.json`).

Orchestrator / TimesFM / full Polymarket→video pipeline can extend `bridge.py` and writers of `state.json`.

## Install

```bash
pip install -e ".[web,dashboard]"
cp .env.example .env   # LLM keys, optional Alpaca / Tradier / webhook
```

## Run

```bash
# Interactive multi-agent CLI
tradingagents

# FastAPI console (port 8765)
ta-web
# or: uvicorn webapp.main:app --host 127.0.0.1 --port 8765

# Streamlit hackathon dashboard (port 8502; 8501 often used by MoneyPrinterTurbo)
streamlit run dashboard.py --server.port 8502
```

## Layout (high level)

| Path | Role |
|------|------|
| `tradingagents/` | LangGraph agents, dataflows, LLM clients |
| `cli/` | Typer/Rich CLI |
| `webapp/` | FastAPI + static UI |
| `dashboard.py` | Streamlit single-page dashboard |
| `bridge.py` | Pipeline entry from Streamlit sidebar |
| `state.json` | Optional; written by orchestrator — use `state.json.example` as template |
| `logs/` | `pipeline.log` (gitignored via `*.log`) |

## Configuration

- **`.env`** — API keys (never commit; see `.env.example`).
- **`state.json`** — trading signals for the dashboard; copy from `state.json.example` if missing.

## Contributing

**PRs target `main`.** One feature or fix per PR. Prefer opening an issue first for larger changes.

Upstream TradingAgents license and citation requirements still apply to framework code.
