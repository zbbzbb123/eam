"""HuggingFace Hub API collector for tracking AI model download trends."""
import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

# HuggingFace API base URL
HUGGINGFACE_API_BASE_URL = "https://huggingface.co/api"

# HTTP client timeout in seconds
HTTP_CLIENT_TIMEOUT = httpx.Timeout(30.0)

# Default tracked models
DEFAULT_TRACKED_MODELS = [
    "meta-llama/Llama-2-7b",
    "meta-llama/Llama-3.2-1B",
    "mistralai/Mistral-7B-v0.1",
    "stabilityai/stable-diffusion-xl-base-1.0",
    "openai/whisper-large-v3",
]


@dataclass
class HuggingFaceModelMetrics:
    """Data class for HuggingFace model metrics."""

    model_id: str
    downloads: int
    likes: int
    pipeline_tag: Optional[str]
    author: str
    last_modified: datetime
    tags: Optional[List[str]]

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "model_id": self.model_id,
            "downloads": self.downloads,
            "likes": self.likes,
            "pipeline_tag": self.pipeline_tag,
            "author": self.author,
            "last_modified": self.last_modified,
            "tags": self.tags,
        }


class HuggingFaceCollector:
    """Collector for HuggingFace model metrics."""

    def __init__(self, tracked_models: Optional[List[str]] = None):
        """Initialize the HuggingFace collector.

        Args:
            tracked_models: Optional list of models to track in 'author/model' format.
                           If None, uses default tracked models.
        """
        self._tracked_models = tracked_models if tracked_models is not None else DEFAULT_TRACKED_MODELS.copy()

    @property
    def name(self) -> str:
        """Return collector name."""
        return "huggingface_collector"

    @property
    def source(self) -> str:
        """Return data source name."""
        return "huggingface"

    @property
    def tracked_models(self) -> List[str]:
        """Return list of tracked models."""
        return self._tracked_models

    async def fetch_model_metrics(
        self,
        model_id: str,
    ) -> Optional[HuggingFaceModelMetrics]:
        """
        Fetch metrics for a single HuggingFace model.

        Args:
            model_id: Model ID in 'author/model' format (e.g., "meta-llama/Llama-2-7b")

        Returns:
            HuggingFaceModelMetrics object or None if not available

        Note:
            This method makes one API call to get model info.
            It handles errors gracefully and returns None on error.
        """
        try:
            model_url = f"{HUGGINGFACE_API_BASE_URL}/models/{model_id}"

            async with httpx.AsyncClient(timeout=HTTP_CLIENT_TIMEOUT) as client:
                response = await client.get(model_url)
                response.raise_for_status()
                data = response.json()

            # Parse last modified date
            last_modified_str = data.get("lastModified", "")
            if last_modified_str:
                # Handle ISO format with milliseconds
                last_modified = datetime.fromisoformat(last_modified_str.replace("Z", "+00:00"))
            else:
                last_modified = datetime.now()

            return HuggingFaceModelMetrics(
                model_id=data.get("id", model_id),
                downloads=data.get("downloads", 0),
                likes=data.get("likes", 0),
                pipeline_tag=data.get("pipeline_tag"),
                author=data.get("author", ""),
                last_modified=last_modified,
                tags=data.get("tags"),
            )

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error fetching HuggingFace model {model_id}: {e}")
            return None
        except httpx.RequestError as e:
            logger.error(f"Network error fetching HuggingFace model {model_id}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error fetching HuggingFace model {model_id}: {e}")
            return None

    async def fetch_all_tracked_models(
        self,
        models: Optional[List[str]] = None,
    ) -> Dict[str, Optional[HuggingFaceModelMetrics]]:
        """
        Fetch metrics for all tracked models.

        Args:
            models: Optional list of models to fetch in 'author/model' format.
                   If None, fetches all configured tracked models.

        Returns:
            Dictionary mapping model ID to HuggingFaceModelMetrics or None
            if that model failed to fetch.
        """
        if models is None:
            models = self._tracked_models

        # Fetch all models concurrently
        async def fetch_one(model_id: str) -> tuple[str, Optional[HuggingFaceModelMetrics]]:
            metrics = await self.fetch_model_metrics(model_id)
            return model_id, metrics

        tasks = [fetch_one(model_id) for model_id in models]
        results = await asyncio.gather(*tasks)

        return dict(results)

    def get_trending_models(
        self,
        metrics: Dict[str, Optional[HuggingFaceModelMetrics]],
        sort_by: str = "downloads",
        limit: Optional[int] = None,
    ) -> List[HuggingFaceModelMetrics]:
        """
        Get trending/hot models sorted by specified metric.

        Args:
            metrics: Dictionary mapping model ID to HuggingFaceModelMetrics
            sort_by: Field to sort by ("downloads" or "likes")
            limit: Optional limit on number of results

        Returns:
            List of HuggingFaceModelMetrics sorted by the specified field (descending)
        """
        # Filter out None values
        valid_metrics = [m for m in metrics.values() if m is not None]

        # Sort by specified field
        if sort_by == "likes":
            valid_metrics.sort(key=lambda m: m.likes, reverse=True)
        else:
            # Default to sorting by downloads
            valid_metrics.sort(key=lambda m: m.downloads, reverse=True)

        # Apply limit if specified
        if limit is not None:
            valid_metrics = valid_metrics[:limit]

        return valid_metrics
