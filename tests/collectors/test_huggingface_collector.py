"""Tests for HuggingFace collector."""
import pytest
from datetime import datetime
from unittest.mock import Mock, patch, AsyncMock

import httpx

from src.collectors.structured.huggingface_collector import (
    HuggingFaceCollector,
    HuggingFaceModelMetrics,
)


class TestHuggingFaceModelMetrics:
    """Tests for HuggingFaceModelMetrics dataclass."""

    def test_model_metrics_creation(self):
        """Test HuggingFaceModelMetrics can be created with required fields."""
        metrics = HuggingFaceModelMetrics(
            model_id="meta-llama/Llama-2-7b",
            downloads=1000000,
            likes=5000,
            pipeline_tag="text-generation",
            author="meta-llama",
            last_modified=datetime(2025, 1, 20),
            tags=["transformers", "pytorch", "llama"],
        )

        assert metrics.model_id == "meta-llama/Llama-2-7b"
        assert metrics.downloads == 1000000
        assert metrics.likes == 5000
        assert metrics.pipeline_tag == "text-generation"
        assert metrics.author == "meta-llama"
        assert metrics.last_modified == datetime(2025, 1, 20)
        assert metrics.tags == ["transformers", "pytorch", "llama"]

    def test_model_metrics_to_dict(self):
        """Test HuggingFaceModelMetrics to_dict method."""
        metrics = HuggingFaceModelMetrics(
            model_id="meta-llama/Llama-2-7b",
            downloads=1000000,
            likes=5000,
            pipeline_tag="text-generation",
            author="meta-llama",
            last_modified=datetime(2025, 1, 20),
            tags=["transformers", "pytorch"],
        )

        d = metrics.to_dict()

        assert d["model_id"] == "meta-llama/Llama-2-7b"
        assert d["downloads"] == 1000000
        assert d["likes"] == 5000
        assert d["pipeline_tag"] == "text-generation"
        assert d["author"] == "meta-llama"
        assert d["last_modified"] == datetime(2025, 1, 20)
        assert d["tags"] == ["transformers", "pytorch"]

    def test_model_metrics_with_optional_fields_none(self):
        """Test HuggingFaceModelMetrics with optional fields as None."""
        metrics = HuggingFaceModelMetrics(
            model_id="test/model",
            downloads=100,
            likes=10,
            pipeline_tag=None,
            author="test",
            last_modified=datetime(2025, 1, 1),
            tags=None,
        )

        assert metrics.pipeline_tag is None
        assert metrics.tags is None


class TestHuggingFaceCollectorProperties:
    """Tests for HuggingFaceCollector properties."""

    @pytest.fixture
    def collector(self):
        """Create collector instance."""
        return HuggingFaceCollector()

    def test_name_property(self, collector):
        """Test that name property returns 'huggingface_collector'."""
        assert collector.name == "huggingface_collector"

    def test_source_property(self, collector):
        """Test that source property returns 'huggingface'."""
        assert collector.source == "huggingface"

    def test_tracked_models_default(self, collector):
        """Test that tracked_models contains default models."""
        expected_models = [
            "meta-llama/Llama-2-7b",
            "meta-llama/Llama-3.2-1B",
            "mistralai/Mistral-7B-v0.1",
            "stabilityai/stable-diffusion-xl-base-1.0",
            "openai/whisper-large-v3",
        ]
        assert all(model in collector.tracked_models for model in expected_models)

    def test_custom_tracked_models(self):
        """Test that collector accepts custom tracked models."""
        custom_models = ["custom/model1", "custom/model2"]
        collector = HuggingFaceCollector(tracked_models=custom_models)
        assert collector.tracked_models == custom_models


