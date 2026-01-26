"""Tests for GitHub collector."""
import pytest
from datetime import datetime
from unittest.mock import Mock, patch, AsyncMock

import httpx

from src.collectors.structured.github_collector import GitHubCollector, GitHubRepoMetrics


class TestGitHubRepoMetrics:
    """Tests for GitHubRepoMetrics dataclass."""

    def test_github_repo_metrics_creation(self):
        """Test GitHubRepoMetrics can be created with required fields."""
        metrics = GitHubRepoMetrics(
            owner="openai",
            repo="openai-python",
            stars=10000,
            forks=1500,
            watchers=500,
            open_issues=120,
            language="Python",
            created_at=datetime(2020, 1, 15),
            updated_at=datetime(2025, 1, 20),
            recent_commits=150,
        )

        assert metrics.owner == "openai"
        assert metrics.repo == "openai-python"
        assert metrics.stars == 10000
        assert metrics.forks == 1500
        assert metrics.watchers == 500
        assert metrics.open_issues == 120
        assert metrics.language == "Python"
        assert metrics.created_at == datetime(2020, 1, 15)
        assert metrics.updated_at == datetime(2025, 1, 20)
        assert metrics.recent_commits == 150

    def test_github_repo_metrics_to_dict(self):
        """Test GitHubRepoMetrics to_dict method."""
        metrics = GitHubRepoMetrics(
            owner="openai",
            repo="openai-python",
            stars=10000,
            forks=1500,
            watchers=500,
            open_issues=120,
            language="Python",
            created_at=datetime(2020, 1, 15),
            updated_at=datetime(2025, 1, 20),
            recent_commits=150,
        )

        d = metrics.to_dict()

        assert d["owner"] == "openai"
        assert d["repo"] == "openai-python"
        assert d["stars"] == 10000
        assert d["forks"] == 1500
        assert d["watchers"] == 500
        assert d["open_issues"] == 120
        assert d["language"] == "Python"
        assert d["created_at"] == datetime(2020, 1, 15)
        assert d["updated_at"] == datetime(2025, 1, 20)
        assert d["recent_commits"] == 150

    def test_github_repo_metrics_full_name(self):
        """Test GitHubRepoMetrics full_name property."""
        metrics = GitHubRepoMetrics(
            owner="openai",
            repo="openai-python",
            stars=10000,
            forks=1500,
            watchers=500,
            open_issues=120,
            language="Python",
            created_at=datetime(2020, 1, 15),
            updated_at=datetime(2025, 1, 20),
            recent_commits=150,
        )

        assert metrics.full_name == "openai/openai-python"


class TestGitHubCollectorProperties:
    """Tests for GitHubCollector properties."""

    @pytest.fixture
    def collector(self):
        """Create collector instance."""
        return GitHubCollector()

    def test_name_property(self, collector):
        """Test that name property returns 'github_collector'."""
        assert collector.name == "github_collector"

    def test_source_property(self, collector):
        """Test that source property returns 'github'."""
        assert collector.source == "github"

    def test_tracked_repos_default(self, collector):
        """Test that tracked_repos contains default repos."""
        expected_repos = [
            "openai/openai-python",
            "huggingface/transformers",
            "pytorch/pytorch",
            "langchain-ai/langchain",
            "microsoft/vscode",
        ]
        assert all(repo in collector.tracked_repos for repo in expected_repos)

    def test_custom_tracked_repos(self):
        """Test that collector accepts custom tracked repos."""
        custom_repos = ["custom/repo1", "custom/repo2"]
        collector = GitHubCollector(tracked_repos=custom_repos)
        assert collector.tracked_repos == custom_repos


