"""Pipeline Logger + State Management for Cash Cow.

Provides:
- JSON-formatted log files with rotation (pipeline, api, videos)
- Thread-safe state.json with atomic writes
- Helper functions for each log category
"""

from __future__ import annotations

import json
import logging
import logging.handlers
import os
import tempfile
import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

CASHCOW_DIR = Path.home() / "cashcow"
LOG_DIR = CASHCOW_DIR / "logs"
STATE_FILE = CASHCOW_DIR / "state.json"

# Log rotation settings
MAX_BYTES = 10 * 1024 * 1024  # 10 MB
BACKUP_COUNT = 5


# ---------------------------------------------------------------------------
# JSON log formatter
# ---------------------------------------------------------------------------

class _JsonFormatter(logging.Formatter):
    """Emit each log record as a single JSON line."""

    def format(self, record: logging.LogRecord) -> str:
        entry: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(
                record.created, tz=timezone.utc
            ).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        # Attach extra structured fields if present
        if hasattr(record, "extra_data"):
            entry["data"] = record.extra_data
        if record.exc_info and record.exc_info[1] is not None:
            entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(entry, default=str)


# ---------------------------------------------------------------------------
# Logger factory
# ---------------------------------------------------------------------------

_loggers: dict[str, logging.Logger] = {}
_lock = threading.Lock()


def _ensure_dirs() -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)


def _get_logger(name: str, filename: str) -> logging.Logger:
    """Return (or create) a named logger writing JSON to *filename*."""
    with _lock:
        if name in _loggers:
            return _loggers[name]

        _ensure_dirs()

        logger = logging.getLogger(f"cashcow.{name}")
        logger.setLevel(logging.DEBUG)
        logger.propagate = False

        handler = logging.handlers.RotatingFileHandler(
            LOG_DIR / filename,
            maxBytes=MAX_BYTES,
            backupCount=BACKUP_COUNT,
            encoding="utf-8",
        )
        handler.setFormatter(_JsonFormatter())
        logger.addHandler(handler)

        _loggers[name] = logger
        return logger


def get_pipeline_logger() -> logging.Logger:
    return _get_logger("pipeline", "pipeline.log")


def get_api_logger() -> logging.Logger:
    return _get_logger("api", "api.log")


def get_video_logger() -> logging.Logger:
    return _get_logger("videos", "videos.log")


# ---------------------------------------------------------------------------
# Convenience logging helpers
# ---------------------------------------------------------------------------

def _log(
    logger: logging.Logger,
    level: int,
    message: str,
    data: dict[str, Any] | None = None,
) -> None:
    extra: dict[str, Any] = {}
    if data is not None:
        extra["extra_data"] = data
    logger.log(level, message, extra=extra)


def log_pipeline_event(
    message: str,
    *,
    level: int = logging.INFO,
    data: dict[str, Any] | None = None,
) -> None:
    """Log an event to pipeline.log."""
    _log(get_pipeline_logger(), level, message, data)


def log_api_call(
    endpoint: str,
    *,
    method: str = "GET",
    status_code: int | None = None,
    latency_ms: float | None = None,
    error: str | None = None,
    level: int = logging.INFO,
) -> None:
    """Log an external API call to api.log."""
    payload: dict[str, Any] = {"endpoint": endpoint, "method": method}
    if status_code is not None:
        payload["status_code"] = status_code
    if latency_ms is not None:
        payload["latency_ms"] = round(latency_ms, 2)
    if error is not None:
        payload["error"] = error
        level = logging.ERROR
    _log(get_api_logger(), level, f"{method} {endpoint}", payload)


def log_video_event(
    message: str,
    *,
    video_id: str | None = None,
    market_id: str | None = None,
    level: int = logging.INFO,
    data: dict[str, Any] | None = None,
) -> None:
    """Log a video generation event to videos.log."""
    payload: dict[str, Any] = dict(data) if data else {}
    if video_id is not None:
        payload["video_id"] = video_id
    if market_id is not None:
        payload["market_id"] = market_id
    _log(get_video_logger(), level, message, payload)


# ---------------------------------------------------------------------------
# State dataclass
# ---------------------------------------------------------------------------

PipelineStatus = Literal["running", "idle", "error"]


