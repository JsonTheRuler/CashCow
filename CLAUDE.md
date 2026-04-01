# CLAUDE.md — Cash Cow Master Project File

> **This is the single source of truth for the Cash Cow project.**
> Every agent (Claude Code, Cursor, ChatGPT, Gemini, Grok, Manus, Perplexity) must follow this file.
> Every pull request must conform to this structure. No exceptions.

---

## Project identity

**Cash Cow** is an autonomous market intelligence engine that converts prediction market data, DeFi yield opportunities, and multi-agent trading signals into short-form video content. Built for a 48-hour hackathon.

**Repository:** `cash-cow`
**Language:** Python 3.11+
**License:** MIT
**Main branch:** `main`

---

## Repository structure

```
cash-cow/
├── CLAUDE.md                  ← YOU ARE HERE — master project spec
├── README.md                  ← Public-facing project description
├── .env.example               ← Template for API keys (NEVER commit real keys)
├── .gitignore
├── docker-compose.yml         ← MoneyPrinterTurbo + services
├── requirements.txt           ← Python dependencies
├── pyproject.toml             ← Project metadata
│
├── app/                       ← Core application logic (CC#2 owns this)
│   ├── __init__.py
│   ├── api.py                 ← FastAPI unified backend (port 8090)
│   ├── scorer.py              ← Cash Cow scoring algorithm
│   ├── extractor.py           ← Ticker extraction from market questions
│   ├── prompts.py             ← Video script templates (5 vibes)
│   ├── data.py                ← Data layer with caching + fallbacks
│   ├── sentiment.py           ← Grok social sentiment integration
│   ├── logger.py              ← Structured logging + state.json writer
│   ├── demo.py                ← Demo mode (hackathon insurance policy)
│   └── cli.py                 ← CLI interface
│
├── bridge/                    ← Integration layer (CC#1 owns this)
│   ├── __init__.py
│   ├── bridge.py              ← Polymarket → MoneyPrinterTurbo connector
│   ├── trading_signal.py      ← TradingAgents adapter
│   ├── forecaster.py          ← TimesFM price forecasting
│   └── orchestrator.py        ← Main pipeline loop (runs every 15 min)
│
├── dashboard/                 ← Frontend (Cursor owns this)
│   ├── dashboard.py           ← Streamlit dashboard (port 8502)
│   ├── components/            ← Reusable Streamlit components
│   └── assets/                ← CSS, images, logo
│
├── intel/                     ← Intelligence reports (Grok + Perplexity own this)
│   ├── social_intel_report.md ← Grok's X/Twitter sentiment analysis
│   ├── hook_templates.json    ← Extracted viral hooks for video scripts
│   └── divergence_alerts.json ← Sentiment-odds divergence data
│
├── config/                    ← Configuration
│   ├── default.yaml           ← Default settings
│   └── turbo_config.toml      ← MoneyPrinterTurbo config reference
│
├── logs/                      ← Runtime logs (gitignored)
│   ├── pipeline.log
│   ├── api.log
│   └── videos.log
│
├── state.json                 ← Live pipeline state (gitignored)
│
└── tests/                     ← Minimal tests
    ├── test_scorer.py
    ├── test_extractor.py
    └── test_bridge.py
```

---

## Branch strategy

Every agent works on a **dedicated branch** and submits PRs to `main`.

| Branch name | Owner | Contains |
|---|---|---|
| `main` | Protected | Merged, working code only |
| `infra/setup` | Claude Code #1 | Docker, MoneyPrinterTurbo, bridge, orchestrator |
| `app/core` | Claude Code #2 | scorer, extractor, prompts, api, data, logger, demo, cli |
| `dashboard/ui` | Cursor | Streamlit dashboard, components, assets |
| `intel/prompts` | ChatGPT | DeepAgents orchestrator, prompt templates, scoring logic |
| `intel/forecast` | Gemini | TimesFM integration, DeFi pipeline, market analytics |
| `intel/social` | Grok | Social sentiment report, hook templates, divergence data |

**Merge order** (respects dependency chain):
1. `infra/setup` → `main` (foundation)
2. `app/core` → `main` (application logic)
3. `intel/prompts` + `intel/forecast` + `intel/social` → `main` (can merge in parallel)
4. `dashboard/ui` → `main` (last, depends on API)

