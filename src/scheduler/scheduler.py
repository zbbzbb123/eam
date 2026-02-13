"""APScheduler-based scheduled task framework."""
import logging
from typing import Any, Callable, Dict, List, Optional
from zoneinfo import ZoneInfo

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.jobstores.base import JobLookupError
from fastapi import APIRouter, HTTPException

TIMEZONE = ZoneInfo("Asia/Shanghai")

logger = logging.getLogger(__name__)

# Default schedule: when each task should run daily
DEFAULT_SCHEDULE = {
    "collect_market_data":      {"hour": 17, "minute": 0},     # A-share close data
    "collect_macro_data":       {"hour": 17, "minute": 10},    # Macro data
    "run_analyzers":            {"hour": 17, "minute": 20},    # Run signal analyzers
    "generate_daily_report_pm": {"hour": 17, "minute": 30},    # Daily report #1 (A-share)
    "collect_market_data_am":   {"hour": 6, "minute": 30},     # US overnight data
    "generate_daily_report_am": {"hour": 7, "minute": 0},      # Daily report #2 (US market)
}

# Weekly schedule
WEEKLY_SCHEDULE = {
    "generate_weekly_report_sat": {"day_of_week": 5, "hour": 7, "minute": 0},    # Saturday 07:00
    "generate_weekly_report_sun": {"day_of_week": 6, "hour": 22, "minute": 0},   # Sunday 22:00
}


def _collect_market_data() -> None:
    """Collect market data from structured collectors and persist to DB."""
    logger.info("Running scheduled market data collection")
    try:
        from src.collectors.registry import get_registry
        from src.db.database import SessionLocal
        from src.services.storage import StorageService

        registry = get_registry()
        db = SessionLocal()
        try:
            storage = StorageService(db)

            # Northbound flow
            info = registry.get("northbound")
            if info and info.is_configured():
                try:
                    result = registry.run("northbound")
                    n = storage.store_northbound_flow(result)
                    logger.info(f"Stored {n} northbound flow records")
                except Exception as e:
                    logger.error(f"Failed to collect northbound: {e}")

            # Sector data
            info = registry.get("sector")
            if info and info.is_configured():
                try:
                    result = registry.run("sector")
                    n = storage.store_sectors(result)
                    logger.info(f"Stored {n} sector snapshot records")
                except Exception as e:
                    logger.error(f"Failed to collect sector: {e}")

            # Market indicators (VIX, gold, silver, copper)
            info = registry.get("market_indicators")
            if info and info.is_configured():
                try:
                    result = registry.run("market_indicators")
                    n = storage.store_market_indicators(result)
                    logger.info(f"Stored {n} market indicator records")
                except Exception as e:
                    logger.error(f"Failed to collect market_indicators: {e}")

            # Fundamentals (holdings + watchlist)
            info = registry.get("fundamentals")
            if info and info.is_configured():
                try:
                    from src.db.models import Holding, HoldingStatus, Watchlist
                    holdings = db.query(Holding).filter(
                        Holding.status == HoldingStatus.ACTIVE
                    ).all()
                    pairs = [(h.symbol, h.market.value) for h in holdings if h.symbol != "CASH"]
                    # Also include watchlist symbols
                    watchlist_items = db.query(Watchlist).all()
                    watchlist_pairs = [(w.symbol, w.market.value) for w in watchlist_items]
                    # Deduplicate
                    all_pairs = list(set(pairs + watchlist_pairs))
                    if all_pairs:
                        collector = info.collector_class()
                        result = collector.fetch_all_holdings_fundamentals(all_pairs)
                        n = storage.store_fundamentals(result)
                        logger.info(f"Stored fundamentals for {n} symbols (holdings + watchlist)")
                except Exception as e:
                    logger.error(f"Failed to collect fundamentals: {e}")

            # Daily quotes for CN holdings (critical for afternoon report)
            try:
                from src.db.models import Holding, HoldingStatus, Watchlist, Market, DailyQuote
                from src.collectors.structured.akshare_collector import AkShareCollector
                from datetime import date, timedelta

                holdings = db.query(Holding).filter(
                    Holding.status == HoldingStatus.ACTIVE,
                    Holding.market == Market.CN
                ).all()
                symbols = [(h.symbol, h.market) for h in holdings if h.symbol != "CASH"]

                # Also include CN watchlist symbols
                watchlist_items = db.query(Watchlist).filter(
                    Watchlist.market == Market.CN
                ).all()
                symbols.extend([(w.symbol, w.market) for w in watchlist_items])
                symbols = list(set(symbols))

                if symbols:
                    collector = AkShareCollector()
                    today = date.today()
                    start = today - timedelta(days=7)
                    synced = 0
                    for symbol, market in symbols:
                        try:
                            quotes = collector.fetch_quotes(symbol, start, today, market.value)
                            for q in quotes:
                                existing = db.query(DailyQuote).filter(
                                    DailyQuote.symbol == symbol,
                                    DailyQuote.market == market,
                                    DailyQuote.trade_date == q.trade_date,
                                ).first()
                                if existing:
                                    existing.open = q.open
                                    existing.high = q.high
                                    existing.low = q.low
                                    existing.close = q.close
                                    existing.volume = q.volume
                                else:
                                    db.add(DailyQuote(
                                        symbol=symbol,
                                        market=market,
                                        trade_date=q.trade_date,
                                        open=q.open,
                                        high=q.high,
                                        low=q.low,
                                        close=q.close,
                                        volume=q.volume,
                                    ))
                                synced += 1
                        except Exception as e:
                            logger.warning(f"PM: Failed to sync quotes for {symbol}: {e}")
                    db.commit()
                    logger.info(f"PM: Synced {synced} daily quotes for {len(symbols)} CN symbols")
            except Exception as e:
                logger.error(f"PM: Failed to collect CN daily quotes: {e}")

            # Sector fund flows
            info = registry.get("sector_flow")
            if info and info.is_configured():
                try:
                    result = registry.run("sector_flow")
                    n = storage.store_sector_flows(result)
                    logger.info(f"Stored {n} sector fund flow records")
                except Exception as e:
                    logger.error(f"Failed to collect sector_flow: {e}")

            # Market breadth (advance/decline)
            info = registry.get("market_breadth")
            if info and info.is_configured():
                try:
                    result = registry.run("market_breadth")
                    n = storage.store_market_breadth(result)
                    logger.info(f"Stored {n} market breadth records")
                except Exception as e:
                    logger.error(f"Failed to collect market_breadth: {e}")

            # TuShare (index valuations + ETF NAVs)
            info = registry.get("tushare")
            if info and info.is_configured():
                try:
                    result = registry.run("tushare")
                    n = storage.store_tushare_data(result)
                    logger.info(f"Stored {n} TuShare records (index valuations + fund NAVs)")
                except Exception as e:
                    logger.error(f"Failed to collect tushare: {e}")
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Market data collection failed: {e}")


