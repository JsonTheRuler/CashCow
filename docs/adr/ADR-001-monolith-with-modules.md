# ADR-001: Monolith with Module Separation vs Microservices

## Status
Accepted

## Context
Cash Cow needs to fetch market data, score it, extract tickers, generate video scripts, and serve an API. We have 48 hours to build, demo, and present. The team is 4-5 agents working in parallel on separate modules.

**Options considered:**
1. **Microservices** — Each module is a separate service with its own process, communicating via HTTP/gRPC.
2. **Monolith with module separation** — Single FastAPI process, modules are Python packages with clean interfaces.
3. **Serverless functions** — Each capability as a cloud function.

## Decision
**Option 2: Monolith with module separation.**

## Rationale

| Criterion | Microservices | Monolith + Modules | Serverless |
|-----------|--------------|---------------------|------------|
| Time to MVP | 12-16h (infra overhead) | 4-6h | 8-12h (cold starts, debugging) |
| Local debugging | Hard (multi-process) | Easy (single process) | Hard (emulators) |
| Deployment | Docker Compose needed | `uvicorn app.api:app` | Cloud dependency |
| Demo reliability | Network failures between services | In-process calls | Internet required |
| Parallel dev | Natural isolation | Discipline needed (interfaces) | Natural isolation |

**Key factors:**
- **48-hour constraint**: Zero tolerance for infrastructure debugging. A single `uvicorn` command must start everything.
- **Demo mode**: In-process mocking is trivial. Cross-service mocking requires service discovery stubs.
- **Shared state**: Scoring needs data from both Polymarket and DeFi Llama. In-process sharing via function calls is simpler than API serialization.
- **MoneyPrinterTurbo**: Already an external service (localhost:8080). Adding more service boundaries adds failure modes.

**Mitigation for monolith risks:**
- Each module defines a clear public API (typed dataclasses in/out).
- No module imports another module's internals — only through `__init__.py` exports.
- Dependency injection via function parameters, not global state.

## Consequences
- All modules must be importable without side effects (no code at module level that hits APIs).
- FastAPI app is the single entry point; modules are called as libraries.
- If we need to scale post-hackathon, modules can be extracted to services since they already have clean interfaces.
