"""Regression test: /batch/generate must stream NDJSON to keep Render's
proxy from returning 502 on long-running requests.

Background: production run #25134915432 took 7m21s and hit a Render
proxy 502 because no bytes were flowing back to the client. Render's
HTTP proxy times out idle upstream connections at ~5-7 minutes.

The fix: stream an NDJSON response with a heartbeat line every ~15s
plus a final ``{"event":"result","data":{...}}`` line.

These tests guard the contract.
"""

from __future__ import annotations

import json

import pytest


@pytest.mark.asyncio
async def test_generate_endpoint_returns_ndjson_stream(client, monkeypatch):
    """Response is NDJSON; final line is ``{"event":"result","data":{...}}``."""

    async def fake_run_full_pipeline(*, family_id, paper_id, session=None, **_):
        return {
            "paper_id": paper_id,
            "family_id": family_id,
            "stages": {},
            "final_status": "completed",
            "total_duration_sec": 1.0,
        }

    async def fake_run_review_pipeline(session, paper_id):
        return {"decision": "pass"}

    async def fake_pick(_n: int) -> list[str]:
        return ["F_STREAM"]

    monkeypatch.setattr(
        "app.services.paper_generation.orchestrator.run_full_pipeline",
        fake_run_full_pipeline,
    )
    monkeypatch.setattr(
        "app.services.review_pipeline.orchestrator.run_review_pipeline",
        fake_run_review_pipeline,
    )
    monkeypatch.setattr(
        "app.api.batch._pick_underserved_families",
        fake_pick,
    )

    resp = await client.post(
        "/api/v1/batch/generate",
        json={"count": 1, "family_id": "F_STREAM"},
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/x-ndjson")

    # Body is one or more newline-terminated JSON objects.
    lines = [line for line in resp.text.strip().split("\n") if line]
    assert len(lines) >= 1, f"expected >=1 NDJSON line, got: {resp.text!r}"
    # Each line must be valid JSON.
    parsed = [json.loads(line) for line in lines]
    # Final line is always the result envelope.
    final = parsed[-1]
    assert final["event"] == "result"
    assert "data" in final
    assert "results" in final["data"]
    assert "summary" in final["data"]


@pytest.mark.asyncio
async def test_generate_endpoint_emits_error_envelope_on_inner_failure(client, monkeypatch):
    """If the inner work raises, the final stream line is an
    ``{"event":"error",...}`` envelope (not a 500 plus dropped body).

    This is what makes the curl side self-diagnosing — even when the
    pipeline itself blows up the client gets a structured payload.
    """
    # Make the inner work raise outside any try/except inside _do_batch_generate.
    monkeypatch.setattr(
        "app.api.batch._pick_underserved_families",
        _raise_runtime_error,
    )

    resp = await client.post(
        "/api/v1/batch/generate",
        json={"count": 1},
    )
    # Stream still completes with 200 — the error is in the body.
    assert resp.status_code == 200
    last_line = resp.text.strip().split("\n")[-1]
    payload = json.loads(last_line)
    assert payload["event"] == "error"
    assert "error_class" in payload
    assert payload["error_class"] == "RuntimeError"
    assert "deliberate failure" in payload["error_message"]


async def _raise_runtime_error(*args, **kwargs):
    raise RuntimeError("deliberate failure for test")