def _collect_macro_data() -> None:
    """Collect macroeconomic data and persist to DB."""
    logger.info("Running scheduled macro data collection")
    try:
        from src.collectors.registry import get_registry
        from src.db.database import SessionLocal
        from src.services.storage import StorageService
        from datetime import date, timedelta
        import asyncio

        registry = get_registry()
        db = SessionLocal()
        try:
            storage = StorageService(db)

            # FRED macro series
            info = registry.get("fred")
            if info and info.is_configured():
                try:
                    end = date.today()
                    start = end - timedelta(days=30)
                    result = registry.run("fred", start_date=start, end_date=end)
                    n = storage.store_fred_data(result)
                    logger.info(f"Stored {n} FRED data points")
                except Exception as e:
                    logger.error(f"Failed to collect fred: {e}")

                # Yield spread (separate call)
                try:
                    collector = info.collector_class()
                    spread = asyncio.run(collector.fetch_yield_spread())
                    n = storage.store_yield_spread(spread)
                    logger.info(f"Stored {n} yield spread record")
                except Exception as e:
                    logger.error(f"Failed to collect yield spread: {e}")

            # CN Macro (PMI/CPI/M2)
            info = registry.get("cn_macro")
            if info and info.is_configured():
                try:
                    result = registry.run("cn_macro")
                    n = storage.store_cn_macro(result)
                    logger.info(f"Stored {n} CN macro data points")
                except Exception as e:
                    logger.error(f"Failed to collect cn_macro: {e}")
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Macro data collection failed: {e}")


def _run_analyzers() -> None:
    """Run all registered analyzers."""
    logger.info("Running scheduled analyzers")
    try:
        from src.db.database import SessionLocal
        from src.services.analyzer_runner import AnalyzerRunner
        db = SessionLocal()
        try:
            runner = AnalyzerRunner(db=db)
            runner.run_all()
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Analyzer run failed: {e}")


