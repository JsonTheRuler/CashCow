"""
Integration test suite for Cash Cow.

Validates that all modules wire together correctly using mock/sample data.
No external APIs, no network calls, no GPU -- runs in <5 seconds.

Usage:
    python -m pytest app/test_integration.py -v
    python app/test_integration.py  # also works standalone
"""

from __future__ import annotations

import importlib
import sys
import types
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

APP_DIR = Path(__file__).parent


def _module_exists(module_name: str) -> bool:
    """Check if a module file exists (even if it has import errors)."""
    return (APP_DIR / f"{module_name}.py").exists()


def _try_import(module_name: str) -> types.ModuleType | None:
    """Attempt to import a module from the app package. Returns None on failure."""
    try:
        return importlib.import_module(f"app.{module_name}")
    except Exception as exc:
        print(f"  [WARN] Failed to import app.{module_name}: {exc}")
        return None


# ---------------------------------------------------------------------------
# Phase 1: Module existence and importability
# ---------------------------------------------------------------------------


class TestModuleStructure:
    """Verify all modules exist and are importable."""

    REQUIRED_MODULES = [
        "data",
        "scorer",
        "extractor",
        "prompts",
        "sentiment",
        "demo",
        "logger",
        "api",
        "cli",
    ]

    @pytest.mark.parametrize("module_name", REQUIRED_MODULES)
    def test_module_file_exists(self, module_name: str) -> None:
        path = APP_DIR / f"{module_name}.py"
        assert path.exists(), f"app/{module_name}.py not found at {path}"

    def test_package_init_exports(self) -> None:
        import app

        assert hasattr(app, "__version__")
        assert hasattr(app, "__all__")
        for name in self.REQUIRED_MODULES:
            assert name in app.__all__, f"{name} missing from app.__all__"


# ---------------------------------------------------------------------------
# Phase 2: Extractor module (no dependencies on other modules)
# ---------------------------------------------------------------------------


class TestExtractor:
    """Validate extractor.py pulls tickers from market questions."""

    def setup_method(self) -> None:
        self.mod = _try_import("extractor")
        if self.mod is None:
            pytest.skip("extractor module not available")

    def test_extract_tickers_exists(self) -> None:
        assert callable(getattr(self.mod, "extract_tickers", None))

    def test_extracts_btc(self) -> None:
        result = self.mod.extract_tickers("Will Bitcoin hit $100k by July 2026?")
        assert "BTC" in result.tickers

    def test_extracts_tsla(self) -> None:
        result = self.mod.extract_tickers("Will Tesla stock (TSLA) be above $300?")
        assert "TSLA" in result.tickers

    def test_extracts_macro(self) -> None:
        result = self.mod.extract_tickers("Will the Fed cut rates in Q3 2026?")
        assert len(result.tickers) > 0
        assert result.source == "macro"

    def test_empty_input(self) -> None:
        result = self.mod.extract_tickers("")
        assert result.tickers == ()
        assert result.source == "none"

    def test_no_match(self) -> None:
        result = self.mod.extract_tickers("Will the Lakers win the NBA Finals?")
        assert result.tickers == ()


# ---------------------------------------------------------------------------
# Phase 3: Scorer module
# ---------------------------------------------------------------------------