class TestGitHubCollectorFetchRepoMetrics:
    """Tests for GitHubCollector fetch_repo_metrics method."""

    @pytest.fixture
    def collector(self):
        """Create collector instance."""
        return GitHubCollector()

    @pytest.fixture
    def mock_repo_response(self):
        """Create mock GitHub repo API response."""
        return {
            "id": 12345,
            "name": "openai-python",
            "full_name": "openai/openai-python",
            "owner": {"login": "openai"},
            "stargazers_count": 10000,
            "forks_count": 1500,
            "subscribers_count": 500,
            "open_issues_count": 120,
            "language": "Python",
            "created_at": "2020-01-15T00:00:00Z",
            "updated_at": "2025-01-20T00:00:00Z",
        }

    @pytest.fixture
    def mock_commit_activity_response(self):
        """Create mock GitHub commit activity API response.

        Returns last 52 weeks of commit activity, we only use last 4 weeks.
        """
        # Create 52 weeks of activity, with last 4 weeks having 10, 20, 30, 40 commits
        activity = [{"week": 1600000000 + i * 604800, "total": 5, "days": [1, 0, 1, 1, 0, 1, 1]} for i in range(48)]
        activity.extend([
            {"week": 1600000000 + 48 * 604800, "total": 10, "days": [1, 2, 3, 1, 1, 1, 1]},
            {"week": 1600000000 + 49 * 604800, "total": 20, "days": [2, 3, 4, 3, 3, 3, 2]},
            {"week": 1600000000 + 50 * 604800, "total": 30, "days": [4, 5, 5, 4, 4, 4, 4]},
            {"week": 1600000000 + 51 * 604800, "total": 40, "days": [5, 6, 6, 6, 5, 6, 6]},
        ])
        return activity

    @pytest.mark.asyncio
    async def test_fetch_repo_metrics_returns_metrics(self, collector, mock_repo_response, mock_commit_activity_response):
        """Test that fetch_repo_metrics returns GitHubRepoMetrics object."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.raise_for_status = Mock()

        def json_side_effect():
            # This will be called twice - once for repo, once for commit activity
            return mock_response._current_json

        mock_response.json = json_side_effect

        async def mock_get(url, **kwargs):
            if "/stats/commit_activity" in url:
                mock_response._current_json = mock_commit_activity_response
            else:
                mock_response._current_json = mock_repo_response
            return mock_response

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_client.return_value)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value.get = AsyncMock(side_effect=mock_get)

            metrics = await collector.fetch_repo_metrics("openai", "openai-python")

            assert metrics is not None
            assert isinstance(metrics, GitHubRepoMetrics)
            assert metrics.owner == "openai"
            assert metrics.repo == "openai-python"
            assert metrics.stars == 10000
            assert metrics.forks == 1500
            assert metrics.watchers == 500
            assert metrics.open_issues == 120
            assert metrics.language == "Python"
            assert metrics.recent_commits == 100  # 10 + 20 + 30 + 40

    @pytest.mark.asyncio
    async def test_fetch_repo_metrics_handles_missing_commit_activity(self, collector, mock_repo_response):
        """Test that fetch_repo_metrics handles missing commit activity gracefully."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.raise_for_status = Mock()

        call_count = 0

        async def mock_get(url, **kwargs):
            nonlocal call_count
            call_count += 1
            if "/stats/commit_activity" in url:
                # Return empty list for commit activity (can happen for new repos)
                mock_response.json = lambda: []
            else:
                mock_response.json = lambda: mock_repo_response
            return mock_response

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_client.return_value)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value.get = AsyncMock(side_effect=mock_get)

            metrics = await collector.fetch_repo_metrics("openai", "openai-python")

            assert metrics is not None
            assert metrics.recent_commits == 0

    @pytest.mark.asyncio
    async def test_fetch_repo_metrics_returns_none_on_http_error(self, collector):
        """Test that fetch_repo_metrics returns None on HTTP error."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_client.return_value)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value.get = AsyncMock(
                side_effect=httpx.HTTPStatusError(
                    "Not Found",
                    request=Mock(),
                    response=Mock(status_code=404),
                )
            )

            metrics = await collector.fetch_repo_metrics("nonexistent", "repo")

            assert metrics is None

    @pytest.mark.asyncio
    async def test_fetch_repo_metrics_returns_none_on_network_error(self, collector):
        """Test that fetch_repo_metrics returns None on network error."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_client.return_value)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value.get = AsyncMock(
                side_effect=httpx.RequestError("Network error")
            )

            metrics = await collector.fetch_repo_metrics("openai", "openai-python")

            assert metrics is None

    @pytest.mark.asyncio
    async def test_fetch_repo_metrics_correct_api_urls(self, collector, mock_repo_response, mock_commit_activity_response):
        """Test that fetch_repo_metrics uses correct GitHub API URLs."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.raise_for_status = Mock()

        called_urls = []

        async def mock_get(url, **kwargs):
            called_urls.append(url)
            if "/stats/commit_activity" in url:
                mock_response.json = lambda: mock_commit_activity_response
            else:
                mock_response.json = lambda: mock_repo_response
            return mock_response

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_client.return_value)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value.get = AsyncMock(side_effect=mock_get)

            await collector.fetch_repo_metrics("openai", "openai-python")

            assert "https://api.github.com/repos/openai/openai-python" in called_urls
            assert "https://api.github.com/repos/openai/openai-python/stats/commit_activity" in called_urls


class TestGitHubCollectorFetchAllTrackedRepos:
    """Tests for GitHubCollector fetch_all_tracked_repos method."""

    @pytest.fixture
    def collector(self):
        """Create collector instance with custom repos."""
        return GitHubCollector(tracked_repos=["openai/openai-python", "pytorch/pytorch"])

    @pytest.fixture
    def mock_repo_response_factory(self):
        """Factory to create mock repo responses."""
        def create_response(owner, repo, stars):
            return {
                "id": 12345,
                "name": repo,
                "full_name": f"{owner}/{repo}",
                "owner": {"login": owner},
                "stargazers_count": stars,
                "forks_count": 100,
                "subscribers_count": 50,
                "open_issues_count": 10,
                "language": "Python",
                "created_at": "2020-01-15T00:00:00Z",
                "updated_at": "2025-01-20T00:00:00Z",
            }
        return create_response

    @pytest.fixture
    def mock_commit_activity_response(self):
        """Create mock commit activity response."""
        return [{"week": 1600000000 + i * 604800, "total": 5, "days": [1, 0, 1, 1, 0, 1, 1]} for i in range(4)]

    @pytest.mark.asyncio
    async def test_fetch_all_tracked_repos_returns_dict(self, collector, mock_repo_response_factory, mock_commit_activity_response):
        """Test that fetch_all_tracked_repos returns dictionary mapping repo to metrics."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.raise_for_status = Mock()

        async def mock_get(url, **kwargs):
            if "/stats/commit_activity" in url:
                mock_response.json = lambda: mock_commit_activity_response
            elif "openai/openai-python" in url:
                mock_response.json = lambda: mock_repo_response_factory("openai", "openai-python", 10000)
            elif "pytorch/pytorch" in url:
                mock_response.json = lambda: mock_repo_response_factory("pytorch", "pytorch", 80000)
            return mock_response

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_client.return_value)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value.get = AsyncMock(side_effect=mock_get)

            result = await collector.fetch_all_tracked_repos()

            assert isinstance(result, dict)
            assert "openai/openai-python" in result
            assert "pytorch/pytorch" in result
            assert isinstance(result["openai/openai-python"], GitHubRepoMetrics)
            assert result["openai/openai-python"].stars == 10000
            assert result["pytorch/pytorch"].stars == 80000

    @pytest.mark.asyncio
    async def test_fetch_all_tracked_repos_handles_partial_failures(self, collector, mock_repo_response_factory, mock_commit_activity_response):
        """Test that fetch_all_tracked_repos handles partial failures gracefully."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.raise_for_status = Mock()

        call_count = 0

        async def mock_get(url, **kwargs):
            nonlocal call_count
            call_count += 1
            if "pytorch/pytorch" in url and "/stats/commit_activity" not in url:
                raise httpx.HTTPStatusError(
                    "Not Found",
                    request=Mock(),
                    response=Mock(status_code=404),
                )
            elif "/stats/commit_activity" in url:
                mock_response.json = lambda: mock_commit_activity_response
            else:
                mock_response.json = lambda: mock_repo_response_factory("openai", "openai-python", 10000)
            return mock_response

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_client.return_value)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value.get = AsyncMock(side_effect=mock_get)

            result = await collector.fetch_all_tracked_repos()

            # Should still have the successful repo
            assert "openai/openai-python" in result
            # Failed repo should be None or not in result
            assert result.get("pytorch/pytorch") is None

    @pytest.mark.asyncio
    async def test_fetch_all_tracked_repos_with_custom_repos(self, mock_repo_response_factory, mock_commit_activity_response):
        """Test that fetch_all_tracked_repos works with custom repo list."""
        custom_repos = ["custom/repo1", "custom/repo2"]
        collector = GitHubCollector(tracked_repos=custom_repos)

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.raise_for_status = Mock()

        async def mock_get(url, **kwargs):
            if "/stats/commit_activity" in url:
                mock_response.json = lambda: mock_commit_activity_response
            elif "custom/repo1" in url:
                mock_response.json = lambda: mock_repo_response_factory("custom", "repo1", 100)
            elif "custom/repo2" in url:
                mock_response.json = lambda: mock_repo_response_factory("custom", "repo2", 200)
            return mock_response

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_client.return_value)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value.get = AsyncMock(side_effect=mock_get)

            result = await collector.fetch_all_tracked_repos()

            assert len(result) == 2
            assert "custom/repo1" in result
            assert "custom/repo2" in result


class TestGitHubCollectorGetTrendingRepos:
    """Tests for GitHubCollector get_trending_repos method."""

    def test_get_trending_repos_sorts_by_stars(self):
        """Test that get_trending_repos sorts repos by star count descending."""
        collector = GitHubCollector()

        # Create mock metrics with different star counts
        metrics = {
            "repo1": GitHubRepoMetrics(
                owner="a", repo="repo1", stars=1000, forks=100, watchers=50,
                open_issues=10, language="Python", created_at=datetime(2020, 1, 1),
                updated_at=datetime(2025, 1, 1), recent_commits=50
            ),
            "repo2": GitHubRepoMetrics(
                owner="b", repo="repo2", stars=5000, forks=200, watchers=100,
                open_issues=20, language="Python", created_at=datetime(2020, 1, 1),
                updated_at=datetime(2025, 1, 1), recent_commits=100
            ),
            "repo3": GitHubRepoMetrics(
                owner="c", repo="repo3", stars=3000, forks=150, watchers=75,
                open_issues=15, language="Python", created_at=datetime(2020, 1, 1),
                updated_at=datetime(2025, 1, 1), recent_commits=75
            ),
        }

        result = collector.get_trending_repos(metrics)

        assert len(result) == 3
        assert result[0].stars == 5000  # repo2 first
        assert result[1].stars == 3000  # repo3 second
        assert result[2].stars == 1000  # repo1 last

    def test_get_trending_repos_filters_none_values(self):
        """Test that get_trending_repos filters out None values."""
        collector = GitHubCollector()

        metrics = {
            "repo1": GitHubRepoMetrics(
                owner="a", repo="repo1", stars=1000, forks=100, watchers=50,
                open_issues=10, language="Python", created_at=datetime(2020, 1, 1),
                updated_at=datetime(2025, 1, 1), recent_commits=50
            ),
            "repo2": None,  # Failed to fetch
            "repo3": GitHubRepoMetrics(
                owner="c", repo="repo3", stars=3000, forks=150, watchers=75,
                open_issues=15, language="Python", created_at=datetime(2020, 1, 1),
                updated_at=datetime(2025, 1, 1), recent_commits=75
            ),
        }

        result = collector.get_trending_repos(metrics)

        assert len(result) == 2
        assert all(m is not None for m in result)

    def test_get_trending_repos_with_limit(self):
        """Test that get_trending_repos respects limit parameter."""
        collector = GitHubCollector()

        metrics = {
            f"repo{i}": GitHubRepoMetrics(
                owner="owner", repo=f"repo{i}", stars=i * 1000, forks=100, watchers=50,
                open_issues=10, language="Python", created_at=datetime(2020, 1, 1),
                updated_at=datetime(2025, 1, 1), recent_commits=50
            )
            for i in range(1, 6)
        }

        result = collector.get_trending_repos(metrics, limit=3)

        assert len(result) == 3
        assert result[0].stars == 5000
        assert result[1].stars == 4000
        assert result[2].stars == 3000

    def test_get_trending_repos_sort_by_recent_commits(self):
        """Test that get_trending_repos can sort by recent commits."""
        collector = GitHubCollector()

        metrics = {
            "repo1": GitHubRepoMetrics(
                owner="a", repo="repo1", stars=5000, forks=100, watchers=50,
                open_issues=10, language="Python", created_at=datetime(2020, 1, 1),
                updated_at=datetime(2025, 1, 1), recent_commits=10
            ),
            "repo2": GitHubRepoMetrics(
                owner="b", repo="repo2", stars=1000, forks=200, watchers=100,
                open_issues=20, language="Python", created_at=datetime(2020, 1, 1),
                updated_at=datetime(2025, 1, 1), recent_commits=100
            ),
            "repo3": GitHubRepoMetrics(
                owner="c", repo="repo3", stars=3000, forks=150, watchers=75,
                open_issues=15, language="Python", created_at=datetime(2020, 1, 1),
                updated_at=datetime(2025, 1, 1), recent_commits=50
            ),
        }

        result = collector.get_trending_repos(metrics, sort_by="recent_commits")

        assert len(result) == 3
        assert result[0].recent_commits == 100  # repo2 first
        assert result[1].recent_commits == 50   # repo3 second
        assert result[2].recent_commits == 10   # repo1 last

    def test_get_trending_repos_empty_dict(self):
        """Test that get_trending_repos handles empty input."""
        collector = GitHubCollector()
        result = collector.get_trending_repos({})
        assert result == []

    def test_get_trending_repos_all_none(self):
        """Test that get_trending_repos handles all None values."""
        collector = GitHubCollector()
        metrics = {"repo1": None, "repo2": None}
        result = collector.get_trending_repos(metrics)
        assert result == []


class TestGitHubCollectorRateLimiting:
    """Tests for GitHubCollector rate limiting awareness."""

    @pytest.fixture
    def collector(self):
        """Create collector instance."""
        return GitHubCollector()

    @pytest.mark.asyncio
    async def test_handles_rate_limit_error(self, collector):
        """Test that collector handles 403 rate limit error gracefully."""
        mock_response = Mock()
        mock_response.status_code = 403
        mock_response.headers = {"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": "1700000000"}

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_client.return_value)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value.get = AsyncMock(
                side_effect=httpx.HTTPStatusError(
                    "Rate limited",
                    request=Mock(),
                    response=mock_response,
                )
            )

            metrics = await collector.fetch_repo_metrics("openai", "openai-python")

            # Should return None gracefully without crashing
            assert metrics is None

    @pytest.mark.asyncio
    async def test_handles_timeout_error(self, collector):
        """Test that collector handles timeout errors gracefully."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_client.return_value)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value.get = AsyncMock(
                side_effect=httpx.TimeoutException("Request timed out")
            )

            metrics = await collector.fetch_repo_metrics("openai", "openai-python")

            assert metrics is None

    def test_rate_limit_info_property(self, collector):
        """Test that collector has rate_limit_info property."""
        info = collector.rate_limit_info

        assert info is not None
        assert "requests_per_hour" in info
        assert info["requests_per_hour"] == 60  # Unauthenticated limit
        assert "authenticated" in info
        assert info["authenticated"] is False

    @pytest.mark.asyncio
    async def test_handles_invalid_json_response(self, collector):
        """Test that collector handles invalid JSON response gracefully."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.raise_for_status = Mock()
        mock_response.json = Mock(side_effect=ValueError("Invalid JSON"))

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_client.return_value)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value.get = AsyncMock(return_value=mock_response)

            metrics = await collector.fetch_repo_metrics("openai", "openai-python")

            assert metrics is None

    @pytest.mark.asyncio
    async def test_handles_missing_required_fields(self, collector):
        """Test that collector handles missing required fields gracefully."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.raise_for_status = Mock()

        # Missing created_at and updated_at which are required
        incomplete_data = {
            "id": 12345,
            "name": "test-repo",
            "stargazers_count": 100,
        }

        async def mock_get(url, **kwargs):
            if "/stats/commit_activity" in url:
                mock_response.json = lambda: []
            else:
                mock_response.json = lambda: incomplete_data
            return mock_response

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_client.return_value)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value.get = AsyncMock(side_effect=mock_get)

            metrics = await collector.fetch_repo_metrics("openai", "openai-python")

            # Should return None due to missing required fields
            assert metrics is None