def _generate_daily_report() -> None:
    """Generate daily brief report (macro + capital flow + commodities + LLM)."""
    logger.info("Running scheduled daily report generation")
    try:
        from src.db.database import SessionLocal
        from src.services.weekly_report import ReportService

        db = SessionLocal()
        try:
            service = ReportService()
            report = service.generate_daily_report(db)
            logger.info(
                f"Daily report generated: {len(report.sections)} sections, "
                f"AI advice: {'yes' if report.ai_advice else 'no'}"
            )
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Daily report generation failed: {e}")


def _generate_weekly_report() -> None:
    """Generate full weekly report (all analyzers + LLM advice)."""
    logger.info("Running scheduled weekly report generation")
    try:
        from src.db.database import SessionLocal
        from src.services.weekly_report import ReportService

        db = SessionLocal()
        try:
            service = ReportService()
            report = service.generate_weekly_report(db)
            logger.info(
                f"Weekly report generated: {len(report.sections)} sections, "
                f"AI advice: {'yes' if report.ai_advice else 'no'}"
            )
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Weekly report generation failed: {e}")


def _generate_daily_report_new() -> None:
    """Generate pre-stored daily report with per-holding AI commentary."""
    logger.info("Running scheduled daily report generation (new)")
    try:
        from src.services.report_generator import DailyReportGenerator
        from src.db.database import SessionLocal
        db = SessionLocal()
        try:
            gen = DailyReportGenerator(db)
            report_id = gen.generate()
            logger.info(f"Daily report generated, id={report_id}")
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Daily report generation failed: {e}")


def _collect_market_data_am() -> None:
    """Collect overnight US market data (morning run)."""
    logger.info("Running morning market data collection (US overnight)")
    try:
        from src.collectors.registry import get_registry
        from src.db.database import SessionLocal
        from src.services.storage import StorageService

        registry = get_registry()
        db = SessionLocal()
        try:
            storage = StorageService(db)

            # Market indicators (VIX, gold, silver, copper - updated overnight)
            info = registry.get("market_indicators")
            if info and info.is_configured():
                try:
                    result = registry.run("market_indicators")
                    n = storage.store_market_indicators(result)
                    logger.info(f"AM: Stored {n} market indicator records")
                except Exception as e:
                    logger.error(f"AM: Failed to collect market_indicators: {e}")

            # Daily quotes for US/HK holdings (critical for morning report)
            try:
                from src.db.models import Holding, HoldingStatus, Watchlist, Market, DailyQuote
                from src.collectors.structured.yfinance_collector import YFinanceCollector
                from datetime import date, timedelta

                holdings = db.query(Holding).filter(
                    Holding.status == HoldingStatus.ACTIVE,
                    Holding.market.in_([Market.US, Market.HK])
                ).all()
                symbols = [(h.symbol, h.market) for h in holdings if h.symbol != "CASH"]

                # Also include US/HK watchlist symbols
                watchlist_items = db.query(Watchlist).filter(
                    Watchlist.market.in_([Market.US, Market.HK])
                ).all()
                symbols.extend([(w.symbol, w.market) for w in watchlist_items])
                symbols = list(set(symbols))

                if symbols:
                    collector = YFinanceCollector()
                    today = date.today()
                    start = today - timedelta(days=7)  # Fetch last week to catch any gaps
                    synced = 0
                    for symbol, market in symbols:
                        try:
                            quotes = collector.fetch_quotes(symbol, start, today)
                            for q in quotes:
                                # Upsert: check if exists, update if so
                                existing = db.query(DailyQuote).filter(
                                    DailyQuote.symbol == symbol,
                                    DailyQuote.market == market,
                                    DailyQuote.trade_date == q.trade_date,
                                ).first()
                                if existing:
                                    existing.open = q.open
                                    existing.high = q.high
                                    existing.low = q.low
                                    existing.close = q.close
                                    existing.volume = q.volume
                                else:
                                    db.add(DailyQuote(
                                        symbol=symbol,
                                        market=market,
                                        trade_date=q.trade_date,
                                        open=q.open,
                                        high=q.high,
                                        low=q.low,
                                        close=q.close,
                                        volume=q.volume,
                                    ))
                                synced += 1
                        except Exception as e:
                            logger.warning(f"AM: Failed to sync quotes for {symbol}: {e}")
                    db.commit()
                    logger.info(f"AM: Synced {synced} daily quotes for {len(symbols)} US/HK symbols")
            except Exception as e:
                logger.error(f"AM: Failed to collect US/HK daily quotes: {e}")

            # Fundamentals for US/HK holdings
            info = registry.get("fundamentals")
            if info and info.is_configured():
                try:
                    from src.db.models import Holding, HoldingStatus, Watchlist, Market
                    holdings = db.query(Holding).filter(
                        Holding.status == HoldingStatus.ACTIVE,
                        Holding.market.in_([Market.US, Market.HK])
                    ).all()
                    pairs = [(h.symbol, h.market.value) for h in holdings if h.symbol != "CASH"]
                    watchlist_items = db.query(Watchlist).filter(
                        Watchlist.market.in_([Market.US, Market.HK])
                    ).all()
                    watchlist_pairs = [(w.symbol, w.market.value) for w in watchlist_items]
                    all_pairs = list(set(pairs + watchlist_pairs))
                    if all_pairs:
                        collector = info.collector_class()
                        result = collector.fetch_all_holdings_fundamentals(all_pairs)
                        n = storage.store_fundamentals(result)
                        logger.info(f"AM: Stored fundamentals for {n} US/HK symbols")
                except Exception as e:
                    logger.error(f"AM: Failed to collect US/HK fundamentals: {e}")
        finally:
            db.close()
    except Exception as e:
        logger.error(f"AM market data collection failed: {e}")


