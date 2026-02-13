"""Tests for Northbound Flow Collector (TuShare API)."""
import pytest
from datetime import date
from decimal import Decimal
from unittest.mock import patch, MagicMock

import pandas as pd

from src.collectors.structured.northbound_collector import (
    NorthboundCollector,
    NorthboundFlowData,
)


# --- Realistic TuShare DataFrame fixtures ---

def _make_tushare_df():
    """Create a mock DataFrame similar to moneyflow_hsgt output."""
    return pd.DataFrame({
        "trade_date": ["20260205", "20260204", "20260203"],
        "ggt_ss": [500.0, -300.0, 200.0],      # 港股通(沪) 百万元
        "ggt_sz": [400.0, -200.0, 100.0],      # 港股通(深) 百万元
        "hgt": [800.0, -600.0, 400.0],          # 沪股通 百万元
        "sgt": [500.0, -400.0, 300.0],          # 深股通 百万元
        "north_money": [1300.0, -1000.0, 700.0], # 北向资金 百万元
        "south_money": [900.0, -500.0, 300.0],  # 南向资金 百万元
    })


def _make_tushare_df_with_nan():
    """DataFrame with some NaN values."""
    import math
    return pd.DataFrame({
        "trade_date": ["20260205"],
        "ggt_ss": [float("nan")],
        "ggt_sz": [float("nan")],
        "hgt": [800.0],
        "sgt": [float("nan")],
        "north_money": [800.0],
        "south_money": [float("nan")],
    })


class TestNorthboundCollectorProperties:
    """Tests for NorthboundCollector properties."""

    @patch("src.collectors.structured.northbound_collector.get_settings")
    @patch("src.collectors.structured.northbound_collector.ts")
    def test_name_property(self, mock_ts, mock_settings):
        mock_settings.return_value.tushare_token = "test_token"
        mock_ts.pro_api.return_value = MagicMock()
        collector = NorthboundCollector()
        assert collector.name == "northbound_collector"

    @patch("src.collectors.structured.northbound_collector.get_settings")
    @patch("src.collectors.structured.northbound_collector.ts")
    def test_source_property(self, mock_ts, mock_settings):
        mock_settings.return_value.tushare_token = "test_token"
        mock_ts.pro_api.return_value = MagicMock()
        collector = NorthboundCollector()
        assert collector.source == "tushare"


class TestNorthboundCollectorFetchDailyNetFlow:
    """Tests for NorthboundCollector fetch_daily_net_flow method."""

    _SENTINEL = object()

    @patch("src.collectors.structured.northbound_collector.get_settings")
    @patch("src.collectors.structured.northbound_collector.ts")
    def _make_collector(self, mock_ts, mock_settings, df=_SENTINEL):
        mock_settings.return_value.tushare_token = "test_token"
        mock_pro = MagicMock()
        mock_pro.moneyflow_hsgt.return_value = df if df is not self._SENTINEL else _make_tushare_df()
        mock_ts.pro_api.return_value = mock_pro
        return NorthboundCollector()

    def test_fetch_returns_list(self):
        collector = self._make_collector()
        result = collector.fetch_daily_net_flow()
        assert isinstance(result, list)
        assert len(result) == 3
        assert all(isinstance(item, NorthboundFlowData) for item in result)

    def test_fetch_correct_data_conversion(self):
        collector = self._make_collector()
        result = collector.fetch_daily_net_flow()
        # Results sorted ascending by date
        assert result[0].trade_date == date(2026, 2, 3)
        # 700 百万元 / 100 = 7 亿元
        assert result[0].net_flow == Decimal("700.0") / Decimal("100")
        # 400 / 100 = 4
        assert result[0].hgt == Decimal("400.0") / Decimal("100")
        assert result[0].sgt == Decimal("300.0") / Decimal("100")
        assert result[0].south_money == Decimal("300.0") / Decimal("100")

    def test_fetch_sorted_ascending(self):
        collector = self._make_collector()
        result = collector.fetch_daily_net_flow()
        dates = [r.trade_date for r in result]
        assert dates == sorted(dates)

    def test_fetch_negative_flow(self):
        collector = self._make_collector()
        result = collector.fetch_daily_net_flow()
        # Second entry (2026-02-04): north_money = -1000 百万元
        feb4 = [r for r in result if r.trade_date == date(2026, 2, 4)][0]
        assert feb4.net_flow == Decimal("-1000.0") / Decimal("100")

    def test_fetch_empty_response(self):
        collector = self._make_collector(df=pd.DataFrame())
        result = collector.fetch_daily_net_flow()
        assert result == []

    def test_fetch_none_response(self):
        collector = self._make_collector(df=None)
        result = collector.fetch_daily_net_flow()
        assert result == []

    def test_fetch_handles_nan(self):
        collector = self._make_collector(df=_make_tushare_df_with_nan())
        result = collector.fetch_daily_net_flow()
        assert len(result) == 1
        # north_money=800, hgt=800, sgt=NaN→None
        assert result[0].net_flow == Decimal("800.0") / Decimal("100")
        assert result[0].hgt == Decimal("800.0") / Decimal("100")
        assert result[0].sgt is None
        assert result[0].south_money is None

    def test_fetch_respects_limit(self):
        collector = self._make_collector()
        result = collector.fetch_daily_net_flow(limit=2)
        assert len(result) == 2
        # Should keep the latest 2
        assert result[0].trade_date == date(2026, 2, 4)
        assert result[1].trade_date == date(2026, 2, 5)

    def test_fetch_no_token_returns_empty(self):
        with patch("src.collectors.structured.northbound_collector.get_settings") as mock_settings:
            mock_settings.return_value.tushare_token = ""
            collector = NorthboundCollector()
            result = collector.fetch_daily_net_flow()
            assert result == []


