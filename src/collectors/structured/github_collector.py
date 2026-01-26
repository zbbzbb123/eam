"""GitHub API collector for tracking open source project popularity."""
import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

# GitHub API base URL
GITHUB_API_BASE_URL = "https://api.github.com"

# HTTP client timeout in seconds
HTTP_CLIENT_TIMEOUT = httpx.Timeout(30.0)

# Number of weeks to consider for recent commit activity
RECENT_WEEKS = 4


@dataclass
class GitHubRepoMetrics:
    """Data class for GitHub repository metrics."""

    owner: str
    repo: str
    stars: int
    forks: int
    watchers: int
    open_issues: int
    language: Optional[str]
    created_at: datetime
    updated_at: datetime
    recent_commits: int

    @property
    def full_name(self) -> str:
        """Return full repository name in owner/repo format."""
        return f"{self.owner}/{self.repo}"

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "owner": self.owner,
            "repo": self.repo,
            "stars": self.stars,
            "forks": self.forks,
            "watchers": self.watchers,
            "open_issues": self.open_issues,
            "language": self.language,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "recent_commits": self.recent_commits,
        }


# Default tracked repositories
DEFAULT_TRACKED_REPOS = [
    "openai/openai-python",
    "huggingface/transformers",
    "pytorch/pytorch",
    "langchain-ai/langchain",
    "microsoft/vscode",
]


class GitHubCollector:
    """Collector for GitHub repository metrics."""

    def __init__(self, tracked_repos: Optional[List[str]] = None):
        """Initialize the GitHub collector.

        Args:
            tracked_repos: Optional list of repos to track in 'owner/repo' format.
                          If None, uses default tracked repos.
        """
        self._tracked_repos = tracked_repos if tracked_repos is not None else DEFAULT_TRACKED_REPOS.copy()

    @property
    def name(self) -> str:
        """Return collector name."""
        return "github_collector"

    @property
    def source(self) -> str:
        """Return data source name."""
        return "github"

    @property
    def tracked_repos(self) -> List[str]:
        """Return list of tracked repositories."""
        return self._tracked_repos

    @property
    def rate_limit_info(self) -> Dict[str, any]:
        """Return rate limit information for the GitHub API.

        GitHub API has different rate limits based on authentication:
        - Unauthenticated: 60 requests per hour
        - Authenticated: 5000 requests per hour

        Returns:
            Dictionary containing rate limit information
        """
        return {
            "requests_per_hour": 60,  # Unauthenticated limit
            "authenticated": False,
            "note": "GitHub API rate limit for unauthenticated requests is 60/hour",
        }

    async def fetch_repo_metrics(
        self,
        owner: str,
        repo: str,
    ) -> Optional[GitHubRepoMetrics]:
        """
        Fetch metrics for a single GitHub repository.

        Args:
            owner: Repository owner (e.g., "openai")
            repo: Repository name (e.g., "openai-python")

        Returns:
            GitHubRepoMetrics object or None if not available

        Note:
            This method makes two API calls: one for repo info and one for
            commit activity. It handles errors gracefully and returns None
            on error.
        """
        try:
            repo_url = f"{GITHUB_API_BASE_URL}/repos/{owner}/{repo}"
            commit_activity_url = f"{GITHUB_API_BASE_URL}/repos/{owner}/{repo}/stats/commit_activity"

            async with httpx.AsyncClient(timeout=HTTP_CLIENT_TIMEOUT) as client:
                # Fetch repo info
                repo_response = await client.get(repo_url)
                repo_response.raise_for_status()
                repo_data = repo_response.json()

                # Fetch commit activity
                activity_response = await client.get(commit_activity_url)
                activity_response.raise_for_status()
                activity_data = activity_response.json()

            # Calculate recent commits (last 4 weeks)
            recent_commits = 0
            if activity_data and isinstance(activity_data, list):
                # Activity data is sorted chronologically, get last RECENT_WEEKS entries
                recent_weeks = activity_data[-RECENT_WEEKS:] if len(activity_data) >= RECENT_WEEKS else activity_data
                recent_commits = sum(week.get("total", 0) for week in recent_weeks)

            # Parse dates
            created_at = datetime.fromisoformat(repo_data["created_at"].replace("Z", "+00:00"))
            updated_at = datetime.fromisoformat(repo_data["updated_at"].replace("Z", "+00:00"))

            return GitHubRepoMetrics(
                owner=owner,
                repo=repo,
                stars=repo_data.get("stargazers_count", 0),
                forks=repo_data.get("forks_count", 0),
                watchers=repo_data.get("subscribers_count", 0),
                open_issues=repo_data.get("open_issues_count", 0),
                language=repo_data.get("language"),
                created_at=created_at,
                updated_at=updated_at,
                recent_commits=recent_commits,
            )

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error fetching GitHub repo {owner}/{repo}: {e}")
            return None
        except httpx.RequestError as e:
            logger.error(f"Network error fetching GitHub repo {owner}/{repo}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error fetching GitHub repo {owner}/{repo}: {e}")
            return None

    async def fetch_all_tracked_repos(
        self,
        repos: Optional[List[str]] = None,
    ) -> Dict[str, Optional[GitHubRepoMetrics]]:
        """
        Fetch metrics for all tracked repositories.

        Args:
            repos: Optional list of repos to fetch in 'owner/repo' format.
                   If None, fetches all configured tracked repos.

        Returns:
            Dictionary mapping repo full name to GitHubRepoMetrics or None
            if that repo failed to fetch.
        """
        if repos is None:
            repos = self._tracked_repos

        # Fetch all repos concurrently
        async def fetch_one(repo_full_name: str) -> tuple[str, Optional[GitHubRepoMetrics]]:
            parts = repo_full_name.split("/")
            if len(parts) != 2:
                logger.error(f"Invalid repo format: {repo_full_name}")
                return repo_full_name, None
            owner, repo = parts
            metrics = await self.fetch_repo_metrics(owner, repo)
            return repo_full_name, metrics

        tasks = [fetch_one(repo) for repo in repos]
        results = await asyncio.gather(*tasks)

        return dict(results)

    def get_trending_repos(
        self,
        metrics: Dict[str, Optional[GitHubRepoMetrics]],
        sort_by: str = "stars",
        limit: Optional[int] = None,
    ) -> List[GitHubRepoMetrics]:
        """
        Get trending/hot repos sorted by specified metric.

        Args:
            metrics: Dictionary mapping repo name to GitHubRepoMetrics
            sort_by: Field to sort by ("stars" or "recent_commits")
            limit: Optional limit on number of results

        Returns:
            List of GitHubRepoMetrics sorted by the specified field (descending)
        """
        # Filter out None values
        valid_metrics = [m for m in metrics.values() if m is not None]

        # Sort by specified field
        if sort_by == "recent_commits":
            valid_metrics.sort(key=lambda m: m.recent_commits, reverse=True)
        else:
            # Default to sorting by stars
            valid_metrics.sort(key=lambda m: m.stars, reverse=True)

        # Apply limit if specified
        if limit is not None:
            valid_metrics = valid_metrics[:limit]

        return valid_metrics
