"""Tests for InsiderTrade database model."""
import pytest
from datetime import date, datetime
from decimal import Decimal

from src.db.models_insider import InsiderTrade, InsiderTradeType


class TestInsiderTradeType:
    """Tests for InsiderTradeType enum."""

    def test_insider_trade_type_purchase(self):
        """Test InsiderTradeType.PURCHASE value."""
        assert InsiderTradeType.PURCHASE.value == "purchase"

    def test_insider_trade_type_sale(self):
        """Test InsiderTradeType.SALE value."""
        assert InsiderTradeType.SALE.value == "sale"


class TestInsiderTradeModel:
    """Tests for InsiderTrade model."""

    def test_insider_trade_creation(self):
        """Test creating an InsiderTrade instance."""
        trade = InsiderTrade(
            filing_date=datetime(2026, 1, 23, 21, 52, 11),
            trade_date=date(2026, 1, 20),
            ticker="AAPL",
            company_name="Apple Inc.",
            insider_name="Cook Tim",
            insider_title="CEO",
            trade_type=InsiderTradeType.PURCHASE,
            price=Decimal("150.50"),
            quantity=10000,
            shares_owned_after=1500000,
            value=Decimal("1505000"),
            source="openinsider",
        )

        assert trade.ticker == "AAPL"
        assert trade.company_name == "Apple Inc."
        assert trade.insider_name == "Cook Tim"
        assert trade.insider_title == "CEO"
        assert trade.trade_type == InsiderTradeType.PURCHASE
        assert trade.price == Decimal("150.50")
        assert trade.quantity == 10000
        assert trade.shares_owned_after == 1500000
        assert trade.value == Decimal("1505000")
        assert trade.source == "openinsider"

    def test_insider_trade_sale_creation(self):
        """Test creating an InsiderTrade sale instance."""
        trade = InsiderTrade(
            filing_date=datetime(2026, 1, 22, 15, 30, 0),
            trade_date=date(2026, 1, 21),
            ticker="MSFT",
            company_name="Microsoft Corp",
            insider_name="Nadella Satya",
            insider_title="CEO",
            trade_type=InsiderTradeType.SALE,
            price=Decimal("420.00"),
            quantity=5000,
            shares_owned_after=500000,
            value=Decimal("2100000"),
            source="openinsider",
        )

        assert trade.trade_type == InsiderTradeType.SALE
        assert trade.ticker == "MSFT"
        assert trade.quantity == 5000

    def test_insider_trade_optional_fields(self):
        """Test InsiderTrade with optional fields."""
        trade = InsiderTrade(
            filing_date=datetime(2026, 1, 23),
            trade_date=date(2026, 1, 20),
            ticker="AAPL",
            company_name="Apple Inc.",
            insider_name="Cook Tim",
            insider_title="CEO",
            trade_type=InsiderTradeType.PURCHASE,
            price=Decimal("150.50"),
            quantity=10000,
            shares_owned_after=1500000,
            value=Decimal("1505000"),
            source="openinsider",
        )

        # Optional fields should be None by default
        assert trade.sec_form_url is None

    def test_insider_trade_with_sec_form_url(self):
        """Test InsiderTrade with SEC form URL."""
        trade = InsiderTrade(
            filing_date=datetime(2026, 1, 23, 21, 52, 11),
            trade_date=date(2026, 1, 20),
            ticker="AAPL",
            company_name="Apple Inc.",
            insider_name="Cook Tim",
            insider_title="CEO",
            trade_type=InsiderTradeType.PURCHASE,
            price=Decimal("150.50"),
            quantity=10000,
            shares_owned_after=1500000,
            value=Decimal("1505000"),
            source="openinsider",
            sec_form_url="http://www.sec.gov/Archives/edgar/data/123/example.xml",
        )

        assert trade.sec_form_url == "http://www.sec.gov/Archives/edgar/data/123/example.xml"
