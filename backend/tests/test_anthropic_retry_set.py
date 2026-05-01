"""Tests that the LLM retry set covers transient httpx transport errors.

Production paper apep_53ebda2e (autonomous-loop run 25212118657)
reached the Drafter stage successfully but the manuscript-generation
LLM call failed mid-stream:

  killed_at_drafter: RemoteProtocolError: peer closed connection
  without sending complete message body (incomplete chunked read)

This is a transient httpx error: Anthropic's API closed the streaming
connection before sending the complete response. Without retry, every
such event kills a paper that was otherwise on track.

The Anthropic provider's retry set covered ``APIConnectionError``,
``RateLimitError``, ``InternalServerError`` — these are SDK-level
exceptions the Anthropic library raises after wrapping HTTP errors.
But raw ``httpx.RemoteProtocolError`` from streamed-message reads
slips through unwrapped.

PR #64 adds ``httpx.TransportError`` (the parent of
RemoteProtocolError / ReadError / ReadTimeout / ConnectError /
ConnectTimeout / WriteError / WriteTimeout) to the retryable set.

This file locks in:
  * httpx.TransportError IS in the retryable set
  * httpx.RemoteProtocolError (the canonical case) IS retryable
  * Several other httpx subclasses are also retryable
  * Anthropic SDK exceptions remain retryable (regression guard)
"""

from __future__ import annotations

import anthropic
import httpx

# Importing anthropic_provider triggers the .extend() that registers
# its SDK-specific exceptions on _RETRYABLE_EXCEPTIONS. Without this
# import, the list contains only the original 3 base classes.
from app.services.llm import anthropic_provider as anthropic_provider_mod
from app.services.llm.provider import _RETRYABLE_EXCEPTIONS


def test_httpx_transport_error_is_retryable():
    """The parent class — covers everything below."""
    assert httpx.TransportError in _RETRYABLE_EXCEPTIONS, (
        "httpx.TransportError must be in the retryable set so transient "
        "network errors during the LLM call (e.g. RemoteProtocolError) "
        "trigger a retry instead of killing the paper."
    )


def test_httpx_remote_protocol_error_is_retryable():
    """Concrete subclass — production failure mode."""
    e = httpx.RemoteProtocolError("test")
    assert isinstance(e, tuple(_RETRYABLE_EXCEPTIONS)), (
        "httpx.RemoteProtocolError instance must satisfy isinstance check "
        "against _RETRYABLE_EXCEPTIONS — that's what tenacity's "
        "retry_if_exception_type does internally."
    )


def test_httpx_read_error_is_retryable():
    e = httpx.ReadError("test")
    assert isinstance(e, tuple(_RETRYABLE_EXCEPTIONS))


def test_httpx_connect_error_is_retryable():
    e = httpx.ConnectError("test")
    assert isinstance(e, tuple(_RETRYABLE_EXCEPTIONS))


def test_anthropic_api_connection_error_still_retryable():
    """Regression guard: don't accidentally drop the SDK-level exceptions
    when adding httpx.TransportError."""
    assert anthropic.APIConnectionError in _RETRYABLE_EXCEPTIONS


def test_anthropic_rate_limit_error_still_retryable():
    assert anthropic.RateLimitError in _RETRYABLE_EXCEPTIONS


def test_anthropic_internal_server_error_still_retryable():
    assert anthropic.InternalServerError in _RETRYABLE_EXCEPTIONS


def test_module_imports_clean():
    assert anthropic_provider_mod.AnthropicProvider is not None
