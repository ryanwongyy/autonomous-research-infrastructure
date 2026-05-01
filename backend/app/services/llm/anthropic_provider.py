import asyncio
import base64
import logging

import anthropic
import httpx

from app.config import settings
from app.services.llm.provider import _RETRYABLE_EXCEPTIONS, LLMProvider, _llm_retry

logger = logging.getLogger(__name__)

# Add Anthropic-specific transient errors to retryable set.
# Use ``.extend()`` (mutate in place) — earlier ``+=`` rebound the
# local name and the augmentation never reached the retry decorator.
# Bare httpx transport errors aren't always wrapped by the Anthropic
# SDK — production paper apep_53ebda2e (run 25212118657) died at the
# Drafter LLM call with a raw ``httpx.RemoteProtocolError: peer
# closed connection without sending complete message body (incomplete
# chunked read)``. ``httpx.TransportError`` is the parent of
# RemoteProtocolError / ReadError / ReadTimeout / ConnectError /
# ConnectTimeout / WriteError / WriteTimeout — every flavor of "the
# connection broke partway through".
_RETRYABLE_EXCEPTIONS.extend([
    anthropic.APIConnectionError,
    anthropic.RateLimitError,
    anthropic.InternalServerError,
    httpx.TransportError,
])


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

        # Use streaming for long generations. The Anthropic SDK refuses
        # non-streaming requests that it estimates may exceed 10 minutes
        # (raises ValueError on Drafter's 32K-token manuscripts —
        # production run #25139424603). Streaming has no such limit
        # and accumulates the same final text, so we can use it
        # unconditionally.
        async with asyncio.timeout(self.timeout_seconds):
            chunks: list[str] = []
            async with self.client.messages.stream(**kwargs) as stream:
                async for text in stream.text_stream:
                    chunks.append(text)
            return "".join(chunks)

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

        # Stream to avoid the SDK's >10-min non-streaming refusal.
        async with asyncio.timeout(self.timeout_seconds):
            chunks: list[str] = []
            async with self.client.messages.stream(**kwargs) as stream:
                async for text in stream.text_stream:
                    chunks.append(text)
            return "".join(chunks)
