import asyncio
import base64
import logging

import anthropic

from app.config import settings
from app.services.llm.provider import _RETRYABLE_EXCEPTIONS, LLMProvider, _llm_retry

logger = logging.getLogger(__name__)

# Add Anthropic-specific transient errors to retryable set
_RETRYABLE_EXCEPTIONS += (
    anthropic.APIConnectionError,
    anthropic.RateLimitError,
    anthropic.InternalServerError,
)


class AnthropicProvider(LLMProvider):
    def __init__(self):
        self.client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    @_llm_retry()
    async def complete(
        self,
        messages: list[dict],
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> str:
        system_msg = None
        user_messages = []
        for msg in messages:
            if msg["role"] == "system":
                system_msg = msg["content"]
            else:
                user_messages.append(msg)

        kwargs = {
            "model": model,
            "messages": user_messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if system_msg:
            kwargs["system"] = system_msg

        async with asyncio.timeout(self.timeout_seconds):
            response = await self.client.messages.create(**kwargs)
        # Stash usage so tracked_complete() can record it. Anthropic returns
        # `usage.input_tokens` / `usage.output_tokens` on every call.
        self.last_usage = {
            "input_tokens": getattr(response.usage, "input_tokens", 0),
            "output_tokens": getattr(response.usage, "output_tokens", 0),
            "model": model,
        }
        return response.content[0].text

    @_llm_retry()
    async def complete_with_pdf(
        self,
        pdf_path: str,
        messages: list[dict],
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> str:
        with open(pdf_path, "rb") as f:
            pdf_data = base64.standard_b64encode(f.read()).decode("utf-8")

        system_msg = None
        user_content = []
        for msg in messages:
            if msg["role"] == "system":
                system_msg = msg["content"]
            elif msg["role"] == "user":
                user_content.append({"type": "text", "text": msg["content"]})

        user_content.insert(
            0,
            {
                "type": "document",
                "source": {
                    "type": "base64",
                    "media_type": "application/pdf",
                    "data": pdf_data,
                },
            },
        )

        kwargs = {
            "model": model,
            "messages": [{"role": "user", "content": user_content}],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if system_msg:
            kwargs["system"] = system_msg

        async with asyncio.timeout(self.timeout_seconds):
            response = await self.client.messages.create(**kwargs)
        self.last_usage = {
            "input_tokens": getattr(response.usage, "input_tokens", 0),
            "output_tokens": getattr(response.usage, "output_tokens", 0),
            "model": model,
        }
        return response.content[0].text