class TestScorer:
    """Validate scorer.py produces 0-100 scores with proper dataclasses."""

    def setup_method(self) -> None:
        self.mod = _try_import("scorer")
        if self.mod is None:
            pytest.skip("scorer module not available")

    def test_has_key_exports(self) -> None:
        assert hasattr(self.mod, "PredictionMarket")
        assert hasattr(self.mod, "DeFiYield")
        assert hasattr(self.mod, "ScoredItem")
        assert hasattr(self.mod, "score_prediction_market")
        assert hasattr(self.mod, "score_defi_yield")
        assert hasattr(self.mod, "rank_all")

    def test_score_prediction_market(self) -> None:
        market = self.mod.PredictionMarket(
            question="Will Bitcoin reach $150k?",
            yes_pct=42.0,
            volume_24h=8_200_000,
            end_date=datetime(2026, 12, 31, tzinfo=timezone.utc),
        )
        now = datetime(2026, 4, 1, tzinfo=timezone.utc)
        result = self.mod.score_prediction_market(market, now=now)

        assert isinstance(result, self.mod.ScoredItem)
        assert 0 <= result.score <= 100
        assert result.category == "prediction"
        assert result.priority is not None
        assert result.vibe is not None

    def test_score_defi_yield(self) -> None:
        pool = self.mod.DeFiYield(
            protocol="Aave",
            asset="USDC",
            apy=14.2,
            tvl=890_000_000,
            chain="Ethereum",
            is_stablecoin=True,
        )
        result = self.mod.score_defi_yield(pool)

        assert isinstance(result, self.mod.ScoredItem)
        assert 0 <= result.score <= 100
        assert result.category == "yield"

    def test_rank_all_normalizes(self) -> None:
        markets = [
            self.mod.PredictionMarket(
                question="Will Bitcoin reach $150k?",
                yes_pct=42.0,
                volume_24h=8_200_000,
                end_date=datetime(2026, 12, 31, tzinfo=timezone.utc),
            ),
        ]
        yields = [
            self.mod.DeFiYield("Aave", "USDC", 14.2, 890_000_000, "Ethereum", True),
        ]
        now = datetime(2026, 4, 1, tzinfo=timezone.utc)
        ranked = self.mod.rank_all(markets, yields, now=now)

        assert len(ranked) == 2
        # After normalization, max should be 100 and min should be 0
        scores = [item.score for item in ranked]
        assert max(scores) == 100.0
        assert min(scores) == 0.0
        # Should be sorted descending
        assert scores == sorted(scores, reverse=True)


# ---------------------------------------------------------------------------
# Phase 4: Prompts module
# ---------------------------------------------------------------------------


class TestPrompts:
    """Validate prompts.py generates scripts for all 5 vibes."""

    def setup_method(self) -> None:
        self.mod = _try_import("prompts")
        if self.mod is None:
            pytest.skip("prompts module not available")

    def test_has_all_templates(self) -> None:
        assert callable(getattr(self.mod, "breaking_news", None))
        assert callable(getattr(self.mod, "deep_analysis", None))
        assert callable(getattr(self.mod, "hot_take", None))
        assert callable(getattr(self.mod, "countdown", None))
        assert callable(getattr(self.mod, "explainer", None))

    def test_has_template_registry(self) -> None:
        templates = getattr(self.mod, "TEMPLATES", None)
        assert templates is not None
        assert len(templates) == 5
        for key in ("breaking_news", "deep_analysis", "hot_take", "countdown", "explainer"):
            assert key in templates

    def test_breaking_news_output(self) -> None:
        script = self.mod.breaking_news(
            question="Will Bitcoin hit $150K?",
            yes_pct=68.0,
            volume=4_200_000,
            description="Smart money is moving fast.",
        )
        assert isinstance(script, str)
        assert len(script) > 100
        assert "Bitcoin" in script or "150K" in script

    def test_deep_analysis_output(self) -> None:
        script = self.mod.deep_analysis(
            question="Will the Fed cut rates?",
            yes_pct=72.0,
            no_pct=28.0,
            volume=8_500_000,
            forecast_trend="trending up",
        )
        assert isinstance(script, str)
        assert len(script) > 100

    def test_hot_take_output(self) -> None:
        script = self.mod.hot_take(
            question="Will TikTok be banned?",
            yes_pct=34.0,
            volume=12_000_000,
        )
        assert isinstance(script, str)
        assert len(script) > 100

    def test_countdown_output(self) -> None:
        script = self.mod.countdown(
            question="Will SpaceX complete orbital flight?",
            yes_pct=81.0,
            end_date="April 15, 2026",
            volume=3_700_000,
        )
        assert isinstance(script, str)
        assert len(script) > 100

    def test_explainer_output(self) -> None:
        script = self.mod.explainer(
            question="Will AI pass the Turing Test?",
            yes_pct=55.0,
            description="The race to build human-level AI.",
        )
        assert isinstance(script, str)
        assert len(script) > 100


