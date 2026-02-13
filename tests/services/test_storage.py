"""Tests for StorageService."""
import pytest
from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock, patch, call
from dataclasses import dataclass
from typing import Optional


# --- Mock dataclasses matching collector outputs ---

@dataclass
class MockMacroDataPoint:
    series_id: str
    date: date
    value: Decimal

    def to_dict(self):
        return {"series_id": self.series_id, "date": self.date, "value": self.value}


@dataclass
class MockYieldSpread:
    date: date
    dgs2: Decimal
    dgs10: Decimal
    spread: Decimal


@dataclass
class MockNorthboundFlowData:
    trade_date: date
    net_flow: Decimal
    quota_remaining: Decimal


@dataclass
class MockCnMacroData:
    indicator: str
    date: date
    value: Decimal
    yoy_change: Optional[Decimal]


@dataclass
class MockSectorData:
    code: str
    name: str
    stock_count: int
    avg_price: Decimal
    change_pct: Decimal
    volume: Decimal
    amount: Decimal
    leading_stock: str


@dataclass
class MockMarketIndicator:
    symbol: str
    name: str
    value: Optional[float]
    change_pct: Optional[float]
    date: Optional[date]


@dataclass
class MockFundamentalData:
    symbol: str
    market: str
    name: Optional[str] = None
    market_cap: Optional[float] = None
    pe_ratio: Optional[float] = None
    pb_ratio: Optional[float] = None
    revenue: Optional[float] = None
    net_income: Optional[float] = None
    revenue_growth: Optional[float] = None
    profit_margin: Optional[float] = None
    analyst_rating: Optional[str] = None
    target_price: Optional[float] = None


@dataclass
class MockSectorFlowData:
    code: str
    name: str
    main_net_inflow: Decimal
    super_large_inflow: Decimal
    large_inflow: Decimal
    medium_inflow: Decimal
    small_inflow: Decimal
    main_pct: Decimal


@dataclass
class MockMarketBreadthData:
    index_code: str
    index_name: str
    close: float
    change_pct: float
    advancing: int
    declining: int
    unchanged: int


# --- Tests ---

class TestStorageServiceStoreFred:
    """Tests for store_fred_data."""

    def test_stores_fred_data(self):
        from src.services.storage import StorageService
        db = MagicMock()
        storage = StorageService(db)

        data = {
            "DGS10": [
                MockMacroDataPoint("DGS10", date(2026, 1, 15), Decimal("4.25")),
                MockMacroDataPoint("DGS10", date(2026, 1, 16), Decimal("4.30")),
            ],
            "CPIAUCSL": [
                MockMacroDataPoint("CPIAUCSL", date(2026, 1, 1), Decimal("312.5")),
            ],
        }
        result = storage.store_fred_data(data)

        assert result == 3
        db.execute.assert_called_once()
        db.commit.assert_called_once()

    def test_empty_data_returns_zero(self):
        from src.services.storage import StorageService
        db = MagicMock()
        storage = StorageService(db)

        result = storage.store_fred_data({})
        assert result == 0
        db.execute.assert_not_called()

    def test_empty_series_returns_zero(self):
        from src.services.storage import StorageService
        db = MagicMock()
        storage = StorageService(db)

        result = storage.store_fred_data({"DGS10": []})
        assert result == 0


class TestStorageServiceStoreYieldSpread:
    """Tests for store_yield_spread."""

    def test_stores_yield_spread(self):
        from src.services.storage import StorageService
        db = MagicMock()
        storage = StorageService(db)

        spread = MockYieldSpread(
            date=date(2026, 1, 15),
            dgs2=Decimal("4.10"),
            dgs10=Decimal("4.50"),
            spread=Decimal("0.40"),
        )
        result = storage.store_yield_spread(spread)

        assert result == 1
        db.execute.assert_called_once()
        db.commit.assert_called_once()

    def test_none_spread_returns_zero(self):
        from src.services.storage import StorageService
        db = MagicMock()
        storage = StorageService(db)

        result = storage.store_yield_spread(None)
        assert result == 0
        db.execute.assert_not_called()