class TestHuggingFaceCollectorFetchModelMetrics:
    """Tests for HuggingFaceCollector fetch_model_metrics method."""

    @pytest.fixture
    def collector(self):
        """Create collector instance."""
        return HuggingFaceCollector()

    @pytest.fixture
    def mock_model_response(self):
        """Create mock HuggingFace model API response."""
        return {
            "id": "meta-llama/Llama-2-7b",
            "modelId": "meta-llama/Llama-2-7b",
            "author": "meta-llama",
            "downloads": 1000000,
            "likes": 5000,
            "pipeline_tag": "text-generation",
            "tags": ["transformers", "pytorch", "llama", "text-generation"],
            "lastModified": "2025-01-20T12:00:00.000Z",
        }

    @pytest.mark.asyncio
    async def test_fetch_model_metrics_returns_metrics(self, collector, mock_model_response):
        """Test that fetch_model_metrics returns HuggingFaceModelMetrics object."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.raise_for_status = Mock()
        mock_response.json = lambda: mock_model_response

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_client.return_value)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value.get = AsyncMock(return_value=mock_response)

            metrics = await collector.fetch_model_metrics("meta-llama/Llama-2-7b")

            assert metrics is not None
            assert isinstance(metrics, HuggingFaceModelMetrics)
            assert metrics.model_id == "meta-llama/Llama-2-7b"
            assert metrics.downloads == 1000000
            assert metrics.likes == 5000
            assert metrics.pipeline_tag == "text-generation"
            assert metrics.author == "meta-llama"
            assert "transformers" in metrics.tags

    @pytest.mark.asyncio
    async def test_fetch_model_metrics_correct_api_url(self, collector, mock_model_response):
        """Test that fetch_model_metrics uses correct HuggingFace API URL."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.raise_for_status = Mock()
        mock_response.json = lambda: mock_model_response

        called_url = None

        async def mock_get(url, **kwargs):
            nonlocal called_url
            called_url = url
            return mock_response

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_client.return_value)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value.get = AsyncMock(side_effect=mock_get)

            await collector.fetch_model_metrics("meta-llama/Llama-2-7b")

            assert called_url == "https://huggingface.co/api/models/meta-llama/Llama-2-7b"

    @pytest.mark.asyncio
    async def test_fetch_model_metrics_returns_none_on_http_error(self, collector):
        """Test that fetch_model_metrics returns None on HTTP error."""
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

            metrics = await collector.fetch_model_metrics("nonexistent/model")

            assert metrics is None

    @pytest.mark.asyncio
    async def test_fetch_model_metrics_returns_none_on_network_error(self, collector):
        """Test that fetch_model_metrics returns None on network error."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_client.return_value)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value.get = AsyncMock(
                side_effect=httpx.RequestError("Network error")
            )

            metrics = await collector.fetch_model_metrics("meta-llama/Llama-2-7b")

            assert metrics is None

    @pytest.mark.asyncio
    async def test_fetch_model_metrics_handles_missing_optional_fields(self, collector):
        """Test that fetch_model_metrics handles missing optional fields gracefully."""
        mock_response_data = {
            "id": "test/model",
            "modelId": "test/model",
            "author": "test",
            "downloads": 100,
            "likes": 10,
            "lastModified": "2025-01-01T00:00:00.000Z",
            # pipeline_tag and tags are missing
        }

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.raise_for_status = Mock()
        mock_response.json = lambda: mock_response_data

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_client.return_value)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value.get = AsyncMock(return_value=mock_response)

            metrics = await collector.fetch_model_metrics("test/model")

            assert metrics is not None
            assert metrics.pipeline_tag is None
            assert metrics.tags is None


class TestHuggingFaceCollectorFetchAllTrackedModels:
    """Tests for HuggingFaceCollector fetch_all_tracked_models method."""

    @pytest.fixture
    def collector(self):
        """Create collector instance with custom models."""
        return HuggingFaceCollector(tracked_models=["meta-llama/Llama-2-7b", "mistralai/Mistral-7B-v0.1"])

    @pytest.fixture
    def mock_model_response_factory(self):
        """Factory to create mock model responses."""
        def create_response(model_id, downloads):
            author = model_id.split("/")[0]
            return {
                "id": model_id,
                "modelId": model_id,
                "author": author,
                "downloads": downloads,
                "likes": 100,
                "pipeline_tag": "text-generation",
                "tags": ["transformers", "pytorch"],
                "lastModified": "2025-01-20T00:00:00.000Z",
            }
        return create_response

    @pytest.mark.asyncio
    async def test_fetch_all_tracked_models_returns_dict(self, collector, mock_model_response_factory):
        """Test that fetch_all_tracked_models returns dictionary mapping model to metrics."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.raise_for_status = Mock()

        async def mock_get(url, **kwargs):
            if "Llama-2-7b" in url:
                mock_response.json = lambda: mock_model_response_factory("meta-llama/Llama-2-7b", 1000000)
            elif "Mistral-7B-v0.1" in url:
                mock_response.json = lambda: mock_model_response_factory("mistralai/Mistral-7B-v0.1", 500000)
            return mock_response

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_client.return_value)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value.get = AsyncMock(side_effect=mock_get)

            result = await collector.fetch_all_tracked_models()

            assert isinstance(result, dict)
            assert "meta-llama/Llama-2-7b" in result
            assert "mistralai/Mistral-7B-v0.1" in result
            assert isinstance(result["meta-llama/Llama-2-7b"], HuggingFaceModelMetrics)
            assert result["meta-llama/Llama-2-7b"].downloads == 1000000
            assert result["mistralai/Mistral-7B-v0.1"].downloads == 500000

    @pytest.mark.asyncio
    async def test_fetch_all_tracked_models_handles_partial_failures(self, collector, mock_model_response_factory):
        """Test that fetch_all_tracked_models handles partial failures gracefully."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.raise_for_status = Mock()

        async def mock_get(url, **kwargs):
            if "Mistral-7B-v0.1" in url:
                raise httpx.HTTPStatusError(
                    "Not Found",
                    request=Mock(),
                    response=Mock(status_code=404),
                )
            else:
                mock_response.json = lambda: mock_model_response_factory("meta-llama/Llama-2-7b", 1000000)
            return mock_response

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_client.return_value)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value.get = AsyncMock(side_effect=mock_get)

            result = await collector.fetch_all_tracked_models()

            # Should still have the successful model
            assert "meta-llama/Llama-2-7b" in result
            assert result["meta-llama/Llama-2-7b"] is not None
            # Failed model should be None
            assert result.get("mistralai/Mistral-7B-v0.1") is None

    @pytest.mark.asyncio
    async def test_fetch_all_tracked_models_with_custom_models(self, mock_model_response_factory):
        """Test that fetch_all_tracked_models works with custom model list."""
        custom_models = ["custom/model1", "custom/model2"]
        collector = HuggingFaceCollector(tracked_models=custom_models)

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.raise_for_status = Mock()

        async def mock_get(url, **kwargs):
            if "custom/model1" in url:
                mock_response.json = lambda: mock_model_response_factory("custom/model1", 100)
            elif "custom/model2" in url:
                mock_response.json = lambda: mock_model_response_factory("custom/model2", 200)
            return mock_response

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_client.return_value)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value.get = AsyncMock(side_effect=mock_get)

            result = await collector.fetch_all_tracked_models()

            assert len(result) == 2
            assert "custom/model1" in result
            assert "custom/model2" in result

    @pytest.mark.asyncio
    async def test_fetch_all_tracked_models_with_specific_models_param(self, collector, mock_model_response_factory):
        """Test that fetch_all_tracked_models accepts a models parameter to override tracked models."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.raise_for_status = Mock()

        async def mock_get(url, **kwargs):
            if "override/model" in url:
                mock_response.json = lambda: mock_model_response_factory("override/model", 999)
            return mock_response

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_client.return_value)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value.get = AsyncMock(side_effect=mock_get)

            result = await collector.fetch_all_tracked_models(models=["override/model"])

            assert len(result) == 1
            assert "override/model" in result