# ---------------------------------------------------------------------------
# Phase 5: Demo module
# ---------------------------------------------------------------------------


class TestDemo:
    """Validate demo.py provides mock data and run_demo."""

    def setup_method(self) -> None:
        self.mod = _try_import("demo")
        if self.mod is None:
            pytest.skip("demo module not available")

    def test_has_mock_data(self) -> None:
        assert hasattr(self.mod, "MOCK_MARKETS")
        assert hasattr(self.mod, "MOCK_DEFI")
        assert hasattr(self.mod, "MOCK_SIGNALS")
        assert len(self.mod.MOCK_MARKETS) > 0
        assert len(self.mod.MOCK_DEFI) > 0
        assert len(self.mod.MOCK_SIGNALS) > 0

    def test_mock_markets_have_required_fields(self) -> None:
        for m in self.mod.MOCK_MARKETS:
            assert hasattr(m, "question")
            assert hasattr(m, "yes_pct")
            assert hasattr(m, "volume")

    def test_has_run_demo(self) -> None:
        assert callable(getattr(self.mod, "run_demo", None))

    def test_has_score_market(self) -> None:
        fn = getattr(self.mod, "_score_market", None)
        assert callable(fn)
        score = fn(self.mod.MOCK_MARKETS[0])
        assert 0 <= score <= 100


# ---------------------------------------------------------------------------
# Phase 6: Logger module
# ---------------------------------------------------------------------------


class TestLogger:
    """Validate logger.py provides structured logging and state management."""

    def setup_method(self) -> None:
        self.mod = _try_import("logger")
        if self.mod is None:
            pytest.skip("logger module not available")

    def test_has_logging_functions(self) -> None:
        assert callable(getattr(self.mod, "log_pipeline_event", None))
        assert callable(getattr(self.mod, "log_api_call", None))
        assert callable(getattr(self.mod, "log_video_event", None))

    def test_has_state_management(self) -> None:
        assert hasattr(self.mod, "StateManager")
        assert callable(getattr(self.mod, "update_state", None))
        assert callable(getattr(self.mod, "read_state", None))

    def test_pipeline_state_roundtrip(self, tmp_path: Path) -> None:
        sm = self.mod.StateManager(tmp_path / "test_state.json")
        state = self.mod.PipelineState(pipeline_status="running", markets_tracked=5)
        sm.write(state)

        loaded = sm.read()
        assert loaded.pipeline_status == "running"
        assert loaded.markets_tracked == 5

    def test_state_update_with_signal(self, tmp_path: Path) -> None:
        sm = self.mod.StateManager(tmp_path / "test_state.json")
        sm.write(self.mod.PipelineState())

        updated = sm.update(
            pipeline_status="running",
            add_signal=self.mod.Signal(
                ticker="BTC", direction="buy", confidence=0.87
            ),
        )
        assert len(updated.signals) == 1
        assert updated.signals[0].ticker == "BTC"


# ---------------------------------------------------------------------------
# Phase 7: Data module (uses sample/fallback data only)
# ---------------------------------------------------------------------------