class TestStorageServiceStoreNorthbound:
    """Tests for store_northbound_flow."""

    def test_stores_northbound_flows(self):
        from src.services.storage import StorageService
        db = MagicMock()
        storage = StorageService(db)

        flows = [
            MockNorthboundFlowData(date(2026, 1, 15), Decimal("50.12"), Decimal("520")),
            MockNorthboundFlowData(date(2026, 1, 16), Decimal("-30.5"), Decimal("530")),
        ]
        result = storage.store_northbound_flow(flows)

        assert result == 2
        db.execute.assert_called_once()
        db.commit.assert_called_once()

    def test_empty_flows_returns_zero(self):
        from src.services.storage import StorageService
        db = MagicMock()
        storage = StorageService(db)

        result = storage.store_northbound_flow([])
        assert result == 0


class TestStorageServiceStoreCnMacro:
    """Tests for store_cn_macro."""

    def test_stores_cn_macro_data(self):
        from src.services.storage import StorageService
        db = MagicMock()
        storage = StorageService(db)

        data = {
            "pmi": [
                MockCnMacroData("manufacturing_pmi", date(2026, 1, 1), Decimal("50.1"), Decimal("0.5")),
            ],
            "cpi": [
                MockCnMacroData("cpi_yoy", date(2025, 12, 1), Decimal("0.1"), None),
            ],
        }
        result = storage.store_cn_macro(data)

        assert result == 2
        db.execute.assert_called_once()

    def test_empty_data_returns_zero(self):
        from src.services.storage import StorageService
        db = MagicMock()
        storage = StorageService(db)

        result = storage.store_cn_macro({})
        assert result == 0


class TestStorageServiceStoreSectors:
    """Tests for store_sectors."""

    def test_stores_sector_data(self):
        from src.services.storage import StorageService
        db = MagicMock()
        storage = StorageService(db)

        data = {
            "industry": [
                MockSectorData("new_bankuai_001", "银行", 42, Decimal("8.5"),
                              Decimal("1.2"), Decimal("500000"), Decimal("425000"), "招商银行"),
            ],
            "concept": [
                MockSectorData("new_flzx_001", "人工智能", 120, Decimal("25.3"),
                              Decimal("3.5"), Decimal("800000"), Decimal("2000000"), "科大讯飞"),
            ],
        }
        result = storage.store_sectors(data)

        assert result == 2
        db.execute.assert_called_once()

    def test_empty_sectors_returns_zero(self):
        from src.services.storage import StorageService
        db = MagicMock()
        storage = StorageService(db)

        result = storage.store_sectors({})
        assert result == 0


class TestStorageServiceStoreMarketIndicators:
    """Tests for store_market_indicators."""

    def test_stores_market_indicators(self):
        from src.services.storage import StorageService
        db = MagicMock()
        storage = StorageService(db)

        indicators = [
            MockMarketIndicator("^VIX", "VIX恐慌指数", 18.5, -2.3, date(2026, 1, 15)),
            MockMarketIndicator("GC=F", "黄金", 2650.0, 0.5, date(2026, 1, 15)),
        ]
        result = storage.store_market_indicators(indicators)

        assert result == 2
        db.execute.assert_called_once()

    def test_skips_none_values(self):
        from src.services.storage import StorageService
        db = MagicMock()
        storage = StorageService(db)

        indicators = [
            MockMarketIndicator("^VIX", "VIX", None, None, None),
            MockMarketIndicator("GC=F", "Gold", 2650.0, 0.5, date(2026, 1, 15)),
        ]
        result = storage.store_market_indicators(indicators)

        # Only 1 stored (the one with None is skipped)
        assert result == 1

    def test_all_none_returns_zero(self):
        from src.services.storage import StorageService
        db = MagicMock()
        storage = StorageService(db)

        indicators = [
            MockMarketIndicator("^VIX", "VIX", None, None, None),
        ]
        result = storage.store_market_indicators(indicators)
        assert result == 0

    def test_empty_list_returns_zero(self):
        from src.services.storage import StorageService
        db = MagicMock()
        storage = StorageService(db)

        result = storage.store_market_indicators([])
        assert result == 0


