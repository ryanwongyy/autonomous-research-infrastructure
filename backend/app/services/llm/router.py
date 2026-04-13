import logging

from app.services.llm.provider import LLMProvider
from app.services.llm.anthropic_provider import AnthropicProvider
from app.services.llm.openai_provider import OpenAIProvider
from app.services.llm.google_provider import GoogleProvider
from app.config import settings

logger = logging.getLogger(__name__)

PROVIDER_MAP = {
    "claude": "anthropic",
    "gpt": "openai",
    "o1": "openai",
    "o3": "openai",
    "gemini": "google",
}


def get_provider_for_model(model: str) -> LLMProvider:
    """Determine which provider to use based on model name prefix."""
    for prefix, provider_name in PROVIDER_MAP.items():
        if model.startswith(prefix):
            return _get_provider_instance(provider_name)

    # Default to Anthropic
    logger.warning("Unknown model prefix for '%s', defaulting to Anthropic", model)
    return _get_provider_instance("anthropic")


def _get_provider_instance(provider_name: str) -> LLMProvider:
    if provider_name == "anthropic":
        return AnthropicProvider()
    elif provider_name == "openai":
        return OpenAIProvider()
    elif provider_name == "google":
        return GoogleProvider()
    else:
        raise ValueError(f"Unknown provider: {provider_name}")


async def get_judge_provider() -> tuple[LLMProvider, str]:
    """Get the provider and model for tournament judging.

    Prefers a non-Anthropic model to avoid self-preference bias when judging
    Claude-generated papers. Falls back through providers based on available keys.
    """
    # Prefer OpenAI for judging (avoids self-preference bias with Claude-generated papers)
    # When Google API key is added, switch to "gemini-2.0-flash" for native PDF support
    if settings.google_api_key:
        model = "gemini-2.0-flash"
    elif settings.openai_api_key:
        model = "gpt-4o"
    else:
        model = "claude-sonnet-4-6"
    provider = get_provider_for_model(model)
    return provider, model


async def get_generation_provider() -> tuple[LLMProvider, str]:
    """Get the provider and model for paper generation."""
    model = "claude-opus-4-6"
    provider = get_provider_for_model(model)
    return provider, model


async def get_review_provider(stage: str) -> tuple[LLMProvider, str]:
    """Get the provider and model for a specific review stage.

    The 5-layer pipeline stages (l1-l5) are mapped here alongside the
    legacy 6-stage names for backward compatibility.
    """
    stage_models = {
        # Legacy 6-stage pipeline (deprecated)
        "advisor": "gpt-4o",
        "theory": "o1",
        "exhibit": "claude-sonnet-4-6",
        "prose": "claude-sonnet-4-6",
        "referee": "gpt-4o",
        "revision": "claude-opus-4-6",
        # 5-layer pipeline
        "l1_structural": "system",       # No LLM needed
        "l2_provenance": "system",       # No LLM needed
        "l3_method": "gpt-4o",           # MUST be non-Claude
        "l4_adversarial_claude": "claude-sonnet-4-6",
        "l4_adversarial_gpt": "gpt-4o",
        "l5_human": "system",            # No LLM needed
    }
    model = stage_models.get(stage, "gpt-4o")
    provider = get_provider_for_model(model)
    return provider, model
