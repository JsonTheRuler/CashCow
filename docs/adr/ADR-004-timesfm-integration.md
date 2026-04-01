# ADR-004: TimesFM Integration Strategy (Lazy-Load, Optional Dependency)

## Status
Accepted

## Context
TimesFM (google-research/timesfm) is a foundation model for time-series forecasting, installed at `~/timesfm`. It can add predictive power to market trend analysis. However:
- Model download is ~1.5GB and can take 10+ minutes on slow connections.
- Import time is 5-15 seconds (loads PyTorch/JAX).
- It may not be installed on all team members' machines.
- It is a "nice to have" — the core pipeline works without it.

**Options considered:**
1. **Required dependency** — Fail fast if TimesFM is not available.
2. **Lazy-load, optional** — Import only when needed, graceful fallback.
3. **Separate microservice** — Run TimesFM in its own process.
4. **Skip entirely** — Don't integrate for the hackathon.

## Decision
**Option 2: Lazy-load with optional dependency and graceful fallback.**

## Rationale

- **Import cost**: Loading TimesFM at startup adds 5-15s to server boot. Lazy-loading means it only loads when a forecast endpoint is hit.
- **Optional**: If `~/timesfm` doesn't exist or import fails, the system returns `forecast: null` instead of crashing.
- **Demo flexibility**: We can show the forecast feature only if it's working. If it's flaky, we skip it in the demo without touching any code.

## Implementation

```python
# In a forecasting module or within scorer.py:

_timesfm = None
_timesfm_available = None

def _load_timesfm():
    global _timesfm, _timesfm_available
    if _timesfm_available is not None:
        return _timesfm_available
    try:
        import sys
        sys.path.insert(0, os.path.expanduser("~/timesfm"))
        import timesfm
        _timesfm = timesfm
        _timesfm_available = True
    except (ImportError, Exception):
        _timesfm_available = False
    return _timesfm_available

def forecast_trend(series: list[float], horizon: int = 24) -> list[float] | None:
    if not _load_timesfm():
        return None  # Graceful fallback
    # ... use _timesfm for prediction
```

## API Behavior

```json
// TimesFM available:
{"trend_score": 78, "forecast": [0.82, 0.85, 0.79, ...]}

// TimesFM unavailable:
{"trend_score": 78, "forecast": null}
```

## Consequences
- First forecast request is slow (model load). Subsequent requests are fast.
- No TimesFM in requirements.txt — it's a system-level install.
- Integration tests mock TimesFM entirely — they never load the real model.
- API consumers must handle `forecast: null` gracefully.