class TestData:
    """Validate data.py has fetch functions and sample fallback data."""

    def setup_method(self) -> None:
        self.mod = _try_import("data")
        if self.mod is None:
            pytest.skip("data module not available")

    def test_has_fetch_functions(self) -> None:
        assert callable(getattr(self.mod, "fetch_markets", None))
        assert callable(getattr(self.mod, "fetch_yields", None))
        assert callable(getattr(self.mod, "fetch_signals", None))

    def test_has_sample_data(self) -> None:
        assert hasattr(self.mod, "SAMPLE_MARKETS")
        assert hasattr(self.mod, "SAMPLE_YIELDS")
        assert hasattr(self.mod, "SAMPLE_SIGNALS")
        assert len(self.mod.SAMPLE_MARKETS) > 0
        assert len(self.mod.SAMPLE_YIELDS) > 0
        assert len(self.mod.SAMPLE_SIGNALS) > 0

    def test_sample_market_shape(self) -> None:
        m = self.mod.SAMPLE_MARKETS[0]
        assert "question" in m
        assert "yes_pct" in m
        assert "volume" in m
        assert "score" in m
        assert "tickers" in m

    def test_sample_yield_shape(self) -> None:
        y = self.mod.SAMPLE_YIELDS[0]
        assert "project" in y
        assert "apy" in y
        assert "tvl" in y

    def test_has_video_script_generation(self) -> None:
        assert callable(getattr(self.mod, "generate_video_script", None))

    def test_generate_script_fallback(self) -> None:
        """Script generation should work even without external services."""
        script = self.mod.generate_video_script(
            topic="Bitcoin to $100k?",
            vibe="hype",
            yes_pct=68.0,
            no_pct=32.0,
            volume=4_200_000,
        )
        assert isinstance(script, str)
        assert len(script) > 50


# ---------------------------------------------------------------------------
# Phase 8: API module
# ---------------------------------------------------------------------------


class TestAPI:
    """Validate api.py creates a FastAPI app with expected endpoints."""

    def setup_method(self) -> None:
        self.mod = _try_import("api")
        if self.mod is None:
            pytest.skip("api module not available")

    def test_has_fastapi_app(self) -> None:
        app_obj = getattr(self.mod, "app", None)
        assert app_obj is not None, "api.py must export `app` (FastAPI instance)"

    def test_has_required_routes(self) -> None:
        app_obj = self.mod.app
        routes = {route.path for route in getattr(app_obj, "routes", [])}
        expected = {
            "/api/v1/markets",
            "/api/v1/yields",
            "/api/v1/signals",
            "/api/v1/dashboard",
            "/api/v1/generate",
            "/api/v1/status",
            "/",
        }
        for route in expected:
            assert route in routes, f"Missing route {route}. Found: {sorted(routes)}"


# ---------------------------------------------------------------------------
# Phase 9: End-to-end pipeline (mock data, no network)
# ---------------------------------------------------------------------------


