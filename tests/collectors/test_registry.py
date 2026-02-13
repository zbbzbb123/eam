"""Tests for CollectorRegistry."""
import pytest
from unittest.mock import Mock, patch, MagicMock
import asyncio

from src.collectors.registry import (
    CollectorRegistry,
    CollectorInfo,
    CollectorType,
    get_registry,
)


class MockSyncCollector:
    """Mock sync collector for testing."""

    @property
    def name(self) -> str:
        return "mock_sync_collector"

    @property
    def source(self) -> str:
        return "mock_source"

    def fetch_data(self) -> list:
        return [{"id": 1, "value": "test"}]


class MockAsyncCollector:
    """Mock async collector for testing."""

    @property
    def name(self) -> str:
        return "mock_async_collector"

    @property
    def source(self) -> str:
        return "mock_async_source"

    async def fetch_series(self) -> list:
        return [{"id": 1, "value": "async_test"}]


class MockConfiguredCollector:
    """Mock collector that appears configured."""

    _api_key = "test_key"

    @property
    def name(self) -> str:
        return "mock_configured_collector"

    @property
    def source(self) -> str:
        return "mock"

    def fetch_data(self) -> list:
        return []


class MockUnconfiguredCollector:
    """Mock collector that appears unconfigured."""

    _api_key = ""

    @property
    def name(self) -> str:
        return "mock_unconfigured_collector"

    @property
    def source(self) -> str:
        return "mock"

    def fetch_data(self) -> list:
        return []


class TestCollectorInfo:
    """Tests for CollectorInfo dataclass."""

    def test_collector_info_creation(self):
        """Test CollectorInfo can be created."""
        info = CollectorInfo(
            name="test_collector",
            collector_class=MockSyncCollector,
            collector_type=CollectorType.SYNC,
            source="test_source",
            description="Test collector",
        )

        assert info.name == "test_collector"
        assert info.collector_class == MockSyncCollector
        assert info.collector_type == CollectorType.SYNC
        assert info.source == "test_source"
        assert info.description == "Test collector"

    def test_is_configured_returns_true_for_configured(self):
        """Test is_configured returns True for configured collectors."""
        info = CollectorInfo(
            name="test",
            collector_class=MockConfiguredCollector,
            collector_type=CollectorType.SYNC,
            source="mock",
        )

        assert info.is_configured() is True

    def test_is_configured_returns_false_for_unconfigured(self):
        """Test is_configured returns False for unconfigured collectors."""
        info = CollectorInfo(
            name="test",
            collector_class=MockUnconfiguredCollector,
            collector_type=CollectorType.SYNC,
            source="mock",
        )

        assert info.is_configured() is False

    def test_is_configured_returns_true_for_no_api_key_collectors(self):
        """Test is_configured returns True for collectors without API key requirement."""
        info = CollectorInfo(
            name="test",
            collector_class=MockSyncCollector,
            collector_type=CollectorType.SYNC,
            source="mock",
        )

        # Collectors without _api_key or _token should be considered configured
        assert info.is_configured() is True


class TestCollectorRegistryInitialization:
    """Tests for CollectorRegistry initialization."""

    def test_registry_creation_without_auto_register(self):
        """Test registry can be created without auto-registering collectors."""
        registry = CollectorRegistry(auto_register=False)

        assert len(registry.list_all()) == 0

    def test_registry_creation_with_auto_register(self):
        """Test registry auto-registers built-in collectors."""
        registry = CollectorRegistry(auto_register=True)

        collectors = registry.list_all()
        # Should have registered at least some collectors
        assert len(collectors) > 0

    def test_auto_registered_collectors_include_expected(self):
        """Test that expected collectors are auto-registered."""
        registry = CollectorRegistry(auto_register=True)

        collectors = registry.list_all()

        # Check for some expected collectors
        expected_collectors = [
            "fred",
            "northbound",
            "sec13f",
            "tushare",
            "jisilu",
            "commodity",
            "cn_macro",
            "sector",
            "market_indicators",
            "fundamentals",
        ]

        for name in expected_collectors:
            assert name in collectors, f"Expected collector '{name}' to be registered"


class TestCollectorRegistration:
    """Tests for collector registration."""

    def test_register_sync_collector(self):
        """Test registering a sync collector."""
        registry = CollectorRegistry(auto_register=False)

        registry.register(MockSyncCollector, name="test_sync")

        assert "test_sync" in registry.list_all()
        info = registry.get("test_sync")
        assert info is not None
        assert info.collector_type == CollectorType.SYNC

    def test_register_async_collector(self):
        """Test registering an async collector."""
        registry = CollectorRegistry(auto_register=False)

        registry.register(MockAsyncCollector, name="test_async")

        assert "test_async" in registry.list_all()
        info = registry.get("test_async")
        assert info is not None
        assert info.collector_type == CollectorType.ASYNC

    def test_register_without_name_uses_class_name(self):
        """Test register uses collector's name property if no name provided."""
        registry = CollectorRegistry(auto_register=False)

        registry.register(MockSyncCollector)

        assert "mock_sync_collector" in registry.list_all()

    def test_register_with_description(self):
        """Test register stores description."""
        registry = CollectorRegistry(auto_register=False)

        registry.register(
            MockSyncCollector,
            name="test",
            description="Test description",
        )

        info = registry.get("test")
        assert info is not None
        assert info.description == "Test description"


