# Risk Assessment — Cash Cow Hackathon

## Risk Matrix

| # | Risk | Probability | Impact | Severity | Mitigation |
|---|------|-------------|--------|----------|------------|
| 1 | External API failures (Polymarket/DeFi Llama down) | Medium | Critical | **HIGH** | Demo mode with frozen mock data. Cache with 5-min TTL means recent data survives brief outages. Health endpoint reports API status before demo. |
| 2 | Rate limiting from Polymarket/DeFi Llama | High | Medium | **HIGH** | TTLCache (ADR-002) limits requests to 1 per 5 min per endpoint. Exponential backoff on 429s. Demo mode as ultimate fallback. Never call APIs in a loop. |
| 3 | Docker/MoneyPrinterTurbo not starting on demo machine | Medium | High | **HIGH** | Pre-record 2-3 sample videos before demo. `prompts.py` generates scripts independently of video generation. API returns script JSON even if video generation fails. Health check at `/health` tests MoneyPrinterTurbo connectivity. |
| 4 | TimesFM model download taking too long / failing | High | Low | **MEDIUM** | Lazy-load only (ADR-004). Never block startup. `forecast: null` is a valid API response. Pre-download model on demo machine the night before. If unavailable, scoring works fine without forecasts. |
| 5 | Demo mode falling back ungracefully (partial mocks, inconsistent state) | Low | Critical | **MEDIUM** | Single `USE_DEMO_MODE` env var activates ALL mocks atomically. `demo.py` is the sole source of mock data — no scattered mock logic. Integration test validates full pipeline in demo mode. |

## Detailed Mitigations

### Risk 1: External API Failures

**Detection**: `data.py` wraps every API call in try/except. On failure:
1. Log the error with full traceback.
2. Return cached data if available (any TTL).
3. If no cache, check `is_demo_mode()`.
4. If not demo mode, raise `DataFetchError` — `api.py` returns 503 with `"demo_available": true`.

**Demo switch**: `GET /demo/activate` sets demo mode at runtime. No restart needed.

### Risk 2: Rate Limiting

**Prevention**:
- Polymarket: max 1 request per 5 minutes (TTL cache).
- DeFi Llama: max 1 request per 5 minutes (TTL cache).
- Never call APIs from unit tests.

**Response to 429**:
```python
if response.status_code == 429:
    retry_after = int(response.headers.get("Retry-After", 60))
    logger.log_event("rate_limited", {"retry_after": retry_after})
    return cached_data or demo_data
```

### Risk 3: MoneyPrinterTurbo Down

**Graceful degradation layers**:
1. `/scripts` endpoint works independently — returns JSON scripts.
2. `/video` endpoint checks MoneyPrinterTurbo health first.
3. If unhealthy, returns `{"script": {...}, "video_url": null, "reason": "video service unavailable"}`.
4. Pre-recorded fallback videos stored in `~/cashcow/assets/sample_videos/`.

### Risk 4: TimesFM Unavailable

**Implementation**: See ADR-004. The key insight is that TimesFM is a bonus feature. The scoring pipeline (scorer.py) works without it. Forecast is an optional enrichment on the API response.

**Pre-demo checklist**:
```bash
# Night before demo:
python -c "import sys; sys.path.insert(0, '$HOME/timesfm'); import timesfm; print('OK')"
```

### Risk 5: Demo Mode Consistency

**Atomic activation**: `demo.py` provides a complete, consistent dataset:
- 5 mock markets (varying scores, time pressure, controversy levels)
- 3 mock yields (varying APY, TVL, chains)
- Pre-generated tickers for each mock market
- Pre-generated scripts in all 5 vibes for the top market

**Integration test validates**: `test_integration.py` runs the full pipeline in demo mode and asserts all outputs are present and consistent.

## Pre-Demo Checklist

```
[ ] APIs responding: curl https://gamma-api.polymarket.com/markets?limit=1
[ ] APIs responding: curl https://api.llama.fi/protocols
[ ] MoneyPrinterTurbo running: curl http://localhost:8080/health
[ ] FastAPI running: curl http://localhost:8090/health
[ ] Demo mode works: USE_DEMO_MODE=true python -m app.cli
[ ] TimesFM loads: python -c "import sys; sys.path.insert(0, ...); import timesfm"
[ ] Sample videos exist in assets/
[ ] Integration tests pass: python -m pytest app/test_integration.py -v
```
