import logging
from abc import ABC, abstractmethod

from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

logger = logging.getLogger(__name__)

# Transient exceptions that should trigger a retry. Provider modules
# (anthropic_provider, openai_provider, google_provider) extend this
# list with their own SDK-specific transient errors at module-load
# time.
#
# IMPORTANT: this is a list, not a tuple. Earlier versions used
# ``_RETRYABLE_EXCEPTIONS = (...)`` and the providers did
# ``_RETRYABLE_EXCEPTIONS += (extra,)`` — but ``+=`` on a tuple
# REBINDS the local name in the provider's namespace rather than
# mutating provider.py's value, so the augmentation never reached
# the retry decorator. Production paper apep_53ebda2e (run
# 25212118657) demonstrated this: a bare httpx.RemoteProtocolError
# at the Drafter LLM call killed the paper because the retry set
# was still just (TimeoutError, ConnectionError, OSError).
#
# Using a list + ``.extend()`` mutates in place, and the retry
# decorator looks up the live list at retry-decision-time via
# retry_if_exception (not retry_if_exception_type, which captures
# the type tuple at decorator-construction time).
_RETRYABLE_EXCEPTIONS: list[type[BaseException]] = [
    TimeoutError,
    ConnectionError,
    OSError,
]


def _llm_retry():
    """Retry decorator for LLM API calls: 3 attempts, exponential backoff 2-30s."""
    return retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=2, max=30),
        # Evaluated at retry-decision-time so we pick up the live
        # value of _RETRYABLE_EXCEPTIONS (which providers extend at
        # module load).
        retry=retry_if_exception(lambda e: isinstance(e, tuple(_RETRYABLE_EXCEPTIONS))),
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