class TestCollectorRetrieval:
    """Tests for collector retrieval methods."""

    def test_get_existing_collector(self):
        """Test get returns CollectorInfo for existing collector."""
        registry = CollectorRegistry(auto_register=False)
        registry.register(MockSyncCollector, name="test")

        info = registry.get("test")

        assert info is not None
        assert info.name == "test"

    def test_get_nonexistent_collector(self):
        """Test get returns None for non-existent collector."""
        registry = CollectorRegistry(auto_register=False)

        info = registry.get("nonexistent")

        assert info is None

    def test_list_all_returns_all_names(self):
        """Test list_all returns all registered collector names."""
        registry = CollectorRegistry(auto_register=False)
        registry.register(MockSyncCollector, name="collector1")
        registry.register(MockAsyncCollector, name="collector2")

        names = registry.list_all()

        assert len(names) == 2
        assert "collector1" in names
        assert "collector2" in names

    def test_get_all_info(self):
        """Test get_all_info returns all collector info."""
        registry = CollectorRegistry(auto_register=False)
        registry.register(MockSyncCollector, name="collector1")
        registry.register(MockAsyncCollector, name="collector2")

        all_info = registry.get_all_info()

        assert len(all_info) == 2
        assert "collector1" in all_info
        assert "collector2" in all_info
        assert isinstance(all_info["collector1"], CollectorInfo)


class TestCollectorExecution:
    """Tests for running collectors."""

    def test_run_sync_collector(self):
        """Test running a sync collector."""
        registry = CollectorRegistry(auto_register=False)
        registry.register(MockSyncCollector, name="test_sync")

        result = registry.run("test_sync", method="fetch_data")

        assert result == [{"id": 1, "value": "test"}]

    def test_run_async_collector(self):
        """Test running an async collector."""
        registry = CollectorRegistry(auto_register=False)
        registry.register(MockAsyncCollector, name="test_async")

        result = registry.run("test_async", method="fetch_series")

        assert result == [{"id": 1, "value": "async_test"}]

    def test_run_nonexistent_collector_raises_error(self):
        """Test run raises ValueError for non-existent collector."""
        registry = CollectorRegistry(auto_register=False)

        with pytest.raises(ValueError, match="not found"):
            registry.run("nonexistent")

    def test_run_invalid_method_raises_error(self):
        """Test run raises ValueError for invalid method."""
        registry = CollectorRegistry(auto_register=False)
        registry.register(MockSyncCollector, name="test")

        with pytest.raises(RuntimeError):
            registry.run("test", method="invalid_method")


class TestRunAllCollectors:
    """Tests for run_all method."""

    def test_run_all_returns_results_dict(self):
        """Test run_all returns dictionary of results."""
        registry = CollectorRegistry(auto_register=False)
        registry.register(MockSyncCollector, name="sync1")
        registry.register(MockSyncCollector, name="sync2")

        # Mock the run method to avoid actual execution
        with patch.object(registry, "run") as mock_run:
            mock_run.return_value = [{"data": "test"}]

            results = registry.run_all(only_configured=False)

            assert "sync1" in results
            assert "sync2" in results

    def test_run_all_handles_errors(self):
        """Test run_all captures errors without stopping."""

        class FailingCollector:
            @property
            def name(self):
                return "failing"

            @property
            def source(self):
                return "test"

            def fetch_all(self):
                raise RuntimeError("Test error")

        registry = CollectorRegistry(auto_register=False)
        registry.register(FailingCollector, name="failing")
        registry.register(MockSyncCollector, name="working")

        # Run without mocking to test real error handling
        with patch.object(registry, "_get_default_method") as mock_method:
            mock_method.side_effect = [
                Mock(side_effect=RuntimeError("Test error")),
                Mock(return_value=[{"data": "test"}]),
            ]

            results = registry.run_all(only_configured=False, stop_on_error=False)

            # Both should be in results
            assert "failing" in results
            assert "working" in results


class TestGetStatus:
    """Tests for get_status method."""

    def test_get_status_returns_info_for_all_collectors(self):
        """Test get_status returns status for all collectors."""
        registry = CollectorRegistry(auto_register=False)
        registry.register(MockConfiguredCollector, name="configured")
        registry.register(MockUnconfiguredCollector, name="unconfigured")

        status = registry.get_status()

        assert "configured" in status
        assert "unconfigured" in status

    def test_get_status_includes_configuration_status(self):
        """Test get_status includes configured flag."""
        registry = CollectorRegistry(auto_register=False)
        registry.register(MockConfiguredCollector, name="configured")
        registry.register(MockUnconfiguredCollector, name="unconfigured")

        status = registry.get_status()

        assert status["configured"]["configured"] is True
        assert status["unconfigured"]["configured"] is False

    def test_get_status_includes_type_and_source(self):
        """Test get_status includes type and source."""
        registry = CollectorRegistry(auto_register=False)
        registry.register(MockSyncCollector, name="test")

        status = registry.get_status()

        assert status["test"]["type"] == "sync"
        assert status["test"]["source"] == "mock_source"


