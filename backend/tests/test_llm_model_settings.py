"""Tests for centralised LLM model-id settings.

Production cron was failing because the codebase hardcoded model ids
(``claude-opus-4-6``, ``claude-sonnet-4-6``, etc.) that don't exist
publicly. This file verifies that:

  * The settings expose a sensible default for every logical model slot
    (Opus / Sonnet / Haiku / OpenAI main / OpenAI reasoning /
    OpenAI fast / Judge non-Claude / Google main).
  * The router reads from settings, so an env-var override changes the
    resolved model name without code changes.
  * Review-pipeline modules (l3_method, l4_adversarial,
    advisor_review, referee_review) take their model ids from settings.
"""

from __future__ import annotations

import importlib

import pytest

from app.config import Settings, settings

# ── Settings exposure ────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "field",
    [
        "claude_opus_model",
        "claude_sonnet_model",
        "claude_haiku_model",
        "openai_main_model",
        "openai_reasoning_model",
        "openai_fast_model",
        "judge_non_claude_model",
        "google_main_model",
    ],
)
def test_setting_exists_and_is_nonempty(field):
    """Every logical model slot has a default; no slot starts empty."""
    fresh = Settings()
    value = getattr(fresh, field)
    assert isinstance(value, str)
    assert value, f"settings.{field} must not be empty by default"


def test_defaults_avoid_known_broken_names():
    """The previous code used `claude-opus-4-6` and `claude-sonnet-4-6`,
    neither of which existed publicly. New defaults must NOT use those
    exact strings."""
    fresh = Settings()
    bad_names = {"claude-opus-4-6", "claude-sonnet-4-6", "claude-haiku-4-6"}
    assert fresh.claude_opus_model not in bad_names
    assert fresh.claude_sonnet_model not in bad_names
    assert fresh.claude_haiku_model not in bad_names


def test_settings_overridable_via_env(monkeypatch):
    """Env-var override changes the resolved value (Pydantic Settings
    behaviour). The router reads from `settings.<>_model`, so the
    override propagates to runtime model selection."""
    monkeypatch.setenv("CLAUDE_OPUS_MODEL", "claude-opus-4-5-20250119")
    fresh = Settings()
    assert fresh.claude_opus_model == "claude-opus-4-5-20250119"


# ── Router reads from settings ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_generation_provider_uses_settings(monkeypatch):
    """`get_generation_provider()` resolves to whatever
    `settings.claude_opus_model` is at call time, not a hardcoded literal."""
    from app.services.llm import router as router_mod

    monkeypatch.setattr(
        "app.services.llm.router.settings.claude_opus_model",
        "claude-opus-4-5-test-suffix",
    )
    # Re-resolve through the live function so we hit the runtime path.
    _, model = await router_mod.get_generation_provider()
    assert model == "claude-opus-4-5-test-suffix"


@pytest.mark.asyncio
async def test_get_review_provider_l3_uses_judge_setting(monkeypatch):
    from app.services.llm import router as router_mod

    monkeypatch.setattr(
        "app.services.llm.router.settings.judge_non_claude_model",
        "gpt-4o-test",
    )
    _, model = await router_mod.get_review_provider("l3_method")
    assert model == "gpt-4o-test"


@pytest.mark.asyncio
async def test_get_review_provider_l4_claude_uses_sonnet_setting(monkeypatch):
    from app.services.llm import router as router_mod

    monkeypatch.setattr(
        "app.services.llm.router.settings.claude_sonnet_model",
        "claude-sonnet-4-5-test",
    )
    _, model = await router_mod.get_review_provider("l4_adversarial_claude")
    assert model == "claude-sonnet-4-5-test"


@pytest.mark.asyncio
async def test_get_judge_provider_falls_through_settings(monkeypatch):
    """Judge provider preference: Google → OpenAI → Anthropic. Each
    branch reads from the corresponding settings field."""
    from app.services.llm import router as router_mod

    # No google key, no openai key → falls back to claude_sonnet_model.
    monkeypatch.setattr("app.services.llm.router.settings.google_api_key", "")
    monkeypatch.setattr("app.services.llm.router.settings.openai_api_key", "")
    monkeypatch.setattr(
        "app.services.llm.router.settings.claude_sonnet_model",
        "claude-sonnet-4-5-test-fallback",
    )
    _, model = await router_mod.get_judge_provider()
    assert model == "claude-sonnet-4-5-test-fallback"