**PR rules:**
- Every PR must include a working `if __name__ == "__main__"` test in each new Python file
- No API keys, secrets, or .env files in PRs
- Max 500 lines per PR (split large changes)
- Describe what the PR does in 1 sentence in the PR title

---

## Coding conventions

### Python style
- Python 3.11+ only
- Type hints on ALL function signatures
- Docstrings on ALL public functions (Google style)
- f-strings for formatting (no .format() or %)
- 4-space indentation, max 100 chars per line
- Snake_case for functions and variables, PascalCase for classes

### Error handling
- ALL external API calls wrapped in try/except with 5-second timeouts
- ALL failures fall back to sample/mock data — NEVER crash
- Log errors to appropriate log file, then continue
- Use this pattern everywhere:

```python
def fetch_markets(n: int = 5) -> list[dict]:
    """Fetch trending markets from Polymarket Gamma API."""
    try:
        r = requests.get(
            "https://gamma-api.polymarket.com/markets",
            params={"active": "true", "limit": n, "order": "volume24hr", "ascending": "false"},
            timeout=5,
        )
        r.raise_for_status()
        return r.json()
    except Exception as e:
        logger.warning(f"Polymarket API failed: {e}, using sample data")
        return SAMPLE_MARKETS
```

### Imports
- Standard library first, blank line, third-party, blank line, local
- Absolute imports only (from app.scorer import score_market)
- No wildcard imports (no `from x import *`)

### Constants
- ALL API URLs as module-level constants in SCREAMING_SNAKE_CASE
- ALL sample/fallback data in a `_samples.py` file or at module top

---

## External API reference

**None of these require payment. All have free tiers or are completely open.**

| API | Base URL | Auth | Rate limit | Used by |
|---|---|---|---|---|
| Polymarket Gamma | `https://gamma-api.polymarket.com` | None | 300/10s | bridge.py, data.py |
| Polymarket CLOB | `https://clob.polymarket.com` | None (reads) | 300/10s | forecaster.py |
| DeFi Llama | `https://api.llama.fi` | None | Generous | data.py |
| MoneyPrinterTurbo | `http://127.0.0.1:8080` | None (local) | N/A | bridge.py, api.py |
| Cash Cow API | `http://127.0.0.1:8090` | None (local) | N/A | dashboard.py |

### Key endpoints

**Polymarket — trending markets:**
```
GET https://gamma-api.polymarket.com/markets?active=true&order=volume24hr&ascending=false&limit=10
```

**Polymarket — single market detail:**
```
GET https://gamma-api.polymarket.com/markets?slug={slug}
```

**Polymarket — price history (for TimesFM):**
```
GET https://clob.polymarket.com/prices-history?market={condition_id}&interval=1d&fidelity=60
```

**DeFi Llama — all yield pools:**
```
GET https://api.llama.fi/pools
```

**DeFi Llama — pool APY history:**
```
GET https://api.llama.fi/chart/{pool_uuid}
```

**MoneyPrinterTurbo — generate video:**
```
POST http://127.0.0.1:8080/api/v1/videos
Content-Type: application/json
{
  "video_subject": "topic string here",
  "video_script": "",
  "video_aspect": "9:16",
  "video_count": 1,
  "video_source": "pexels",
  "voice_name": "en-US-AndrewNeural-Male",
  "subtitle_enabled": true
}
```

**MoneyPrinterTurbo — check task status:**
```
GET http://127.0.0.1:8080/api/v1/tasks
```

---

## Port allocation

| Port | Service | Owner |
|---|---|---|
| 8080 | MoneyPrinterTurbo FastAPI | CC#1 (Docker) |
| 8501 | MoneyPrinterTurbo Streamlit UI | CC#1 (Docker) |
| 8502 | Cash Cow Streamlit Dashboard | Cursor |
| 8090 | Cash Cow Unified API | CC#2 |

---

## Environment variables

Copy `.env.example` to `.env` and fill in your keys.

```bash
# LLM (pick one, Gemini recommended for free tier)
GEMINI_API_KEY=
OPENAI_API_KEY=

# Video footage
PEXELS_API_KEY=
PIXABAY_API_KEY=

# Trading analysis
FINNHUB_API_KEY=

# Optional
ELEVENLABS_API_KEY=
```

**NEVER commit `.env` to the repo. It is in `.gitignore`.**

---

## Agent responsibilities