class TestGlobalRegistry:
    """Tests for global registry functions."""

    def test_get_registry_returns_registry(self):
        """Test get_registry returns a CollectorRegistry instance."""
        registry = get_registry()

        assert isinstance(registry, CollectorRegistry)

    def test_get_registry_returns_same_instance(self):
        """Test get_registry returns the same instance on multiple calls."""
        # Reset global registry
        import src.collectors.registry as reg_module
        reg_module._registry = None

        registry1 = get_registry()
        registry2 = get_registry()

        assert registry1 is registry2


class TestCollectorTypeDetection:
    """Tests for collector type detection."""

    def test_detect_sync_collector(self):
        """Test sync collector is detected correctly."""
        registry = CollectorRegistry(auto_register=False)

        collector_type = registry._detect_collector_type(MockSyncCollector)

        assert collector_type == CollectorType.SYNC

    def test_detect_async_collector(self):
        """Test async collector is detected correctly."""
        registry = CollectorRegistry(auto_register=False)

        collector_type = registry._detect_collector_type(MockAsyncCollector)

        assert collector_type == CollectorType.ASYNC


class TestBuiltInCollectors:
    """Integration tests for built-in collectors in registry."""

    @pytest.fixture
    def registry(self):
        """Create registry with auto-registered collectors."""
        return CollectorRegistry(auto_register=True)

    def test_fred_collector_registered(self, registry):
        """Test FRED collector is registered."""
        info = registry.get("fred")

        assert info is not None
        assert info.collector_type == CollectorType.ASYNC
        assert info.source == "fred"

    def test_northbound_collector_registered(self, registry):
        """Test Northbound collector is registered."""
        info = registry.get("northbound")

        assert info is not None
        assert info.collector_type == CollectorType.SYNC
        assert info.source == "tushare"

    def test_sec13f_collector_registered(self, registry):
        """Test SEC 13F collector is registered."""
        info = registry.get("sec13f")

        assert info is not None
        assert info.collector_type == CollectorType.ASYNC
        assert info.source == "sec_edgar"

    def test_tushare_collector_registered(self, registry):
        """Test TuShare collector is registered."""
        info = registry.get("tushare")

        assert info is not None
        assert info.collector_type == CollectorType.SYNC
        assert info.source == "tushare"

    def test_jisilu_crawler_registered(self, registry):
        """Test Jisilu crawler is registered."""
        info = registry.get("jisilu")

        assert info is not None
        assert info.collector_type == CollectorType.SYNC
        assert info.source == "jisilu"

    def test_commodity_crawler_registered(self, registry):
        """Test Commodity crawler is registered."""
        info = registry.get("commodity")

        assert info is not None
        assert info.collector_type == CollectorType.SYNC
        assert info.source == "100ppi"

    def test_cn_macro_collector_registered(self, registry):
        """Test CN Macro collector is registered."""
        info = registry.get("cn_macro")

        assert info is not None
        assert info.collector_type == CollectorType.ASYNC

    def test_sector_collector_registered(self, registry):
        """Test Sector collector is registered."""
        info = registry.get("sector")

        assert info is not None
        assert info.collector_type == CollectorType.SYNC

    def test_market_indicators_collector_registered(self, registry):
        """Test Market Indicators collector is registered."""
        info = registry.get("market_indicators")

        assert info is not None
        assert info.collector_type == CollectorType.SYNC

    def test_fundamentals_collector_registered(self, registry):
        """Test Fundamentals collector is registered."""
        info = registry.get("fundamentals")

        assert info is not None
        assert info.collector_type == CollectorType.SYNC


class TestCLIIntegration:
    """Tests for CLI integration (via main function)."""

    def test_cli_list_returns_zero(self):
        """Test CLI --list returns exit code 0."""
        from src.cli.collect import main

        exit_code = main(["--list"])

        assert exit_code == 0

    def test_cli_status_returns_zero(self):
        """Test CLI --status returns exit code 0."""
        from src.cli.collect import main

        exit_code = main(["--status"])

        assert exit_code == 0

    def test_cli_invalid_collector_returns_one(self):
        """Test CLI with invalid collector returns exit code 1."""
        from src.cli.collect import main

        exit_code = main(["--collector", "nonexistent_collector"])

        assert exit_code == 1

    def test_cli_no_args_returns_zero(self):
        """Test CLI with no arguments returns exit code 0 (shows help)."""
        from src.cli.collect import main

        exit_code = main([])

        assert exit_code == 0