# ── Review-pipeline module constants ─────────────────────────────────────────


def test_l3_method_module_uses_judge_setting():
    """L3 imports settings.judge_non_claude_model at module load time, so
    its `METHOD_MODEL` constant must match settings (not a stale literal)."""
    from app.services.review_pipeline import l3_method

    # Re-import to capture any setting changes within this test process.
    importlib.reload(l3_method)
    assert settings.judge_non_claude_model == l3_method.METHOD_MODEL


def test_l4_adversarial_uses_sonnet_and_main_settings():
    from app.services.review_pipeline import l4_adversarial

    importlib.reload(l4_adversarial)
    assert settings.claude_sonnet_model == l4_adversarial.ADVERSARIAL_CLAUDE_MODEL
    assert settings.openai_main_model == l4_adversarial.ADVERSARIAL_GPT_MODEL


def test_advisor_review_models_are_settings_driven():
    from app.services.review_pipeline.advisor_review import _get_advisor_models

    models = _get_advisor_models()
    # First slot: openai_main_model. Second: claude_sonnet_model.
    # Third: openai_fast_model. Order matters — the existing review
    # logic depends on positional slots.
    assert models[0] == settings.openai_main_model
    assert models[1] == settings.claude_sonnet_model
    # When no Google key, _get_advisor_models returns 3 items.
    assert settings.openai_fast_model in models


def test_referee_review_models_are_settings_driven():
    from app.services.review_pipeline.referee_review import _get_referee_models

    models = _get_referee_models()
    assert models[0] == settings.openai_main_model
    assert models[1] == settings.claude_sonnet_model


# ── /api/v1/config/models endpoint ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_models_endpoint_reflects_settings(client):
    """`GET /api/v1/config/models` returns whatever settings says — useful
    for the frontend to display "currently routing to <X>"."""
    resp = await client.get("/api/v1/config/models")
    assert resp.status_code == 200
    body = resp.json()

    assert settings.claude_opus_model in body["providers"]["anthropic"]["models"]
    assert settings.openai_main_model in body["providers"]["openai"]["models"]
    assert settings.google_main_model in body["providers"]["google"]["models"]


# ── No hardcoded broken model ids in source ──────────────────────────────────


def test_no_hardcoded_broken_model_ids_in_source():
    """No file under app/ may contain the literal `claude-opus-4-6`,
    `claude-sonnet-4-6`, or `claude-haiku-4-6` outside of comments. Those
    names never existed publicly and silently 400'd every Scout call in
    production. Comments are allowed (they explain the historical bug).
    """
    import pathlib
    import re

    bad_literals = ["claude-opus-4-6", "claude-sonnet-4-6", "claude-haiku-4-6"]
    app_root = pathlib.Path(__file__).resolve().parent.parent / "app"
    assert app_root.is_dir(), f"app/ not found at {app_root}"

    offenders: list[tuple[str, int, str]] = []
    for py_file in app_root.rglob("*.py"):
        text = py_file.read_text(encoding="utf-8")
        for lineno, line in enumerate(text.splitlines(), start=1):
            stripped = line.lstrip()
            # Allow these literals to appear in comments — config.py and
            # domain_config.py reference them in explanatory notes.
            if stripped.startswith("#"):
                continue
            # Allow them in docstring lines too (best-effort: any line
            # whose only non-quote content is one of the bad literals
            # surrounded by backticks / quotes is documentation).
            doc_pattern = re.compile(r"^[\"' \t`]*claude-(opus|sonnet|haiku)-4-6")
            if doc_pattern.match(stripped):
                continue
            for bad in bad_literals:
                if bad in line:
                    offenders.append((str(py_file.relative_to(app_root.parent)), lineno, line.strip()))

    assert not offenders, (
        "Hardcoded broken model ids found in source. Replace with "
        "`settings.<>_model` lookups:\n"
        + "\n".join(f"  {f}:{n}: {ln}" for f, n, ln in offenders)
    )
