from abc import ABC, abstractmethod
import logging

from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)

logger = logging.getLogger(__name__)

# Transient exceptions that should trigger a retry
_RETRYABLE_EXCEPTIONS = (
    TimeoutError,
    ConnectionError,
    OSError,
)


def _llm_retry():
    """Retry decorator for LLM API calls: 3 attempts, exponential backoff 2-30s."""
    return retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=2, max=30),
        retry=retry_if_exception_type(_RETRYABLE_EXCEPTIONS),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )


class LLMProvider(ABC):
    """Abstract base class for LLM provider adapters."""

    @property
    def timeout_seconds(self) -> int:
        """Per-LLM-call timeout, configured via settings.

        Default: 600s (10 min). Long generations (Analyst code 16K
        tokens, Drafter manuscript 32K tokens) can take 3-5 minutes
        at the model. Production run #25138168976 killed Analyst
        with TimeoutError under the old 120s default.
        """
        from app.config import settings

        return settings.llm_timeout_seconds

    @abstractmethod
    async def complete(
        self,
        messages: list[dict],
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> str:
        """Send a completion request and return the response text."""
        ...

    @abstractmethod
    async def complete_with_pdf(
        self,
        pdf_path: str,
        messages: list[dict],
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> str:
        """Send a completion request with a PDF file attachment."""
        ...