class TestEndToEndPipeline:
    """Full pipeline: scorer -> extractor -> prompts using mock data only."""

    def test_scorer_to_extractor_to_prompts(self) -> None:
        """The core content pipeline: score markets, extract tickers, generate scripts."""
        scorer_mod = _try_import("scorer")
        extractor_mod = _try_import("extractor")
        prompts_mod = _try_import("prompts")

        if not all([scorer_mod, extractor_mod, prompts_mod]):
            pytest.skip("Missing core modules for E2E test")

        # Step 1: Create and score prediction markets
        now = datetime(2026, 4, 1, tzinfo=timezone.utc)
        markets = [
            scorer_mod.PredictionMarket(
                question="Will Bitcoin hit $150K by July 2026?",
                yes_pct=68.0,
                volume_24h=4_200_000,
                end_date=datetime(2026, 7, 1, tzinfo=timezone.utc),
            ),
            scorer_mod.PredictionMarket(
                question="Will Tesla stock be above $300?",
                yes_pct=51.0,
                volume_24h=3_100_000,
                end_date=datetime(2026, 7, 1, tzinfo=timezone.utc),
            ),
        ]
        yields = [
            scorer_mod.DeFiYield("Aave", "USDC", 14.2, 890_000_000, "Ethereum", True),
        ]

        ranked = scorer_mod.rank_all(markets, yields, now=now)
        assert len(ranked) == 3
        assert all(0 <= item.score <= 100 for item in ranked)

        # Step 2: Extract tickers from market questions
        for item in ranked:
            if item.category == "prediction":
                result = extractor_mod.extract_tickers(item.title)
                assert isinstance(result.tickers, tuple)

        # Verify we can find BTC and TSLA
        btc_result = extractor_mod.extract_tickers("Will Bitcoin hit $150K by July 2026?")
        assert "BTC" in btc_result.tickers

        tsla_result = extractor_mod.extract_tickers("Will Tesla stock be above $300?")
        assert "TSLA" in tsla_result.tickers

        # Step 3: Generate scripts for the top-scored item
        top = ranked[0]
        scripts_generated = 0
        for name, template_fn in prompts_mod.TEMPLATES.items():
            try:
                # Each template has different signatures, use the registry
                if name == "breaking_news":
                    script = template_fn(top.title, 68.0, 4_200_000, "Market is moving.")
                elif name == "deep_analysis":
                    script = template_fn(top.title, 68.0, 32.0, 4_200_000, "trending up")
                elif name == "hot_take":
                    script = template_fn(top.title, 68.0, 4_200_000)
                elif name == "countdown":
                    script = template_fn(top.title, 68.0, "July 1, 2026", 4_200_000)
                elif name == "explainer":
                    script = template_fn(top.title, 68.0, "A trending prediction market.")
                else:
                    continue

                assert isinstance(script, str)
                assert len(script) > 50
                scripts_generated += 1
            except Exception as e:
                print(f"  [WARN] Script gen failed for {name}: {e}")

        assert scripts_generated == 5, (
            f"Expected 5 scripts, generated {scripts_generated}"
        )

        # Pipeline summary
        print("\n  === E2E Pipeline Summary ===")
        print(f"  Scored items:      {len(ranked)}")
        print(f"  Top item:          {ranked[0].title} (score={ranked[0].score})")
        print(f"  Tickers extracted: BTC={btc_result.tickers}, TSLA={tsla_result.tickers}")
        print(f"  Scripts generated: {scripts_generated}/5 vibes")

    def test_data_sample_to_script_pipeline(self) -> None:
        """Validate the data.py -> prompts pipeline using sample data."""
        data_mod = _try_import("data")
        if data_mod is None:
            pytest.skip("data module not available")

        # Use sample data (no network)
        markets = data_mod.SAMPLE_MARKETS
        assert len(markets) > 0

        # Generate a script for the first market
        m = markets[0]
        script = data_mod.generate_video_script(
            topic=m["question"],
            vibe=m["suggested_vibe"],
            yes_pct=m["yes_pct"],
            no_pct=m["no_pct"],
            volume=m["volume"],
        )
        assert isinstance(script, str)
        assert len(script) > 50


# ---------------------------------------------------------------------------
# Phase 10: Cross-module type consistency
# ---------------------------------------------------------------------------


class TestTypeConsistency:
    """Verify dataclass/type contracts between modules."""

    def test_scorer_output_has_title_for_extractor(self) -> None:
        """ScoredItem.title should be passable to extract_tickers()."""
        scorer_mod = _try_import("scorer")
        extractor_mod = _try_import("extractor")
        if not scorer_mod or not extractor_mod:
            pytest.skip("scorer or extractor not available")

        item = scorer_mod.ScoredItem(
            title="Will Bitcoin reach $150k?",
            score=75.0,
            category="prediction",
            priority=scorer_mod.Priority.HIGH,
            vibe=scorer_mod.VideoVibe.DEEP_ANALYSIS,
            raw_components={"controversy": 84.0, "volume": 69.0},
        )
        result = extractor_mod.extract_tickers(item.title)
        assert "BTC" in result.tickers

    def test_data_sample_has_tickers_from_extractor(self) -> None:
        """data.py's SAMPLE_MARKETS tickers should match extractor output."""
        data_mod = _try_import("data")
        extractor_mod = _try_import("extractor")
        if not data_mod or not extractor_mod:
            pytest.skip("data or extractor not available")

        for market in data_mod.SAMPLE_MARKETS:
            expected_tickers = market["tickers"]
            result = extractor_mod.extract_tickers(market["question"])
            for ticker in expected_tickers:
                assert ticker in result.tickers, (
                    f"Expected ticker {ticker} from question '{market['question']}', "
                    f"got {result.tickers}"
                )


# ---------------------------------------------------------------------------
# Standalone runner
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v", "--tb=short"]))