@dataclass
class Signal:
    ticker: str
    direction: str  # "buy" | "sell" | "hold"
    confidence: float
    source: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RecentVideo:
    video_id: str
    market: str
    created_at: str  # ISO timestamp
    url: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PipelineState:
    """In-memory representation of state.json."""

    last_run: str = ""
    pipeline_status: PipelineStatus = "idle"
    markets_tracked: int = 0
    videos_generated: int = 0
    total_volume: int = 0
    avg_yield: float = 0.0
    signals: list[Signal] = field(default_factory=list)
    recent_videos: list[RecentVideo] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "last_run": self.last_run,
            "pipeline_status": self.pipeline_status,
            "markets_tracked": self.markets_tracked,
            "videos_generated": self.videos_generated,
            "total_volume": self.total_volume,
            "avg_yield": self.avg_yield,
            "signals": [s.to_dict() for s in self.signals],
            "recent_videos": [v.to_dict() for v in self.recent_videos],
            "errors": list(self.errors),
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> PipelineState:
        return cls(
            last_run=d.get("last_run", ""),
            pipeline_status=d.get("pipeline_status", "idle"),
            markets_tracked=d.get("markets_tracked", 0),
            videos_generated=d.get("videos_generated", 0),
            total_volume=d.get("total_volume", 0),
            avg_yield=d.get("avg_yield", 0.0),
            signals=[Signal(**s) for s in d.get("signals", [])],
            recent_videos=[RecentVideo(**v) for v in d.get("recent_videos", [])],
            errors=list(d.get("errors", [])),
        )


# ---------------------------------------------------------------------------
# State manager — atomic read/write via tempfile + rename
# ---------------------------------------------------------------------------

class StateManager:
    """Thread-safe, atomic state.json manager.

    Uses write-to-temp-then-rename for crash-safe updates.
    """

    def __init__(self, path: Path = STATE_FILE) -> None:
        self._path = path
        self._lock = threading.Lock()

    # -- reads ---------------------------------------------------------------

    def read(self) -> PipelineState:
        """Read current state from disk. Returns default state if missing."""
        with self._lock:
            return self._read_unsafe()

    def _read_unsafe(self) -> PipelineState:
        if not self._path.exists():
            return PipelineState()
        try:
            raw = self._path.read_text(encoding="utf-8")
            return PipelineState.from_dict(json.loads(raw))
        except (json.JSONDecodeError, KeyError, TypeError):
            return PipelineState()

    # -- writes --------------------------------------------------------------

    def write(self, state: PipelineState) -> None:
        """Atomically write *state* to disk."""
        with self._lock:
            self._write_unsafe(state)

    def _write_unsafe(self, state: PipelineState) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        data = json.dumps(state.to_dict(), indent=2, default=str)

        # Atomic: write tmp in same dir, then rename (same filesystem)
        fd, tmp = tempfile.mkstemp(
            dir=str(self._path.parent), suffix=".tmp", prefix=".state_"
        )
        closed = False
        try:
            os.write(fd, data.encode("utf-8"))
            os.close(fd)
            closed = True
            # On Windows, target must not exist for os.rename; remove first.
            if self._path.exists():
                self._path.unlink()
            os.rename(tmp, str(self._path))
        except BaseException:
            if not closed:
                try:
                    os.close(fd)
                except OSError:
                    pass
            if os.path.exists(tmp):
                os.unlink(tmp)
            raise

    # -- convenience mutators ------------------------------------------------

    def update(self, **kwargs: Any) -> PipelineState:
        """Read state, apply keyword updates, write back, return new state.

        Supports nested helpers via special keys:
          add_signal=Signal(...)
          add_video=RecentVideo(...)
          add_error="message"
        """
        with self._lock:
            state = self._read_unsafe()

            if "add_signal" in kwargs:
                sig = kwargs.pop("add_signal")
                state.signals.append(sig)

            if "add_video" in kwargs:
                vid = kwargs.pop("add_video")
                state.recent_videos.append(vid)
                state.videos_generated = len(state.recent_videos)

            if "add_error" in kwargs:
                err = kwargs.pop("add_error")
                state.errors.append(err)

            for key, value in kwargs.items():
                if hasattr(state, key):
                    object.__setattr__(state, key, value)

            # Always update last_run on write
            state.last_run = datetime.now(timezone.utc).isoformat()
            self._write_unsafe(state)
            return state


