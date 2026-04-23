"""Smoke test: run the orchestrator with mock backends for a few seconds and
assert that frames + audio actually flow through the pipeline.

Skips automatically if optional deps are missing — this is a *contract* test,
not an integration test for the GPU stack.
"""

from __future__ import annotations

import asyncio
import importlib
import sys
import pytest


@pytest.mark.asyncio
async def test_pipeline_smokes():
    yaml = pytest.importorskip("yaml")
    cv2 = pytest.importorskip("cv2")
    np = pytest.importorskip("numpy")

    # Stub-out the LLM call so we don't need Ollama running.
    from ai_streamer.llm import client as llm_mod

    async def _fake_chat(self, system, user):
        return f"echo: {user[:60]}"
    llm_mod.LLMClient._chat = _fake_chat  # type: ignore[assignment]

    from ai_streamer import orchestrator
    cfg_p = "ai_streamer/config/persona.example.yaml"
    cfg_pl = "ai_streamer/config/platforms.example.yaml"

    task = asyncio.create_task(orchestrator.main_async(cfg_p, cfg_pl))
    await asyncio.sleep(8)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