class TestStorageServiceStoreFundamentals:
    """Tests for store_fundamentals."""

    def test_stores_fundamentals(self):
        from src.services.storage import StorageService
        db = MagicMock()
        storage = StorageService(db)

        fundamentals = [
            MockFundamentalData(
                symbol="GOOG", market="US", name="Alphabet Inc.",
                market_cap=2000000000000.0, pe_ratio=25.5, pb_ratio=6.8,
                revenue=300000000000.0, net_income=70000000000.0,
                revenue_growth=0.12, profit_margin=0.23,
                analyst_rating="buy", target_price=200.0,
            ),
            MockFundamentalData(
                symbol="01810", market="HK", name="小米集团",
                market_cap=500000000000.0, pe_ratio=18.0, pb_ratio=3.2,
            ),
        ]
        result = storage.store_fundamentals(fundamentals)

        assert result == 2
        db.execute.assert_called_once()

    def test_skips_none_entries(self):
        from src.services.storage import StorageService
        db = MagicMock()
        storage = StorageService(db)

        fundamentals = [None, MockFundamentalData(symbol="GOOG", market="US")]
        result = storage.store_fundamentals(fundamentals)

        assert result == 1

    def test_empty_list_returns_zero(self):
        from src.services.storage import StorageService
        db = MagicMock()
        storage = StorageService(db)

        result = storage.store_fundamentals([])
        assert result == 0

    def test_all_none_returns_zero(self):
        from src.services.storage import StorageService
        db = MagicMock()
        storage = StorageService(db)

        result = storage.store_fundamentals([None, None])
        assert result == 0


class TestStorageServiceStoreSectorFlows:
    """Tests for store_sector_flows."""

    def test_stores_sector_flows(self):
        from src.services.storage import StorageService
        db = MagicMock()
        storage = StorageService(db)

        data = {
            "industry": [
                MockSectorFlowData("BK1036", "半导体", Decimal("-1000"), Decimal("-700"),
                                   Decimal("-300"), Decimal("200"), Decimal("100"), Decimal("-5.5")),
            ],
            "concept": [
                MockSectorFlowData("BK2001", "AI", Decimal("500"), Decimal("300"),
                                   Decimal("200"), Decimal("-100"), Decimal("-50"), Decimal("3.2")),
            ],
        }
        result = storage.store_sector_flows(data)

        assert result == 2
        db.execute.assert_called_once()
        db.commit.assert_called_once()

    def test_empty_data_returns_zero(self):
        from src.services.storage import StorageService
        db = MagicMock()
        storage = StorageService(db)

        result = storage.store_sector_flows({})
        assert result == 0


class TestStorageServiceStoreMarketBreadth:
    """Tests for store_market_breadth."""

    def test_stores_market_breadth(self):
        from src.services.storage import StorageService
        db = MagicMock()
        storage = StorageService(db)

        breadth = [
            MockMarketBreadthData("000001", "上证指数", 3200.5, -1.2, 800, 1500, 60),
            MockMarketBreadthData("399001", "深证成指", 11000.3, -0.8, 1000, 1200, 50),
        ]
        result = storage.store_market_breadth(breadth)

        assert result == 2
        db.execute.assert_called_once()
        db.commit.assert_called_once()

    def test_empty_list_returns_zero(self):
        from src.services.storage import StorageService
        db = MagicMock()
        storage = StorageService(db)

        result = storage.store_market_breadth([])
        assert result == 0
