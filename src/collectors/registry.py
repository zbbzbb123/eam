"""Collector registry for unified access to all data collectors."""
import asyncio
import inspect
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Type

logger = logging.getLogger(__name__)


class CollectorType(Enum):
    """Collector type enumeration."""
    ASYNC = "async"
    SYNC = "sync"


@dataclass
class CollectorInfo:
    """Information about a registered collector."""

    name: str
    collector_class: Type
    collector_type: CollectorType
    source: str
    description: str = ""

    def is_configured(self) -> bool:
        """Check if the collector is properly configured.

        This instantiates the collector and checks for common configuration
        attributes like API keys or tokens.
        """
        try:
            instance = self.collector_class()

            # Check for common configuration patterns
            # FRED collector
            if hasattr(instance, "_api_key"):
                return bool(instance._api_key)

            # TuShare collector
            if hasattr(instance, "_token"):
                return bool(instance._token)

            if hasattr(instance, "_pro"):
                return instance._pro is not None

            # Most collectors are configured by default (no API key needed)
            # Crawlers and some collectors work without configuration
            return True

        except Exception as e:
            logger.debug(f"Error checking configuration for {self.name}: {e}")
            return False


class CollectorRegistry:
    """Registry for all data collectors.

    This class provides a unified interface to register, discover, and run
    any data collector in the system. It handles both sync and async collectors
    transparently.

    Example:
        >>> registry = CollectorRegistry()
        >>> registry.list_all()
        ['fred_collector', 'northbound_collector', ...]
        >>> result = registry.run('fred_collector')
    """

    def __init__(self, auto_register: bool = True):
        """Initialize the collector registry.

        Args:
            auto_register: If True, automatically register all built-in collectors.
        """
        self._collectors: Dict[str, CollectorInfo] = {}

        if auto_register:
            self._auto_register_collectors()

    def _auto_register_collectors(self) -> None:
        """Auto-register all built-in collectors."""
        # Import collectors
        try:
            from src.collectors.structured.fred_collector import FREDCollector
            self.register(
                FREDCollector,
                name="fred",
                description="FRED (Federal Reserve Economic Data) collector for US macro data",
            )
        except ImportError as e:
            logger.warning(f"Could not import FREDCollector: {e}")

        try:
            from src.collectors.structured.northbound_collector import NorthboundCollector
            self.register(
                NorthboundCollector,
                name="northbound",
                description="Northbound capital flow collector via TuShare moneyflow_hsgt API",
            )
        except ImportError as e:
            logger.warning(f"Could not import NorthboundCollector: {e}")

        try:
            from src.collectors.structured.sec13f_collector import SEC13FCollector
            self.register(
                SEC13FCollector,
                name="sec13f",
                description="SEC EDGAR 13F collector for institutional holdings data",
            )
        except ImportError as e:
            logger.warning(f"Could not import SEC13FCollector: {e}")

        try:
            from src.collectors.structured.tushare_collector import TuShareCollector
            self.register(
                TuShareCollector,
                name="tushare",
                description="TuShare Pro collector for A-share financial metrics and valuation",
            )
        except ImportError as e:
            logger.warning(f"Could not import TuShareCollector: {e}")

        # Crawlers
        try:
            from src.collectors.crawlers.jisilu_crawler import JisiluCrawler
            self.register(
                JisiluCrawler,
                name="jisilu",
                description="Jisilu ETF premium/discount crawler for Chinese ETF data",
            )
        except ImportError as e:
            logger.warning(f"Could not import JisiluCrawler: {e}")

        try:
            from src.collectors.crawlers.commodity_crawler import CommodityCrawler
            self.register(
                CommodityCrawler,
                name="commodity",
                description="Commodity price crawler for lithium carbonate and polysilicon",
            )
        except ImportError as e:
            logger.warning(f"Could not import CommodityCrawler: {e}")

        # New collectors
        try:
            from src.collectors.structured.cn_macro_collector import CnMacroCollector
            self.register(
                CnMacroCollector,
                name="cn_macro",
                description="China macro data (PMI/CPI/M2) via eastmoney datacenter",
            )
        except ImportError as e:
            logger.warning(f"Could not import CnMacroCollector: {e}")

        try:
            from src.collectors.structured.sector_collector import SectorCollector
            self.register(
                SectorCollector,
                name="sector",
                description="Industry and concept sector data via Sina Finance",
            )
        except ImportError as e:
            logger.warning(f"Could not import SectorCollector: {e}")

        try:
            from src.collectors.structured.market_indicators_collector import MarketIndicatorsCollector
            self.register(
                MarketIndicatorsCollector,
                name="market_indicators",
                description="VIX, gold, silver, copper market indicators via YFinance",
            )
        except ImportError as e:
            logger.warning(f"Could not import MarketIndicatorsCollector: {e}")

        try:
            from src.collectors.structured.fundamentals_collector import FundamentalsCollector
            self.register(
                FundamentalsCollector,
                name="fundamentals",
                description="Company fundamentals (PE/PB/revenue) via YFinance and TuShare",
            )
        except ImportError as e:
            logger.warning(f"Could not import FundamentalsCollector: {e}")

        try:
            from src.collectors.structured.sector_flow_collector import SectorFlowCollector
            self.register(
                SectorFlowCollector,
                name="sector_flow",
                description="Sector fund flow data (主力资金) via EastMoney",
            )
        except ImportError as e:
            logger.warning(f"Could not import SectorFlowCollector: {e}")

        try:
            from src.collectors.structured.market_breadth_collector import MarketBreadthCollector
            self.register(
                MarketBreadthCollector,
                name="market_breadth",
                description="A-share market breadth (advance/decline) via EastMoney",
            )
        except ImportError as e:
            logger.warning(f"Could not import MarketBreadthCollector: {e}")

    def _detect_collector_type(self, collector_class: Type) -> CollectorType:
        """Detect if a collector is async or sync based on its methods.

        Args:
            collector_class: The collector class to check.

        Returns:
            CollectorType indicating async or sync.
        """
        # Check common method names for async patterns
        async_method_names = [
            "fetch_series",
            "fetch_all_series",
            "fetch_latest_value",
            "fetch_filings",
            "fetch_holdings",
            "fetch_latest_holdings",
            "fetch_all_tracked_holdings",
            "fetch_all",
            "fetch_pmi",
        ]

        for method_name in async_method_names:
            method = getattr(collector_class, method_name, None)
            if method and inspect.iscoroutinefunction(method):
                return CollectorType.ASYNC

        return CollectorType.SYNC

    def _get_source(self, collector_class: Type) -> str:
        """Get the source name from a collector class.

        Args:
            collector_class: The collector class.

        Returns:
            Source name string.
        """
        try:
            instance = collector_class()
            if hasattr(instance, "source"):
                return instance.source
        except Exception:
            pass
        return "unknown"

    def register(
        self,
        collector_class: Type,
        name: Optional[str] = None,
        description: str = "",
    ) -> None:
        """Register a collector class.

        Args:
            collector_class: The collector class to register.
            name: Optional name for the collector. If not provided,
                  uses the class's name property or class name.
            description: Optional description of the collector.
        """
        # Determine the name
        if name is None:
            try:
                instance = collector_class()
                name = instance.name
            except Exception:
                name = collector_class.__name__.lower()

        # Detect collector type
        collector_type = self._detect_collector_type(collector_class)

        # Get source
        source = self._get_source(collector_class)

        # Register
        self._collectors[name] = CollectorInfo(
            name=name,
            collector_class=collector_class,
            collector_type=collector_type,
            source=source,
            description=description,
        )

        logger.debug(f"Registered collector: {name} ({collector_type.value})")

    def get(self, name: str) -> Optional[CollectorInfo]:
        """Get collector info by name.

        Args:
            name: Name of the collector.

        Returns:
            CollectorInfo or None if not found.
        """
        return self._collectors.get(name)

    def list_all(self) -> List[str]:
        """List all registered collector names.

        Returns:
            List of collector names.
        """
        return list(self._collectors.keys())

    def get_all_info(self) -> Dict[str, CollectorInfo]:
        """Get information about all registered collectors.

        Returns:
            Dictionary mapping names to CollectorInfo objects.
        """
        return self._collectors.copy()

    def run(self, name: str, method: Optional[str] = None, **kwargs) -> Any:
        """Run a collector and return the result.

        This method handles both sync and async collectors transparently.
        For async collectors, it runs them in an event loop.

        Args:
            name: Name of the collector to run.
            method: Optional method name to call. If not provided,
                    calls a default method based on collector type.
            **kwargs: Arguments to pass to the method.

        Returns:
            Result from the collector method.

        Raises:
            ValueError: If collector not found.
            RuntimeError: If collector execution fails.
        """
        collector_info = self.get(name)
        if not collector_info:
            raise ValueError(f"Collector '{name}' not found. Available: {self.list_all()}")

        try:
            instance = collector_info.collector_class()

            # Determine which method to call
            if method:
                target_method = getattr(instance, method, None)
                if not target_method:
                    raise ValueError(f"Method '{method}' not found on collector '{name}'")
            else:
                # Use default methods based on collector
                target_method = self._get_default_method(instance)

            # Execute the method
            if inspect.iscoroutinefunction(target_method):
                # Run async method
                return self._run_async(target_method, **kwargs)
            else:
                # Run sync method
                return target_method(**kwargs)

        except Exception as e:
            logger.error(f"Error running collector '{name}': {e}")
            raise RuntimeError(f"Failed to run collector '{name}': {e}") from e

    def _get_default_method(self, instance: Any) -> Callable:
        """Get the default method to call for a collector.

        Args:
            instance: Collector instance.

        Returns:
            Method to call.
        """
        # Priority list of methods to try
        method_names = [
            # Async collectors
            "fetch_all_series",
            "fetch_all_tracked_holdings",
            # Sync collectors
            "fetch_daily_net_flow",
            "fetch_etf_premium_data",
            "fetch_all_tracked_commodities",
            "fetch_all_holdings_fundamentals",
            "fetch_all",
        ]

        for method_name in method_names:
            method = getattr(instance, method_name, None)
            if method:
                # For methods that need default arguments, wrap them
                if method_name == "fetch_all_series":
                    from datetime import date, timedelta
                    import asyncio
                    end = date.today()
                    start = end - timedelta(days=30)
                    return lambda m=method, s=start, e=end: asyncio.run(m(s, e))
                if method_name == "fetch_all_holdings_fundamentals":
                    from src.db.database import SessionLocal
                    from src.db.models import Holding, HoldingStatus, Watchlist
                    db = SessionLocal()
                    try:
                        holdings = db.query(Holding).filter(Holding.status == HoldingStatus.ACTIVE).all()
                        pairs = [(h.symbol, h.market.value) for h in holdings if h.symbol != "CASH"]
                        watchlist_items = db.query(Watchlist).all()
                        pairs += [(w.symbol, w.market.value) for w in watchlist_items]
                        pairs = list(set(pairs))
                    finally:
                        db.close()
                    if not pairs:
                        return lambda: {}
                    return lambda m=method, p=pairs: m(p)
                return method

        raise ValueError(f"No default method found for collector {type(instance).__name__}")

    def _run_async(self, coro_func: Callable, **kwargs) -> Any:
        """Run an async method.

        Args:
            coro_func: Async function to run.
            **kwargs: Arguments to pass.

        Returns:
            Result from the async function.
        """
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            # We're already in an async context, create a new task
            # This shouldn't normally happen in CLI context
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, coro_func(**kwargs))
                return future.result()
        else:
            # Run in a new event loop
            return asyncio.run(coro_func(**kwargs))

    def run_all(
        self,
        only_configured: bool = True,
        stop_on_error: bool = False,
    ) -> Dict[str, Any]:
        """Run all registered collectors.

        Args:
            only_configured: If True, only run collectors that are configured.
            stop_on_error: If True, stop on first error. Otherwise, continue
                          and return errors in results.

        Returns:
            Dictionary mapping collector names to their results or error messages.
        """
        results = {}

        for name, info in self._collectors.items():
            if only_configured and not info.is_configured():
                results[name] = {"status": "skipped", "reason": "not configured"}
                continue

            try:
                result = self.run(name)
                results[name] = {"status": "success", "data": result}
            except Exception as e:
                error_msg = str(e)
                results[name] = {"status": "error", "error": error_msg}
                logger.error(f"Error running collector '{name}': {error_msg}")

                if stop_on_error:
                    break

        return results

    def get_status(self) -> Dict[str, Dict[str, Any]]:
        """Get status of all registered collectors.

        Returns:
            Dictionary with status information for each collector.
        """
        status = {}

        for name, info in self._collectors.items():
            status[name] = {
                "type": info.collector_type.value,
                "source": info.source,
                "description": info.description,
                "configured": info.is_configured(),
            }

        return status


# Global registry instance
_registry: Optional[CollectorRegistry] = None


def get_registry() -> CollectorRegistry:
    """Get the global collector registry instance.

    Returns:
        CollectorRegistry instance.
    """
    global _registry
    if _registry is None:
        _registry = CollectorRegistry()
    return _registry
