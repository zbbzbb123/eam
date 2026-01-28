"""APScheduler-based scheduled task framework."""
import logging
from typing import Any, Callable, Dict, List, Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.jobstores.base import JobLookupError
from fastapi import APIRouter, HTTPException

logger = logging.getLogger(__name__)

# Default schedule: when each task should run daily
DEFAULT_SCHEDULE = {
    "collect_market_data": {"hour": 17, "minute": 0},       # After market close
    "collect_macro_data": {"hour": 18, "minute": 0},         # Daily evening
    "run_analyzers": {"hour": 18, "minute": 30},              # After data collection
    "collect_alternative_data": {"hour": 19, "minute": 0},    # GitHub, HuggingFace weekly
}


def _collect_market_data() -> None:
    """Collect market data from structured collectors."""
    logger.info("Running scheduled market data collection")
    try:
        from src.collectors.registry import get_registry
        registry = get_registry()
        for name in ["northbound", "tushare"]:
            info = registry.get(name)
            if info and info.is_configured():
                try:
                    registry.run(name)
                    logger.info(f"Collected {name} data")
                except Exception as e:
                    logger.error(f"Failed to collect {name}: {e}")
    except Exception as e:
        logger.error(f"Market data collection failed: {e}")


def _collect_macro_data() -> None:
    """Collect macroeconomic data."""
    logger.info("Running scheduled macro data collection")
    try:
        from src.collectors.registry import get_registry
        registry = get_registry()
        for name in ["fred"]:
            info = registry.get(name)
            if info and info.is_configured():
                try:
                    registry.run(name)
                    logger.info(f"Collected {name} data")
                except Exception as e:
                    logger.error(f"Failed to collect {name}: {e}")
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


def _collect_alternative_data() -> None:
    """Collect alternative data (GitHub, HuggingFace)."""
    logger.info("Running scheduled alternative data collection")
    try:
        from src.collectors.registry import get_registry
        registry = get_registry()
        for name in ["github", "huggingface", "openinsider", "jisilu", "commodity", "sec13f"]:
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
    "collect_alternative_data": _collect_alternative_data,
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
        trigger = CronTrigger(hour=hour, minute=minute)
        job = self._scheduler.add_job(func, trigger=trigger, id=name, name=name, replace_existing=True)
        logger.info(f"Added daily job '{name}' at {hour:02d}:{minute:02d}")
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

    def setup_default_jobs(self) -> None:
        """Register all jobs from DEFAULT_SCHEDULE."""
        for name, config in DEFAULT_SCHEDULE.items():
            func = _DEFAULT_FUNCS.get(name)
            if func:
                self.add_daily_job(func, hour=config["hour"], minute=config["minute"], name=name)


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
