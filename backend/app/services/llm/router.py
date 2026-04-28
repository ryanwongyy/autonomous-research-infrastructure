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
    # Prefer Google → OpenAI → Anthropic for judging (the first two avoid
    # self-preference bias against Claude-generated papers; Anthropic is
    # the last-resort fallback when only that key is configured).
    if settings.google_api_key:
        model = settings.google_main_model
    elif settings.openai_api_key:
        model = settings.openai_main_model
    else:
        model = settings.claude_sonnet_model
    provider = get_provider_for_model(model)
    return provider, model


async def get_generation_provider() -> tuple[LLMProvider, str]:
    """Get the provider and model for paper generation."""
    model = settings.claude_opus_model
    provider = get_provider_for_model(model)
    return provider, model


async def get_review_provider(stage: str) -> tuple[LLMProvider, str]:
    """Get the provider and model for a specific review stage.

    The 5-layer pipeline stages (l1-l5) are mapped here alongside the
    legacy 6-stage names for backward compatibility.
    """
    stage_models = {
        # Legacy 6-stage pipeline (deprecated)
        "advisor": settings.openai_main_model,
        "theory": settings.openai_reasoning_model,
        "exhibit": settings.claude_sonnet_model,
        "prose": settings.claude_sonnet_model,
        "referee": settings.openai_main_model,
        "revision": settings.claude_opus_model,
        # 5-layer pipeline
        "l1_structural": "system",  # No LLM needed
        "l2_provenance": "system",  # No LLM needed
        "l3_method": settings.judge_non_claude_model,  # MUST be non-Claude
        "l4_adversarial_claude": settings.claude_sonnet_model,
        "l4_adversarial_gpt": settings.openai_main_model,
        "l5_human": "system",  # No LLM needed
    }
    model = stage_models.get(stage, settings.openai_main_model)
    provider = get_provider_for_model(model)
    return provider, model