class TestNorthboundFlowData:
    """Tests for NorthboundFlowData data class."""

    def test_creation(self):
        data = NorthboundFlowData(
            trade_date=date(2026, 2, 5),
            net_flow=Decimal("13.0"),
            hgt=Decimal("8.0"),
            sgt=Decimal("5.0"),
            south_money=Decimal("9.0"),
        )
        assert data.trade_date == date(2026, 2, 5)
        assert data.net_flow == Decimal("13.0")
        assert data.hgt == Decimal("8.0")
        assert data.sgt == Decimal("5.0")
        assert data.south_money == Decimal("9.0")

    def test_to_dict(self):
        data = NorthboundFlowData(
            trade_date=date(2026, 2, 5),
            net_flow=Decimal("13.0"),
            hgt=Decimal("8.0"),
            sgt=Decimal("5.0"),
        )
        d = data.to_dict()
        assert d["trade_date"] == date(2026, 2, 5)
        assert d["net_flow"] == Decimal("13.0")
        assert d["hgt"] == Decimal("8.0")
        assert d["sgt"] == Decimal("5.0")
        assert d["south_money"] is None
        assert d["quota_remaining"] is None

    def test_defaults(self):
        data = NorthboundFlowData(
            trade_date=date(2026, 2, 5),
            net_flow=Decimal("10.0"),
        )
        assert data.hgt is None
        assert data.sgt is None
        assert data.south_money is None
        assert data.quota_remaining is None


class TestNorthboundCollectorGetLatestFlow:
    """Tests for NorthboundCollector get_latest_flow method."""

    @patch("src.collectors.structured.northbound_collector.get_settings")
    @patch("src.collectors.structured.northbound_collector.ts")
    def test_returns_most_recent(self, mock_ts, mock_settings):
        mock_settings.return_value.tushare_token = "test_token"
        mock_pro = MagicMock()
        mock_pro.moneyflow_hsgt.return_value = _make_tushare_df()
        mock_ts.pro_api.return_value = mock_pro
        collector = NorthboundCollector()
        result = collector.get_latest_flow()
        assert result is not None
        assert result.trade_date == date(2026, 2, 5)

    @patch("src.collectors.structured.northbound_collector.get_settings")
    @patch("src.collectors.structured.northbound_collector.ts")
    def test_empty_returns_none(self, mock_ts, mock_settings):
        mock_settings.return_value.tushare_token = "test_token"
        mock_pro = MagicMock()
        mock_pro.moneyflow_hsgt.return_value = pd.DataFrame()
        mock_ts.pro_api.return_value = mock_pro
        collector = NorthboundCollector()
        result = collector.get_latest_flow()
        assert result is None
