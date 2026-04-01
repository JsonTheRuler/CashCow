# ADR-003: Mock-First Development Strategy

## Status
Accepted

## Context
Four agents are building modules in parallel. Each module depends on data from other modules or external APIs. We cannot block on API access or other modules being ready. We also need a "demo mode" insurance policy for the hackathon presentation.

**Options considered:**
1. **Contract-first with OpenAPI specs** — Define API schemas, generate stubs.
2. **Mock-first with frozen sample data** — Each module ships with realistic mock data and works standalone.
3. **Integration-first** — Build modules sequentially, each depending on the previous.

## Decision
**Option 2: Mock-first with frozen sample data.**

Every module MUST:
1. Work standalone with `python -m app.<module>` using mock data.
2. Export a `get_mock_*()` function returning realistic sample data.
3. Accept data via function parameters (not by fetching it internally).

## Rationale

- **Parallel development**: Agent building `scorer.py` doesn't need to wait for `data.py` to be done. It uses `get_mock_markets()` and `get_mock_yields()`.
- **Demo insurance**: If Polymarket API is down during presentation, `demo.py` activates mock data for every module. The audience sees the full pipeline working.
- **Testing**: Integration tests use mock data. No API keys needed in CI.
- **Debugging**: Deterministic inputs make bugs reproducible.

## Mock Data Contract

Each module defines frozen dataclasses for its inputs and outputs:

```python
# data.py exports:
def get_mock_markets() -> list[dict]: ...
def get_mock_yields() -> list[dict]: ...

# scorer.py accepts:
def score_items(items: list[dict]) -> list[ScoredItem]: ...

# extractor.py accepts:
def extract_tickers(markets: list[dict]) -> list[TickerSignal]: ...
```

## Consequences
- Mock data must be realistic enough to demonstrate all edge cases.
- Mock data must be kept in sync with actual API response shapes.
- `demo.py` becomes the single switch: `USE_DEMO_MODE=true` activates mocks everywhere.
- Every PR must include mock data for new data shapes.
