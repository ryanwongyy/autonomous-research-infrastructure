"""Regression test: LLM timeout must be generous enough for long
token-generating stages.

Background: production run #25138168976 finally got past every
connection-management bug and reached the Analyst stage. Analyst's
LLM call (max_tokens=16384 for code generation) hit a TimeoutError
inside ``anthropic_provider.complete()``::

    File ".../anthropic_provider.py", line 49, in complete
        async with asyncio.timeout(self.timeout_seconds):
    File ".../asyncio/timeouts.py", line 115, in __aexit__
        raise TimeoutError from exc_val
    TimeoutError

The hardcoded 120s timeout was too tight. Bumped to a configurable
``settings.llm_timeout_seconds`` defaulting to 600s. This test
locks in the contract.
"""

from __future__ import annotations

from app.config import settings
from app.services.llm.provider import LLMProvider


def test_llm_timeout_default_is_generous():
    """Default must be >= 300s so Analyst (16K tokens) and Drafter
    (32K tokens) can complete their LLM calls.
    """
    assert settings.llm_timeout_seconds >= 300, (
        f"settings.llm_timeout_seconds = {settings.llm_timeout_seconds} "
        f"is too short for long-token-generating stages. Analyst's "
        f"code-gen and Drafter's manuscript-gen need 3-5 minutes."
    )


def test_llm_timeout_is_configurable_via_settings():
    """LLMProvider's timeout_seconds property must read from settings,
    not from a hardcoded value, so operators can adjust without code
    changes.
    """

    class _StubProvider(LLMProvider):
        async def complete(self, *args, **kwargs):
            return ""

        async def complete_with_pdf(self, *args, **kwargs):
            return ""

    provider = _StubProvider()
    # The property should match settings exactly.
    assert provider.timeout_seconds == settings.llm_timeout_seconds, (
        "LLMProvider.timeout_seconds must be derived from settings."
    )
