"""Tests for SchedulerService."""
import pytest
from unittest.mock import MagicMock, patch, call
from datetime import datetime

from src.scheduler.scheduler import SchedulerService, DEFAULT_SCHEDULE


class TestSchedulerService:
    """Tests for SchedulerService initialization and lifecycle."""

    def test_create_scheduler_service(self):
        """SchedulerService can be instantiated."""
        service = SchedulerService()
        assert service is not None
        assert service.is_running is False

    def test_start_and_stop(self):
        """Scheduler can be started and stopped."""
        service = SchedulerService()
        service.start()
        assert service.is_running is True
        service.stop()
        assert service.is_running is False

    def test_stop_when_not_running(self):
        """Stopping a non-running scheduler does not raise."""
        service = SchedulerService()
        service.stop()  # Should not raise

    def test_start_twice_no_error(self):
        """Starting an already-running scheduler does not raise."""
        service = SchedulerService()
        service.start()
        service.start()  # Should not raise
        assert service.is_running is True
        service.stop()


class TestAddJobs:
    """Tests for adding scheduled jobs."""

    def setup_method(self):
        self.service = SchedulerService()
        self.service.start()

    def teardown_method(self):
        self.service.stop()

    def test_add_daily_job(self):
        """Can add a daily job."""
        func = MagicMock()
        self.service.add_daily_job(func, hour=17, minute=0, name="test_daily")
        jobs = self.service.list_jobs()
        assert len(jobs) == 1
        assert jobs[0]["name"] == "test_daily"

    def test_add_interval_job(self):
        """Can add an interval job."""
        func = MagicMock()
        self.service.add_interval_job(func, hours=6, name="test_interval")
        jobs = self.service.list_jobs()
        assert len(jobs) == 1
        assert jobs[0]["name"] == "test_interval"

    def test_add_multiple_jobs(self):
        """Can add multiple jobs and list them all."""
        self.service.add_daily_job(MagicMock(), hour=9, minute=0, name="job1")
        self.service.add_daily_job(MagicMock(), hour=10, minute=0, name="job2")
        self.service.add_interval_job(MagicMock(), hours=1, name="job3")
        jobs = self.service.list_jobs()
        assert len(jobs) == 3
        names = {j["name"] for j in jobs}
        assert names == {"job1", "job2", "job3"}

    def test_list_jobs_returns_details(self):
        """list_jobs returns id, name, trigger, and next_run_time."""
        self.service.add_daily_job(MagicMock(), hour=17, minute=30, name="detailed")
        jobs = self.service.list_jobs()
        job = jobs[0]
        assert "id" in job
        assert "name" in job
        assert "trigger" in job
        assert "next_run_time" in job


class TestRemoveJob:
    """Tests for removing jobs."""

    def setup_method(self):
        self.service = SchedulerService()
        self.service.start()

    def teardown_method(self):
        self.service.stop()

    def test_remove_job_by_id(self):
        """Can remove a job by its ID."""
        self.service.add_daily_job(MagicMock(), hour=9, minute=0, name="removeme")
        jobs = self.service.list_jobs()
        job_id = jobs[0]["id"]
        result = self.service.remove_job(job_id)
        assert result is True
        assert len(self.service.list_jobs()) == 0

    def test_remove_nonexistent_job(self):
        """Removing a nonexistent job returns False."""
        result = self.service.remove_job("nonexistent_id")
        assert result is False


class TestDefaultSchedule:
    """Tests for default schedule configuration."""

    def test_default_schedule_has_expected_keys(self):
        """DEFAULT_SCHEDULE contains expected job configurations."""
        assert "collect_market_data" in DEFAULT_SCHEDULE
        assert "collect_macro_data" in DEFAULT_SCHEDULE
        assert "run_analyzers" in DEFAULT_SCHEDULE
        assert "collect_alternative_data" in DEFAULT_SCHEDULE

    def test_default_schedule_values(self):
        """DEFAULT_SCHEDULE values have hour and minute."""
        for name, config in DEFAULT_SCHEDULE.items():
            assert "hour" in config, f"{name} missing 'hour'"
            assert "minute" in config, f"{name} missing 'minute'"

    def test_setup_default_jobs(self):
        """setup_default_jobs registers jobs from DEFAULT_SCHEDULE."""
        service = SchedulerService()
        service.start()
        service.setup_default_jobs()
        jobs = service.list_jobs()
        # Should have at least the 4 default jobs
        assert len(jobs) >= 4
        names = {j["name"] for j in jobs}
        for key in DEFAULT_SCHEDULE:
            assert key in names
        service.stop()


class TestSchedulerServiceAPI:
    """Tests for the scheduler FastAPI router."""

    def test_router_exists(self):
        """The scheduler module exposes a FastAPI router."""
        from src.scheduler.scheduler import router
        assert router is not None

    def test_list_jobs_endpoint(self):
        """The /scheduler/jobs endpoint is registered."""
        from src.scheduler.scheduler import router
        paths = [r.path for r in router.routes]
        assert any("/jobs" in p for p in paths)

    def test_delete_job_endpoint(self):
        """The /scheduler/jobs/{job_id} DELETE endpoint is registered."""
        from src.scheduler.scheduler import router
        paths = [r.path for r in router.routes]
        assert any("/jobs/{job_id}" in p for p in paths)