### Claude Code #1 — Infrastructure lead
- **Branch:** `infra/setup`
- **Owns:** docker-compose.yml, bridge/, MoneyPrinterTurbo config
- **Delivers:** Working Polymarket → video pipeline
- **First PR by:** Hour 8

### Claude Code #2 — Application builder
- **Branch:** `app/core`
- **Owns:** app/ directory (all modules)
- **Delivers:** Scoring engine, API layer, CLI, demo mode
- **First PR by:** Hour 6 (scorer.py + extractor.py + prompts.py)

### Cursor — Dashboard builder
- **Branch:** `dashboard/ui`
- **Owns:** dashboard/ directory
- **Delivers:** Streamlit dashboard pulling from Cash Cow API at :8090
- **First PR by:** Hour 10

### ChatGPT — Intelligence layer
- **Branch:** `intel/prompts`
- **Owns:** DeepAgents orchestrator, advanced prompt templates
- **Delivers:** Python files dropped into app/ or bridge/
- **First PR by:** Hour 8

### Gemini — Forecasting engine
- **Branch:** `intel/forecast`
- **Owns:** TimesFM integration, DeFi analytics
- **Delivers:** forecaster.py, defi_pipeline.py, market_analytics.py
- **First PR by:** Hour 12

### Grok — Social intelligence
- **Branch:** `intel/social`
- **Owns:** intel/ directory
- **Delivers:** social_intel_report.md, hook_templates.json, divergence_alerts.json
- **First PR by:** Hour 10

### Manus — Operations
- Does NOT submit PRs
- Provides API keys via secure channel
- Performs E2E testing on merged main branch

### Perplexity — Research support
- Does NOT submit PRs
- Provides troubleshooting answers on demand

---

## Data flow

```
Polymarket Gamma API ──→ data.py (cache) ──→ scorer.py (rank)
                                │                  │
DeFi Llama API ────────→ data.py (cache) ──→ scorer.py (rank)
                                │                  │
Grok X/Twitter ────────→ sentiment.py ─────→ scorer.py (boost)
                                                   │
                                          ┌────────┴────────┐
                                          ↓                  ↓
                                    prompts.py          extractor.py
                                    (video script)      (find tickers)
                                          │                  │
                                          ↓                  ↓
                                    bridge.py           trading_signal.py
                                    (→ Turbo API)       (→ TradingAgents)
                                          │                  │
                                          ↓                  ↓
                                    VIDEO OUTPUT        SIGNAL OUTPUT
                                          │                  │
                                          └────────┬─────────┘
                                                   ↓
                                             state.json
                                                   ↓
                                          ┌────────┴────────┐
                                          ↓                  ↓
                                    dashboard.py        api.py
                                    (Streamlit :8502)   (FastAPI :8090)
```

---

## Scoring algorithm specification

All agents implementing scoring MUST use this formula:

### Prediction market score (0-100)

```python
controversy = 100 - abs(yes_pct - 50) * 2      # 50/50 = 100, extremes = 0
volume_score = min(100, math.log10(max(volume_24h, 1)) * 15)
time_pressure = 1.5 if days_until_end <= 7 else (1.2 if days_until_end <= 30 else 1.0)
clarity = max(0, 100 - len(question))           # shorter = clearer

raw = (controversy * 0.35) + (volume_score * 0.30) + (clarity * 0.15)
score = min(100, raw * time_pressure)

# Social boost from Grok data (if available)
if social_divergence_score > 7:
    score = min(100, score * 1.25)
```

### DeFi yield score (0-100)

```python
apy_score = min(100, apy * 3)                   # 33% APY = max score
tvl_score = min(100, math.log10(max(tvl, 1)) * 12)
stable_bonus = 15 if is_stablecoin else 0

score = (apy_score * 0.35) + (tvl_score * 0.30) + stable_bonus + (20 * chain_diversity_factor)
```

---

## Video script specification

All video scripts MUST follow this structure:

1. **Hook** (first sentence, <15 words): Grab attention. Use data. Create curiosity.
2. **Context** (2-3 sentences): What is this market? Why does it matter?
3. **Data** (2-3 sentences): Current odds, volume, key numbers.
4. **Analysis** (2-3 sentences): What the signals say, where it might go.
5. **CTA** (last sentence): "Follow for daily market intelligence from Cash Cow."

**Total length:** 150-200 words (60-90 seconds spoken)
**Format:** Single paragraph (MoneyPrinterTurbo expects this)