class TestHuggingFaceCollectorGetTrendingModels:
    """Tests for HuggingFaceCollector get_trending_models method."""

    def test_get_trending_models_sorts_by_downloads(self):
        """Test that get_trending_models sorts models by download count descending."""
        collector = HuggingFaceCollector()

        # Create mock metrics with different download counts
        metrics = {
            "model1": HuggingFaceModelMetrics(
                model_id="a/model1", downloads=1000, likes=10, pipeline_tag="text-generation",
                author="a", last_modified=datetime(2025, 1, 1), tags=["pytorch"]
            ),
            "model2": HuggingFaceModelMetrics(
                model_id="b/model2", downloads=5000, likes=50, pipeline_tag="text-generation",
                author="b", last_modified=datetime(2025, 1, 1), tags=["pytorch"]
            ),
            "model3": HuggingFaceModelMetrics(
                model_id="c/model3", downloads=3000, likes=30, pipeline_tag="text-generation",
                author="c", last_modified=datetime(2025, 1, 1), tags=["pytorch"]
            ),
        }

        result = collector.get_trending_models(metrics)

        assert len(result) == 3
        assert result[0].downloads == 5000  # model2 first
        assert result[1].downloads == 3000  # model3 second
        assert result[2].downloads == 1000  # model1 last

    def test_get_trending_models_filters_none_values(self):
        """Test that get_trending_models filters out None values."""
        collector = HuggingFaceCollector()

        metrics = {
            "model1": HuggingFaceModelMetrics(
                model_id="a/model1", downloads=1000, likes=10, pipeline_tag="text-generation",
                author="a", last_modified=datetime(2025, 1, 1), tags=["pytorch"]
            ),
            "model2": None,  # Failed to fetch
            "model3": HuggingFaceModelMetrics(
                model_id="c/model3", downloads=3000, likes=30, pipeline_tag="text-generation",
                author="c", last_modified=datetime(2025, 1, 1), tags=["pytorch"]
            ),
        }

        result = collector.get_trending_models(metrics)

        assert len(result) == 2
        assert all(m is not None for m in result)

    def test_get_trending_models_with_limit(self):
        """Test that get_trending_models respects limit parameter."""
        collector = HuggingFaceCollector()

        metrics = {
            f"model{i}": HuggingFaceModelMetrics(
                model_id=f"owner/model{i}", downloads=i * 1000, likes=i * 10,
                pipeline_tag="text-generation", author="owner",
                last_modified=datetime(2025, 1, 1), tags=["pytorch"]
            )
            for i in range(1, 6)
        }

        result = collector.get_trending_models(metrics, limit=3)

        assert len(result) == 3
        assert result[0].downloads == 5000
        assert result[1].downloads == 4000
        assert result[2].downloads == 3000

    def test_get_trending_models_sort_by_likes(self):
        """Test that get_trending_models can sort by likes count."""
        collector = HuggingFaceCollector()

        metrics = {
            "model1": HuggingFaceModelMetrics(
                model_id="a/model1", downloads=5000, likes=10, pipeline_tag="text-generation",
                author="a", last_modified=datetime(2025, 1, 1), tags=["pytorch"]
            ),
            "model2": HuggingFaceModelMetrics(
                model_id="b/model2", downloads=1000, likes=100, pipeline_tag="text-generation",
                author="b", last_modified=datetime(2025, 1, 1), tags=["pytorch"]
            ),
            "model3": HuggingFaceModelMetrics(
                model_id="c/model3", downloads=3000, likes=50, pipeline_tag="text-generation",
                author="c", last_modified=datetime(2025, 1, 1), tags=["pytorch"]
            ),
        }

        result = collector.get_trending_models(metrics, sort_by="likes")

        assert len(result) == 3
        assert result[0].likes == 100  # model2 first
        assert result[1].likes == 50   # model3 second
        assert result[2].likes == 10   # model1 last

    def test_get_trending_models_empty_dict(self):
        """Test that get_trending_models handles empty input."""
        collector = HuggingFaceCollector()
        result = collector.get_trending_models({})
        assert result == []

    def test_get_trending_models_all_none(self):
        """Test that get_trending_models handles all None values."""
        collector = HuggingFaceCollector()
        metrics = {"model1": None, "model2": None}
        result = collector.get_trending_models(metrics)
        assert result == []


