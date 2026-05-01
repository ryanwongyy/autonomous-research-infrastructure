import asyncio
import base64
import logging

import httpx
import openai
from openai import AsyncOpenAI

from app.services.llm.provider import LLMProvider, _llm_retry, _RETRYABLE_EXCEPTIONS
from app.config import settings

logger = logging.getLogger(__name__)

# Add OpenAI-specific transient errors to retryable set. Use .extend()
# so the mutation reaches provider.py's list (see provider.py for the
# bug-history note on `+=`).
# httpx.TransportError covers raw transport failures the SDK doesn't
# wrap.
_RETRYABLE_EXCEPTIONS.extend([
    openai.APIConnectionError,
    openai.RateLimitError,
    openai.InternalServerError,
    httpx.TransportError,
])


class OpenAIProvider(LLMProvider):
    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)

    @_llm_retry()
    async def complete(
        self,
        messages: list[dict],
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> str:
        async with asyncio.timeout(self.timeout_seconds):
            response = await self.client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        return response.choices[0].message.content

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

        # Build messages with file attachment
        adapted_messages = []
        for msg in messages:
            if msg["role"] == "user":
                adapted_messages.append({
                    "role": "user",
                    "content": [
                        {
                            "type": "file",
                            "file": {
                                "filename": "paper.pdf",
                                "file_data": f"data:application/pdf;base64,{pdf_data}",
                            },
                        },
                        {"type": "text", "text": msg["content"]},
                    ],
                })
            else:
                adapted_messages.append(msg)

        async with asyncio.timeout(self.timeout_seconds):
            response = await self.client.chat.completions.create(
                model=model,
                messages=adapted_messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        return response.choices[0].message.content
