# Integration Blueprint

## Data Flow Diagram

```
                         EXTERNAL SERVICES
    ┌─────────────────┐  ┌──────────────┐  ┌─────────────────┐
    │  Polymarket API  │  │ DeFi Llama   │  │ MoneyPrinter    │
    │  (prediction mkts)│  │ (yields)     │  │ Turbo :8080     │
    └────────┬─────────┘  └──────┬───────┘  └────────▲────────┘
             │                   │                    │
             ▼                   ▼                    │
    ┌────────────────────────────────────┐            │
    │           data.py                  │            │
    │  fetch_markets() fetch_yields()    │            │
    │  get_mock_markets() get_mock_yields│            │
    └──────────┬──────────────┬──────────┘            │
               │              │                       │
       ┌───────▼───┐   ┌─────▼──────┐                │
       │ scorer.py  │   │extractor.py│                │
       │            │   │            │                │
       │score_items │   │extract_    │                │
       │  (0-100)   │   │ tickers()  │                │
       └─────┬──────┘   └─────┬──────┘                │
             │                │                       │
             │    ┌───────────┘                       │
             ▼    ▼                                   │
    ┌──────────────────┐    ┌──────────────────┐      │
    │  sentiment.py    │    │  prompts.py       │      │
    │                  │    │                   │      │
    │ analyze_market   │    │ generate_script() │      │
    │ _sentiment()     │    │ 5 vibes:          │──────┘
    └────────┬─────────┘    │ breaking_news     │
             │              │ deep_analysis     │
             │              │ hot_take          │
             │              │ countdown         │
             │              │ explainer         │
             ▼              └───────────────────┘
    ┌──────────────────┐
    │  ~/timesfm       │  (optional, lazy-loaded)
    │  forecast_trend() │
    └──────────────────┘

    ┌──────────────────┐    ┌──────────────────┐
    │  demo.py         │    │  logger.py       │
    │                  │    │                  │
    │ activate_demo()  │    │ log_event()      │
    │ is_demo_mode()   │    │ log_error()      │
    │ get_demo_data()  │    │ get_run_log()    │
    └──────────────────┘    └──────────────────┘

    ┌──────────────────────────────────────────────────────────┐
    │                      api.py (FastAPI :8090)              │
    │                                                          │
    │  GET  /api/v1/markets    → data.fetch_markets()          │
    │  GET  /api/v1/yields     → data.fetch_yields()           │
    │  GET  /api/v1/signals    → data.fetch_signals()          │
    │  GET  /api/v1/dashboard  → data.fetch_all_dashboard_data │
    │  POST /api/v1/generate   → data.generate_video_script()  │
    │                            + data.submit_to_turbo()      │
    │  GET  /api/v1/status     → health check (all deps)       │
    │  GET  /                  → root redirect to /docs         │
    └──────────────────────────────────────────────────────────┘

    ┌──────────────────┐
    │  cli.py          │
    │                  │
    │ CLI entry point  │
    │ mirrors API      │
    │ endpoints        │
    └──────────────────┘
```

## Module Dependency Matrix

```
                data  scorer  extractor  prompts  sentiment  demo  logger  api  cli
data             -      -        -         -         -        -      ✓     -    -
scorer           ✓      -        -         -         -        -      ✓     -    -
extractor        ✓      -        -         -         -        -      ✓     -    -
prompts          -      ✓        ✓         -         ✓        -      ✓     -    -
sentiment        -      -        -         -         -        -      ✓     -    -
demo             -      -        -         -         -        -      ✓     -    -
logger           -      -        -         -         -        -      -     -    -
api              ✓      ✓        ✓         ✓         ✓        ✓      ✓     -    -
cli              -      -        -         -         -        ✓      ✓     ✓    -

Row = module, Column = depends on. ✓ = imports from.
```

## Dependency Direction Rules

1. **logger.py** depends on NOTHING. Every module can import logger.
2. **data.py** depends only on logger. It is the data source layer.
3. **scorer.py** and **extractor.py** depend on data (for types) and logger.
4. **sentiment.py** depends only on logger. It is a leaf service.
5. **prompts.py** depends on scorer, extractor, sentiment (it composes outputs).
6. **demo.py** depends only on logger. It provides mock data — it does NOT import other modules.
7. **api.py** is the composition root. It imports everything and wires them together.
8. **cli.py** imports api (reuses endpoints) and demo.

**Forbidden dependencies:**
- No module imports api.py (api is top-level only).
- No circular imports. The graph is a DAG.
- data.py NEVER imports scorer/extractor/prompts.

## Error Propagation Strategy

```
Layer 1 (data.py):     API call fails → log warning → return cached data → if no cache → raise DataFetchError
Layer 2 (scorer.py):   DataFetchError caught → log → return empty list (graceful degradation)
Layer 3 (prompts.py):  Empty scored list → generate "no data available" script → never crash
Layer 4 (api.py):      Any unhandled exception → 500 with {"error": "...", "demo_available": true}

Demo fallback at every layer:
  if is_demo_mode():
      return get_demo_data(module_name)
```

## Startup Sequence

```
1. logger.py initializes (file + stdout handlers)
2. demo.py checks USE_DEMO_MODE env var
3. data.py warms cache (optional, async background task)
4. api.py mounts all routes
5. uvicorn starts on :8090
6. TimesFM lazy-loads on first /forecast request
```
