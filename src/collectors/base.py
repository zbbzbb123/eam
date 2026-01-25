"""Base collector class."""
from abc import ABC, abstractmethod
from typing import List, Optional
from datetime import date

from pydantic import BaseModel


class QuoteData(BaseModel):
    """Quote data model."""
    symbol: str
    trade_date: date
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    close: Optional[float] = None
    volume: Optional[int] = None


class BaseCollector(ABC):
    """Abstract base class for data collectors."""

    @abstractmethod
    def fetch_quotes(
        self,
        symbol: str,
        start_date: date,
        end_date: date,
    ) -> List[QuoteData]:
        """Fetch historical quotes for a symbol."""
        pass

    @abstractmethod
    def fetch_latest_quote(self, symbol: str) -> Optional[QuoteData]:
        """Fetch the latest quote for a symbol."""
        pass
