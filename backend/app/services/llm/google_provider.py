import asyncio
import logging

from google import genai
from google.genai import types

from app.services.llm.provider import LLMProvider, _llm_retry
from app.config import settings

logger = logging.getLogger(__name__)


class GoogleProvider(LLMProvider):
    """Google Gemini provider with native PDF upload support."""

    def __init__(self):
        self.client = genai.Client(api_key=settings.google_api_key)

    @_llm_retry()
    async def complete(
        self,
        messages: list[dict],
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> str:
        system_instruction = None
        contents = []

        for msg in messages:
            if msg["role"] == "system":
                system_instruction = msg["content"]
            elif msg["role"] == "user":
                contents.append(types.Content(role="user", parts=[types.Part.from_text(msg["content"])]))
            elif msg["role"] == "assistant":
                contents.append(types.Content(role="model", parts=[types.Part.from_text(msg["content"])]))

        config = types.GenerateContentConfig(
            temperature=temperature,
            max_output_tokens=max_tokens,
            system_instruction=system_instruction,
        )

        async with asyncio.timeout(self.timeout_seconds):
            response = await self.client.aio.models.generate_content(
                model=model,
                contents=contents,
                config=config,
            )
        return response.text

    @_llm_retry()
    async def complete_with_pdf(
        self,
        pdf_path: str,
        messages: list[dict],
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> str:
        # Upload the PDF file
        uploaded_file = await self.client.aio.files.upload(file=pdf_path)

        system_instruction = None
        user_text = ""

        for msg in messages:
            if msg["role"] == "system":
                system_instruction = msg["content"]
            elif msg["role"] == "user":
                user_text += msg["content"] + "\n"

        contents = [
            types.Content(
                role="user",
                parts=[
                    types.Part.from_uri(file_uri=uploaded_file.uri, mime_type="application/pdf"),
                    types.Part.from_text(user_text),
                ],
            )
        ]

        config = types.GenerateContentConfig(
            temperature=temperature,
            max_output_tokens=max_tokens,
            system_instruction=system_instruction,
        )

        async with asyncio.timeout(self.timeout_seconds):
            response = await self.client.aio.models.generate_content(
                model=model,
                contents=contents,
                config=config,
            )
        return response.text
