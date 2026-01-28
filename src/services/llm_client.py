"""LLM Client Service - OpenAI-compatible gateway."""
import json
import logging
from typing import List, Optional

import httpx

from src.config import get_settings

logger = logging.getLogger(__name__)


class ModelChoice:
    """Available model choices."""

    QUALITY = "claude-4.5-opus"  # For important analysis
    FAST = "gemini-2.5-flash"  # For summarization, simple tasks


class LLMError(Exception):
    """Base exception for LLM client errors."""


class LLMClient:
    """Unified LLM client supporting multiple models via OpenAI-compatible gateway."""

    def __init__(self, model: str = ModelChoice.FAST):
        self.default_model = model
        settings = get_settings()
        self.base_url = settings.llm_base_url.rstrip("/")
        self.api_key = settings.llm_api_key

    async def chat(
        self,
        messages: List[dict],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> str:
        """Send a chat completion request and return the content string.

        Args:
            messages: List of message dicts with 'role' and 'content'.
            model: Model to use, defaults to instance default.
            temperature: Sampling temperature.
            max_tokens: Maximum tokens in response.

        Returns:
            The assistant's response content as a string.

        Raises:
            LLMError: On network errors, API errors, or empty responses.
        """
        model = model or self.default_model
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise LLMError(f"API error {e.response.status_code}: {e.response.text}") from e
        except httpx.RequestError as e:
            raise LLMError(f"Network error: {e}") from e

        content = self._parse_sse_response(response.text)
        if not content:
            raise LLMError("Empty response from LLM")

        logger.info("LLM response: model=%s, content_length=%d", model, len(content))
        return content

    async def chat_with_system(
        self,
        system_prompt: str,
        user_message: str,
        model: Optional[str] = None,
    ) -> str:
        """Convenience method to chat with a system prompt.

        Args:
            system_prompt: The system prompt.
            user_message: The user message.
            model: Model to use.

        Returns:
            The assistant's response content.
        """
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]
        return await self.chat(messages, model=model)

    @staticmethod
    def _parse_sse_response(raw: str) -> str:
        """Parse SSE response and extract content.

        The API returns lines like:
            data: {"type": "response", "data": {"choices": [{"message": {"content": "..."}}]}}
            data: [DONE]
        """
        for line in raw.strip().splitlines():
            line = line.strip()
            if not line or not line.startswith("data: "):
                continue
            payload = line[len("data: "):]
            if payload == "[DONE]":
                continue
            try:
                parsed = json.loads(payload)
                content = parsed["data"]["choices"][0]["message"]["content"]
                return content
            except (json.JSONDecodeError, KeyError, IndexError) as e:
                logger.warning("Failed to parse SSE line: %s (%s)", line, e)
                continue
        return ""