class TestHuggingFaceCollectorErrorHandling:
    """Tests for HuggingFaceCollector error handling."""

    @pytest.fixture
    def collector(self):
        """Create collector instance."""
        return HuggingFaceCollector()

    @pytest.mark.asyncio
    async def test_handles_timeout_error(self, collector):
        """Test that collector handles timeout errors gracefully."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_client.return_value)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value.get = AsyncMock(
                side_effect=httpx.TimeoutException("Request timed out")
            )

            metrics = await collector.fetch_model_metrics("meta-llama/Llama-2-7b")

            assert metrics is None

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

            metrics = await collector.fetch_model_metrics("meta-llama/Llama-2-7b")

            assert metrics is None

    @pytest.mark.asyncio
    async def test_handles_missing_required_fields(self, collector):
        """Test that collector handles missing required fields gracefully."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.raise_for_status = Mock()

        # Missing author which is technically required
        incomplete_data = {
            "id": "test/model",
            "downloads": 100,
            "likes": 10,
            # Missing lastModified - will use default
        }
        mock_response.json = lambda: incomplete_data

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_client.return_value)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value.get = AsyncMock(return_value=mock_response)

            metrics = await collector.fetch_model_metrics("test/model")

            # Should still work with defaults for missing fields
            assert metrics is not None
            assert metrics.author == ""  # Default value
            assert metrics.pipeline_tag is None
            assert metrics.tags is None

    @pytest.mark.asyncio
    async def test_handles_rate_limit_error(self, collector):
        """Test that collector handles 429 rate limit error gracefully."""
        mock_response = Mock()
        mock_response.status_code = 429

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

            metrics = await collector.fetch_model_metrics("meta-llama/Llama-2-7b")

            # Should return None gracefully without crashing
            assert metrics is None

    @pytest.mark.asyncio
    async def test_handles_server_error(self, collector):
        """Test that collector handles 5xx server errors gracefully."""
        mock_response = Mock()
        mock_response.status_code = 500

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_client.return_value)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value.get = AsyncMock(
                side_effect=httpx.HTTPStatusError(
                    "Internal Server Error",
                    request=Mock(),
                    response=mock_response,
                )
            )

            metrics = await collector.fetch_model_metrics("meta-llama/Llama-2-7b")

            assert metrics is None

    @pytest.mark.asyncio
    async def test_handles_connection_error(self, collector):
        """Test that collector handles connection errors gracefully."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_client.return_value)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value.get = AsyncMock(
                side_effect=httpx.ConnectError("Connection refused")
            )

            metrics = await collector.fetch_model_metrics("meta-llama/Llama-2-7b")

            assert metrics is None

    @pytest.mark.asyncio
    async def test_handles_invalid_date_format(self, collector):
        """Test that collector handles invalid date format gracefully."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.raise_for_status = Mock()

        # Invalid date format
        invalid_data = {
            "id": "test/model",
            "modelId": "test/model",
            "author": "test",
            "downloads": 100,
            "likes": 10,
            "lastModified": "invalid-date-format",
        }
        mock_response.json = lambda: invalid_data

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_client.return_value)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value.get = AsyncMock(return_value=mock_response)

            # Should return None due to date parsing error
            metrics = await collector.fetch_model_metrics("test/model")

            assert metrics is None