---

## Testing requirements

Every Python file MUST include:

```python
if __name__ == "__main__":
    # Quick smoke test with sample data
    result = main_function(SAMPLE_INPUT)
    assert result is not None, "Function returned None"
    print(f"✓ {__file__} passed smoke test")
    print(f"  Result: {result}")
```

Run all tests: `python -m pytest tests/ -v`
Run single module: `python -m app.scorer`

---

## Git workflow for agents

### Initial setup (Claude Code #1 does this ONCE):

```bash
cd ~/cashcow
git init
git remote add origin https://github.com/YOUR_USERNAME/cash-cow.git

# Create .gitignore
cat > .gitignore << 'EOF'
.env
__pycache__/
*.pyc
logs/
state.json
*.mp4
*.avi
*.mov
node_modules/
.DS_Store
MoneyPrinterTurbo/
TradingAgents/
timesfm/
EOF

# Copy this CLAUDE.md to the repo root
# Commit and push
git add -A
git commit -m "init: Cash Cow project scaffold with CLAUDE.md"
git push -u origin main
```

### Each agent creates their branch:

```bash
git checkout -b infra/setup    # CC#1
git checkout -b app/core       # CC#2
git checkout -b dashboard/ui   # Cursor
git checkout -b intel/prompts  # ChatGPT output
git checkout -b intel/forecast # Gemini output
git checkout -b intel/social   # Grok output
```

### Submitting work:

```bash
git add -A
git commit -m "feat(app): add scorer.py with market ranking algorithm"
git push origin app/core
# Then create PR on GitHub
```

### Commit message format:

```
feat(scope): description     ← new feature
fix(scope): description      ← bug fix
docs(scope): description     ← documentation
refactor(scope): description ← code restructure
```

Scopes: `infra`, `app`, `bridge`, `dashboard`, `intel`, `config`

---

## Dependencies

```
# requirements.txt
requests>=2.31.0
fastapi>=0.109.0
uvicorn>=0.27.0
streamlit>=1.31.0
pandas>=2.2.0
plotly>=5.18.0
rich>=13.7.0
click>=8.1.0
pyyaml>=6.0.1
python-dotenv>=1.0.0
colorama>=0.4.6

# Optional (install as needed)
# timesfm[torch]>=1.2.6     ← TimesFM forecasting
# tradingagents>=0.2.2       ← TradingAgents framework
# deepagents>=0.4.12         ← LangChain DeepAgents
# py-clob-client>=0.1.0      ← Polymarket CLOB SDK
```

---

## Definition of done

The hackathon demo is "done" when:

- [ ] `python -m app.demo` runs a 30-second theatrical demo with zero errors
- [ ] `python bridge/bridge.py` fetches live Polymarket data and triggers video generation
- [ ] `streamlit run dashboard/dashboard.py` shows the live dashboard
- [ ] At least 3 videos have been generated from real Polymarket markets
- [ ] The scoring algorithm ranks markets and yields on a 0-100 scale
- [ ] TradingAgents returns Buy/Hold/Sell signals for detected tickers
- [ ] The dashboard displays all 4 sections (markets, signals, yields, videos)
- [ ] `python -m app.cli status` shows system health

**If everything breaks, `python -m app.demo` is the fallback. Build it early.**

---

## This repository (merged monorepo)

The following paths are **in-tree** on `main` / `feature/tradingagents-web-console` (not gitignored):

| Component | Location | Run |
|-----------|-----------|-----|
| TradingAgents (upstream framework) | `tradingagents/`, `cli/`, `main.py` | `tradingagents` CLI or `python main.py` |
| FastAPI web console | `webapp/` | `ta-web` or `uvicorn webapp.main:app --port 8765` |
| Streamlit dashboard | `dashboard.py` (repo root) | `streamlit run dashboard.py --server.port 8502` |
| Pipeline bridge (sidebar) | `bridge.py` (repo root) | `python bridge.py` |
| Orchestrator state | `state.json` (gitignored; template `state.json.example`) | — |

Install: `pip install -e ".[web,dashboard]"` (see `pyproject.toml`).

**Note:** The scaffold above references `app/`, `bridge/`, `dashboard/dashboard.py`. This fork may use root-level `bridge.py` and `dashboard.py` until those packages are aligned. PRs target `main` (one feature per PR).