def _generate_weekly_report_new() -> None:
    """Generate pre-stored weekly report with strategic analysis."""
    logger.info("Running scheduled weekly report generation (new)")
    try:
        from src.services.report_generator import WeeklyReportGenerator
        from src.db.database import SessionLocal
        db = SessionLocal()
        try:
            gen = WeeklyReportGenerator(db)
            report_id = gen.generate()
            logger.info(f"Weekly report generated, id={report_id}")
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Weekly report generation failed: {e}")


def _collect_alternative_data() -> None:
    """Collect alternative data (GitHub, HuggingFace)."""
    logger.info("Running scheduled alternative data collection")
    try:
        from src.collectors.registry import get_registry
        registry = get_registry()
        for name in ["jisilu", "commodity", "sec13f"]:
            info = registry.get(name)
            if info and info.is_configured():
                try:
                    registry.run(name)
                    logger.info(f"Collected {name} data")
                except Exception as e:
                    logger.error(f"Failed to collect {name}: {e}")
    except Exception as e:
        logger.error(f"Alternative data collection failed: {e}")


# Map default schedule names to their functions
_DEFAULT_FUNCS = {
    "collect_market_data": _collect_market_data,
    "collect_macro_data": _collect_macro_data,
    "run_analyzers": _run_analyzers,
    "generate_daily_report_pm": _generate_daily_report_new,
    "collect_market_data_am": _collect_market_data_am,
    "generate_daily_report_am": _generate_daily_report_new,
}

_WEEKLY_FUNCS = {
    "generate_weekly_report_sat": _generate_weekly_report_new,
    "generate_weekly_report_sun": _generate_weekly_report_new,
}


