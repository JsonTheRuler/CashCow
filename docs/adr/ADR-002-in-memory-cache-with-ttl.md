# ADR-002: In-Memory Caching with TTL vs Redis/External Cache

## Status
Accepted

## Context
Cash Cow fetches from Polymarket API and DeFi Llama API. These APIs have rate limits and latency. We need caching to:
1. Avoid hammering APIs during demo (repeated refreshes).
2. Reduce latency for the scoring pipeline.
3. Provide a fallback if APIs go down mid-demo.

**Options considered:**
1. **Redis** — External cache with TTL, pub/sub, persistence.
2. **In-memory dict with TTL** — Simple Python dict with expiry timestamps.
3. **cachetools TTLCache** — Battle-tested library, drop-in decorator.
4. **No cache** — Hit APIs every time.

## Decision
**Option 3: `cachetools.TTLCache` with a thin wrapper.**

## Rationale

| Criterion | Redis | In-Memory TTLCache | No Cache |
|-----------|-------|---------------------|----------|
| Setup time | 15-30 min (install, config) | 0 min (pip install cachetools) | 0 min |
| Demo reliability | Requires Redis running | Zero external deps | API-dependent |
| Persistence across restarts | Yes | No | N/A |
| Memory management | Automatic eviction | maxsize parameter | N/A |
| Horizontal scaling | Shared state | Per-process | N/A |

**Key factors:**
- **Single process**: ADR-001 chose monolith. No need for shared cache across processes.
- **Hackathon scope**: We will never restart during demo. In-memory is sufficient.
- **`cachetools` is mature**: TTLCache handles expiry, maxsize, and thread safety (with lock).
- **Fallback chain**: Cache miss -> API call -> on failure, demo mode data. This chain is trivial in-process.

## Implementation

```python
from cachetools import TTLCache
from threading import Lock

# Module-level cache: 100 items, 5-minute TTL
_cache = TTLCache(maxsize=100, ttl=300)
_lock = Lock()

def cached_fetch(key: str, fetcher: Callable) -> Any:
    with _lock:
        if key in _cache:
            return _cache[key]
    result = fetcher()
    with _lock:
        _cache[key] = result
    return result
```

## Consequences
- Cache is lost on restart (acceptable for hackathon).
- No cache warming — first request after startup is slow.
- If we need Redis post-hackathon, the `cached_fetch` wrapper can swap backends without changing callers.