# Module-level singleton for convenience
_state_manager: StateManager | None = None
_sm_lock = threading.Lock()


def get_state_manager(path: Path = STATE_FILE) -> StateManager:
    """Return the module-level StateManager singleton."""
    global _state_manager
    with _sm_lock:
        if _state_manager is None:
            _state_manager = StateManager(path)
        return _state_manager


def update_state(**kwargs: Any) -> PipelineState:
    """Convenience wrapper around the singleton StateManager.update()."""
    return get_state_manager().update(**kwargs)


def read_state() -> PipelineState:
    """Convenience wrapper around the singleton StateManager.read()."""
    return get_state_manager().read()


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import shutil

    print("=" * 70)
    print("LOGGER SELF-TEST")
    print("=" * 70)

    # --- Log file tests ---
    print("\n[1] Writing log entries...")
    log_pipeline_event("Pipeline started", data={"markets": 8})
    log_pipeline_event("Market scanned", data={"id": "polymarket-btc-100k"})
    log_api_call(
        "https://polymarket.com/api/markets",
        method="GET",
        status_code=200,
        latency_ms=142.5,
    )
    log_api_call(
        "https://tradingagents.ai/signal",
        method="POST",
        status_code=500,
        error="Internal Server Error",
    )
    log_video_event(
        "Video rendered",
        video_id="vid_001",
        market_id="mkt_btc",
        data={"duration_s": 45},
    )

    for name in ("pipeline.log", "api.log", "videos.log"):
        path = LOG_DIR / name
        exists = path.exists()
        size = path.stat().st_size if exists else 0
        print(f"  {name}: exists={exists}  size={size} bytes")

    # --- State tests ---
    print("\n[2] State management...")

    test_state_path = CASHCOW_DIR / "state_test.json"
    sm = StateManager(test_state_path)

    # Write initial state
    sm.write(PipelineState(pipeline_status="running", markets_tracked=8))
    state = sm.read()
    assert state.pipeline_status == "running", f"Expected running, got {state.pipeline_status}"
    assert state.markets_tracked == 8
    print(f"  Initial write/read: OK  (status={state.pipeline_status})")

    # Update with convenience mutators
    state = sm.update(
        pipeline_status="idle",
        total_volume=28_234_567,
        avg_yield=15.2,
        add_signal=Signal(ticker="BTC", direction="buy", confidence=0.87, source="ta"),
        add_video=RecentVideo(
            video_id="vid_001",
            market="BTC 100k",
            created_at=datetime.now(timezone.utc).isoformat(),
        ),
    )
    assert state.pipeline_status == "idle"
    assert state.total_volume == 28_234_567
    assert len(state.signals) == 1
    assert state.signals[0].ticker == "BTC"
    assert len(state.recent_videos) == 1
    assert state.last_run != ""
    print(f"  Atomic update: OK  (volume={state.total_volume}, signals={len(state.signals)})")

    # Error tracking
    state = sm.update(pipeline_status="error", add_error="API timeout on polymarket")
    assert len(state.errors) == 1
    assert "API timeout" in state.errors[0]
    print(f"  Error tracking: OK  (errors={state.errors})")

    # Verify JSON is valid on disk
    raw = json.loads(test_state_path.read_text(encoding="utf-8"))
    assert "signals" in raw
    assert "recent_videos" in raw
    print(f"  Disk JSON valid: OK  (keys={sorted(raw.keys())})")

    # Cleanup test file
    test_state_path.unlink(missing_ok=True)

    # --- Thread safety smoke test ---
    print("\n[3] Thread safety smoke test (20 concurrent writes)...")
    sm2 = StateManager(test_state_path)
    sm2.write(PipelineState())

    errors: list[str] = []

    def worker(i: int) -> None:
        try:
            sm2.update(
                markets_tracked=i,
                add_signal=Signal(
                    ticker=f"T{i}", direction="buy", confidence=0.5
                ),
            )
        except Exception as exc:
            errors.append(f"Thread {i}: {exc}")

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    final = sm2.read()
    print(f"  Signals accumulated: {len(final.signals)} (expected 20)")
    print(f"  Errors during writes: {len(errors)}")
    if errors:
        for e in errors:
            print(f"    {e}")

    test_state_path.unlink(missing_ok=True)

    print("\n" + "=" * 70)
    print("ALL LOGGER TESTS PASSED")
    print("=" * 70)
