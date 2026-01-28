"""Tests for LLM Client Service."""
import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from src.services.llm_client import LLMClient, LLMError, ModelChoice


class TestModelChoice:
    def test_quality_model(self):
        assert ModelChoice.QUALITY == "claude-4.5-opus"

    def test_fast_model(self):
        assert ModelChoice.FAST == "gemini-2.5-flash"


def _make_sse_response(content: str, model: str = "gemini-2.5-flash") -> str:
    """Build a fake SSE response body."""
    data = {
        "type": "response",
        "data": {
            "id": "chatcmpl-test123",
            "object": "chat.completion",
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": content},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
        },
    }
    return f"data: {json.dumps(data)}\n\ndata: [DONE]\n"


@pytest.fixture
def client():
    with patch("src.services.llm_client.get_settings") as mock_settings:
        settings = MagicMock()
        settings.llm_base_url = "https://test.example.com/v1"
        settings.llm_api_key = "sk-test-key"
        mock_settings.return_value = settings
        yield LLMClient()


class TestLLMClientInit:
    def test_default_model(self, client):
        assert client.default_model == ModelChoice.FAST

    def test_custom_model(self):
        with patch("src.services.llm_client.get_settings") as mock_settings:
            settings = MagicMock()
            settings.llm_base_url = "https://test.example.com/v1"
            settings.llm_api_key = "sk-test"
            mock_settings.return_value = settings
            c = LLMClient(model=ModelChoice.QUALITY)
            assert c.default_model == ModelChoice.QUALITY

    def test_base_url_trailing_slash_stripped(self):
        with patch("src.services.llm_client.get_settings") as mock_settings:
            settings = MagicMock()
            settings.llm_base_url = "https://test.example.com/v1/"
            settings.llm_api_key = "sk-test"
            mock_settings.return_value = settings
            c = LLMClient()
            assert c.base_url == "https://test.example.com/v1"


class TestParseSSEResponse:
    def test_parse_valid_response(self):
        raw = _make_sse_response("Hello world")
        assert LLMClient._parse_sse_response(raw) == "Hello world"

    def test_parse_skips_done(self):
        raw = "data: [DONE]\n"
        assert LLMClient._parse_sse_response(raw) == ""

    def test_parse_skips_empty_lines(self):
        raw = "\n\n" + _make_sse_response("test") + "\n\n"
        assert LLMClient._parse_sse_response(raw) == "test"

    def test_parse_invalid_json(self):
        raw = "data: {invalid json}\n\ndata: [DONE]\n"
        assert LLMClient._parse_sse_response(raw) == ""

    def test_parse_missing_content_key(self):
        raw = 'data: {"type": "response", "data": {"choices": []}}\n\ndata: [DONE]\n'
        assert LLMClient._parse_sse_response(raw) == ""

    def test_parse_multiline_content(self):
        content = "Line 1\nLine 2\nLine 3"
        raw = _make_sse_response(content)
        assert LLMClient._parse_sse_response(raw) == content


class TestChat:
    @pytest.mark.asyncio
    async def test_chat_success(self, client):
        sse_body = _make_sse_response("Hello!")
        mock_response = httpx.Response(200, text=sse_body, request=httpx.Request("POST", "https://test.example.com"))

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_response):
            result = await client.chat([{"role": "user", "content": "Hi"}])
            assert result == "Hello!"

    @pytest.mark.asyncio
    async def test_chat_uses_specified_model(self, client):
        sse_body = _make_sse_response("response")
        mock_response = httpx.Response(200, text=sse_body, request=httpx.Request("POST", "https://test.example.com"))

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_response) as mock_post:
            await client.chat([{"role": "user", "content": "Hi"}], model=ModelChoice.QUALITY)
            call_kwargs = mock_post.call_args
            assert call_kwargs[1]["json"]["model"] == ModelChoice.QUALITY

    @pytest.mark.asyncio
    async def test_chat_network_error(self, client):
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, side_effect=httpx.ConnectError("fail")):
            with pytest.raises(LLMError, match="Network error"):
                await client.chat([{"role": "user", "content": "Hi"}])

    @pytest.mark.asyncio
    async def test_chat_api_error(self, client):
        mock_response = httpx.Response(
            429, text="rate limited", request=httpx.Request("POST", "https://test.example.com")
        )
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_response):
            with pytest.raises(LLMError, match="API error 429"):
                await client.chat([{"role": "user", "content": "Hi"}])

    @pytest.mark.asyncio
    async def test_chat_empty_response(self, client):
        mock_response = httpx.Response(
            200, text="data: [DONE]\n", request=httpx.Request("POST", "https://test.example.com")
        )
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_response):
            with pytest.raises(LLMError, match="Empty response"):
                await client.chat([{"role": "user", "content": "Hi"}])


class TestChatWithSystem:
    @pytest.mark.asyncio
    async def test_chat_with_system(self, client):
        sse_body = _make_sse_response("analysis result")
        mock_response = httpx.Response(200, text=sse_body, request=httpx.Request("POST", "https://test.example.com"))

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_response) as mock_post:
            result = await client.chat_with_system("You are helpful", "Analyze this")
            assert result == "analysis result"
            messages = mock_post.call_args[1]["json"]["messages"]
            assert messages[0] == {"role": "system", "content": "You are helpful"}
            assert messages[1] == {"role": "user", "content": "Analyze this"}

    @pytest.mark.asyncio
    async def test_chat_with_system_custom_model(self, client):
        sse_body = _make_sse_response("deep analysis")
        mock_response = httpx.Response(200, text=sse_body, request=httpx.Request("POST", "https://test.example.com"))

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_response) as mock_post:
            await client.chat_with_system("sys", "msg", model=ModelChoice.QUALITY)
            assert mock_post.call_args[1]["json"]["model"] == ModelChoice.QUALITY
