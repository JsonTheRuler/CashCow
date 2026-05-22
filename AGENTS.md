# AGENTS.md

## Cursor Cloud specific instructions

### Project overview

Cash Cow is a monorepo with two products:

1. **Cash Cow** — Polymarket + DeFi yield scoring engine with FastAPI backend (`api.py` on `:8090`) and Streamlit dashboard (`dashboard.py` on `:8502`).
2. **TradingAgents** — Multi-agent LLM trading framework with CLI (`tradingagents` command) and web console (`webapp/` on `:8765`).

See `CLAUDE.md` for the full project spec, scoring algorithm, and coding conventions.

### Running services

| Service | Command | Port |
|---|---|---|
| Cash Cow API | `python3 api.py` | 8090 |
| Streamlit Dashboard | `streamlit run dashboard.py --server.port 8502 --server.headless true` | 8502 |
| TradingAgents Web Console | `uvicorn webapp.main:app --port 8765` | 8765 |

The dashboard depends on the API running first (it fetches from `http://127.0.0.1:8090`).

### Testing

- Run `python3 -m pytest tests/ -v` from the repo root.
- One test (`test_bridge_scoring`) has a pre-existing import error (`bridge.score_market` doesn't exist); 11/12 pass.
- No lint config is defined in the repo; `ruff check --select E,F` can be used for basic checks.

### Gotchas

- `pip install -e ".[web,dashboard]"` installs both Cash Cow and TradingAgents deps. Use `pip install -r requirements.txt` for Cash Cow only.
- `numpy` is needed by `forecaster.py` but is not declared in `requirements.txt` or `pyproject.toml`; it comes pre-installed system-wide but ensure it's available.
- Scripts installed by pip land in `~/.local/bin` — ensure `PATH` includes that directory (`export PATH="$HOME/.local/bin:$PATH"`).
- Root-level Python files (`api.py`, `dashboard.py`, `scorer.py`, etc.) are the active code. The `app/` and `bridge/` subdirectories contain earlier versions.
- TradingAgents CLI and web console require an LLM API key (e.g. `OPENAI_API_KEY`). Cash Cow core works without any API keys (uses Polymarket/DeFi Llama free APIs).
- MoneyPrinterTurbo (`:8080`) is optional; the video factory tab degrades gracefully if it's not running.
