"""Price alert analyzer for holdings."""
from typing import List, Optional
import logging

from sqlalchemy.orm import Session
from sqlalchemy import select

from src.analyzers.base import BaseAnalyzer, AnalyzerResult
from src.db.models import Holding, HoldingStatus, Market, SignalSeverity
from src.collectors.structured.yfinance_collector import YFinanceCollector
from src.collectors.structured.akshare_collector import AkShareCollector

logger = logging.getLogger(__name__)

# Thresholds
LARGE_MOVE_THRESHOLD = 0.05  # 5% daily move triggers alert


class PriceAlertAnalyzer(BaseAnalyzer):
    """
    Analyzer for price-based alerts on holdings.

    Monitors:
    - Stop loss triggers
    - Take profit triggers
    - Large daily moves (>5%)
    - 52-week high/low (future enhancement)
    """

    def __init__(self, db: Session):
        """
        Initialize price alert analyzer.

        Args:
            db: Database session for fetching holdings.
        """
        self._db = db
        self._us_collector = YFinanceCollector()
        self._cn_collector = AkShareCollector()

    @property
    def name(self) -> str:
        return "price_alert_analyzer"

    @property
    def sector(self) -> str:
        return "price"

    def _get_current_price(self, symbol: str, market: Market) -> Optional[float]:
        """Get current price for a symbol."""
        try:
            if market == Market.US:
                quote = self._us_collector.fetch_latest_quote(symbol)
            else:
                quote = self._cn_collector.fetch_latest_quote(symbol, market.value)

            if quote and quote.close:
                return float(quote.close)
        except Exception as e:
            logger.error(f"Error fetching price for {symbol}: {e}")
        return None

    def _get_previous_close(self, symbol: str, market: Market) -> Optional[float]:
        """Get previous close price."""
        # For MVP, return None - in production, fetch from database or calculate
        return None

    def analyze(self) -> List[AnalyzerResult]:
        """Analyze prices for all active holdings."""
        results = []

        # Get all active holdings
        holdings = self._db.execute(
            select(Holding).where(Holding.status == HoldingStatus.ACTIVE)
        ).scalars().all()

        for holding in holdings:
            current_price = self._get_current_price(holding.symbol, holding.market)
            if current_price is None:
                continue

            # Check stop loss
            if holding.stop_loss_price:
                stop_loss_result = self._check_stop_loss(holding, current_price)
                if stop_loss_result:
                    results.append(stop_loss_result)
                    continue  # Don't check other conditions if stop loss triggered

            # Check take profit
            if holding.take_profit_price:
                take_profit_result = self._check_take_profit(holding, current_price)
                if take_profit_result:
                    results.append(take_profit_result)
                    continue

            # Check large daily move
            prev_close = self._get_previous_close(holding.symbol, holding.market)
            if prev_close:
                move_result = self._check_large_move(holding, current_price, prev_close)
                if move_result:
                    results.append(move_result)

        return results

    def _check_stop_loss(
        self,
        holding: Holding,
        current_price: float
    ) -> Optional[AnalyzerResult]:
        """Check if stop loss is triggered."""
        stop_loss = float(holding.stop_loss_price)

        if current_price <= stop_loss:
            loss_pct = ((current_price - float(holding.avg_cost)) / float(holding.avg_cost)) * 100

            return AnalyzerResult(
                title=f"STOP LOSS TRIGGERED: {holding.symbol}",
                description=(
                    f"{holding.symbol} has hit stop loss at ${stop_loss:.2f}. "
                    f"Current price: ${current_price:.2f}. "
                    f"Your avg cost: ${float(holding.avg_cost):.2f}. "
                    f"Position P/L: {loss_pct:.1f}%. "
                    f"Consider executing stop loss order."
                ),
                severity=SignalSeverity.CRITICAL,
                data={
                    "symbol": holding.symbol,
                    "current_price": current_price,
                    "stop_loss": stop_loss,
                    "avg_cost": float(holding.avg_cost),
                    "loss_pct": round(loss_pct, 2),
                    "alert_type": "stop_loss",
                },
                related_symbols=[holding.symbol],
            )

        return None

    def _check_take_profit(
        self,
        holding: Holding,
        current_price: float
    ) -> Optional[AnalyzerResult]:
        """Check if take profit is triggered."""
        take_profit = float(holding.take_profit_price)

        if current_price >= take_profit:
            gain_pct = ((current_price - float(holding.avg_cost)) / float(holding.avg_cost)) * 100

            return AnalyzerResult(
                title=f"TAKE PROFIT REACHED: {holding.symbol}",
                description=(
                    f"{holding.symbol} has reached take profit target at ${take_profit:.2f}. "
                    f"Current price: ${current_price:.2f}. "
                    f"Your avg cost: ${float(holding.avg_cost):.2f}. "
                    f"Position gain: +{gain_pct:.1f}%. "
                    f"Consider taking profits or adjusting target."
                ),
                severity=SignalSeverity.HIGH,
                data={
                    "symbol": holding.symbol,
                    "current_price": current_price,
                    "take_profit": take_profit,
                    "avg_cost": float(holding.avg_cost),
                    "gain_pct": round(gain_pct, 2),
                    "alert_type": "take_profit",
                },
                related_symbols=[holding.symbol],
            )

        return None

    def _check_large_move(
        self,
        holding: Holding,
        current_price: float,
        prev_close: float
    ) -> Optional[AnalyzerResult]:
        """Check for large daily price move."""
        change_pct = (current_price - prev_close) / prev_close

        if abs(change_pct) >= LARGE_MOVE_THRESHOLD:
            direction = "up" if change_pct > 0 else "down"

            return AnalyzerResult(
                title=f"Large Move: {holding.symbol} {direction} {abs(change_pct)*100:.1f}%",
                description=(
                    f"{holding.symbol} moved {direction} {abs(change_pct)*100:.1f}% today. "
                    f"Previous close: ${prev_close:.2f}, Current: ${current_price:.2f}. "
                    f"Review news and consider if position adjustment needed."
                ),
                severity=SignalSeverity.MEDIUM,
                data={
                    "symbol": holding.symbol,
                    "current_price": current_price,
                    "prev_close": prev_close,
                    "change_pct": round(change_pct * 100, 2),
                    "alert_type": "large_move",
                },
                related_symbols=[holding.symbol],
            )

        return None