class SchedulerService:
    """Scheduled task service using APScheduler BackgroundScheduler.

    Provides methods to add, list, and remove scheduled jobs. Integrates
    with the collector registry and analyzer runner for automatic data
    collection and analysis.
    """

    def __init__(self) -> None:
        self._scheduler = BackgroundScheduler()
        self._started = False

    @property
    def is_running(self) -> bool:
        """Whether the scheduler is currently running."""
        return self._started

    def start(self) -> None:
        """Start the scheduler. Safe to call multiple times."""
        if self._started:
            return
        self._scheduler.start()
        self._started = True
        logger.info("Scheduler started")

    def stop(self) -> None:
        """Stop the scheduler. Safe to call when not running."""
        if not self._started:
            return
        self._scheduler.shutdown(wait=False)
        self._started = False
        logger.info("Scheduler stopped")

    def add_daily_job(
        self,
        func: Callable,
        hour: int,
        minute: int,
        name: str,
    ) -> str:
        """Schedule a job to run daily at a specific time.

        Args:
            func: The callable to execute.
            hour: Hour of day (0-23).
            minute: Minute of hour (0-59).
            name: Human-readable job name (also used as job ID).

        Returns:
            The job ID.
        """
        trigger = CronTrigger(hour=hour, minute=minute, timezone=TIMEZONE)
        job = self._scheduler.add_job(func, trigger=trigger, id=name, name=name, replace_existing=True)
        logger.info(f"Added daily job '{name}' at {hour:02d}:{minute:02d} CST")
        return job.id

    def add_interval_job(
        self,
        func: Callable,
        hours: int,
        name: str,
    ) -> str:
        """Schedule a job to run at a fixed interval.

        Args:
            func: The callable to execute.
            hours: Interval in hours.
            name: Human-readable job name (also used as job ID).

        Returns:
            The job ID.
        """
        trigger = IntervalTrigger(hours=hours)
        job = self._scheduler.add_job(func, trigger=trigger, id=name, name=name, replace_existing=True)
        logger.info(f"Added interval job '{name}' every {hours}h")
        return job.id

    def list_jobs(self) -> List[Dict[str, Any]]:
        """List all scheduled jobs.

        Returns:
            List of dicts with id, name, trigger, and next_run_time.
        """
        jobs = self._scheduler.get_jobs()
        return [
            {
                "id": job.id,
                "name": job.name,
                "trigger": str(job.trigger),
                "next_run_time": str(job.next_run_time) if job.next_run_time else None,
            }
            for job in jobs
        ]

    def remove_job(self, job_id: str) -> bool:
        """Remove a scheduled job by ID.

        Args:
            job_id: The job ID to remove.

        Returns:
            True if removed, False if not found.
        """
        try:
            self._scheduler.remove_job(job_id)
            logger.info(f"Removed job '{job_id}'")
            return True
        except JobLookupError:
            return False

    def add_weekly_job(
        self,
        func: Callable,
        day_of_week: int,
        hour: int,
        minute: int,
        name: str,
    ) -> str:
        """Schedule a job to run weekly on a specific day and time.

        Args:
            func: The callable to execute.
            day_of_week: Day of week (0=Mon, 6=Sun).
            hour: Hour of day (0-23).
            minute: Minute of hour (0-59).
            name: Human-readable job name (also used as job ID).

        Returns:
            The job ID.
        """
        trigger = CronTrigger(day_of_week=day_of_week, hour=hour, minute=minute, timezone=TIMEZONE)
        job = self._scheduler.add_job(func, trigger=trigger, id=name, name=name, replace_existing=True)
        logger.info(f"Added weekly job '{name}' on day {day_of_week} at {hour:02d}:{minute:02d} CST")
        return job.id

    def setup_default_jobs(self) -> None:
        """Register all jobs from DEFAULT_SCHEDULE and WEEKLY_SCHEDULE."""
        for name, config in DEFAULT_SCHEDULE.items():
            func = _DEFAULT_FUNCS.get(name)
            if func:
                self.add_daily_job(func, hour=config["hour"], minute=config["minute"], name=name)
        for name, config in WEEKLY_SCHEDULE.items():
            func = _WEEKLY_FUNCS.get(name)
            if func:
                self.add_weekly_job(
                    func,
                    day_of_week=config["day_of_week"],
                    hour=config["hour"],
                    minute=config["minute"],
                    name=name,
                )


# ---------------------------------------------------------------------------
# Singleton for app-wide use
# ---------------------------------------------------------------------------
_scheduler_service: Optional[SchedulerService] = None


def get_scheduler_service() -> SchedulerService:
    """Get or create the global SchedulerService singleton."""
    global _scheduler_service
    if _scheduler_service is None:
        _scheduler_service = SchedulerService()
    return _scheduler_service


# ---------------------------------------------------------------------------
# FastAPI router
# ---------------------------------------------------------------------------
router = APIRouter(prefix="/scheduler", tags=["scheduler"])


@router.get("/jobs")
def list_scheduled_jobs() -> List[Dict[str, Any]]:
    """List all scheduled jobs."""
    service = get_scheduler_service()
    return service.list_jobs()


@router.delete("/jobs/{job_id}")
def delete_scheduled_job(job_id: str) -> Dict[str, Any]:
    """Remove a scheduled job by ID."""
    service = get_scheduler_service()
    removed = service.remove_job(job_id)
    if not removed:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")
    return {"status": "removed", "job_id": job_id}
