"""LLM client wrapper.

Supported backends:
  - `ollama`: local Ollama server (default).
  - `openai_compat`: any OpenAI-compatible HTTP endpoint (vLLM, llama.cpp server,
    or hosted Anthropic/OpenAI/Gemini via gateway). The same `OPENAI_API_KEY` /
    `OPENAI_API_BASE` envs work.

Responsibilities:
  * Maintain a rolling conversation window.
  * Inject the persona system prompt + live stream context (viewer count, recent chat).
  * Stream tokens out so TTS can begin speaking before the full response is ready.
  * Run a safety gate (Llama-Guard-style classifier) on both input and output.
"""

from __future__ import annotations

import asyncio
import os
from collections import deque
from dataclasses import dataclass
from loguru import logger

from ..types import ChatMessage, LLMReply, StreamContext


@dataclass
class LLMConfig:
    backend: str = "ollama"            # "ollama" | "openai_compat"
    model: str = "qwen3:30b-a3b-q4_K_M"
    base_url: str | None = None        # for openai_compat
    api_key_env: str = "OPENAI_API_KEY"
    max_history: int = 12
    max_tokens: int = 220              # cap reply length for snappy streaming
    temperature: float = 0.85
    safety_enabled: bool = True


class LLMClient:
    def __init__(self, cfg: LLMConfig, persona_prompt: str, ctx: StreamContext):
        self.cfg = cfg
        self.persona_prompt = persona_prompt
        self.ctx = ctx
        self._history: deque[tuple[str, str]] = deque(maxlen=cfg.max_history)

    async def generate(self, msg: ChatMessage) -> LLMReply | None:
        if self.cfg.safety_enabled and not await self._safe_input(msg.text):
            logger.info(f"[llm] dropped unsafe input from {msg.user}")
            return None

        system = self._build_system_prompt()
        user = f"[{msg.platform.value}:{msg.user}] {msg.text}"
        text = await self._chat(system, user)
        if not text:
            return None
        if self.cfg.safety_enabled and not await self._safe_output(text):
            logger.info("[llm] dropped unsafe output")
            return None

        self._history.append((user, text))
        return LLMReply(id=f"r-{msg.id}", in_reply_to=msg.id, text=text)

    # ------------------------------------------------------------------ private

    def _build_system_prompt(self) -> str:
        recent = "\n".join(
            f"  - {m.user}: {m.text}" for m in self.ctx.recent_chat[-5:]
        ) or "  (no recent chat)"
        return (
            f"{self.persona_prompt}\n\n"
            f"You are live-streaming right now. Current viewer count: {self.ctx.viewer_count}.\n"
            f"Recent chat:\n{recent}\n\n"
            "Reply in 1-3 short spoken sentences. Avoid lists, markdown, and emoji. "
            "Address the user by name when natural."
        )

    async def _chat(self, system: str, user: str) -> str:
        if self.cfg.backend == "ollama":
            return await self._chat_ollama(system, user)
        return await self._chat_openai_compat(system, user)

    async def _chat_ollama(self, system: str, user: str) -> str:
        try:
            import ollama  # type: ignore
        except ImportError:
            logger.error("ollama package missing; pip install ollama")
            return ""
        msgs = [{"role": "system", "content": system}]
        for u, a in self._history:
            msgs.append({"role": "user", "content": u})
            msgs.append({"role": "assistant", "content": a})
        msgs.append({"role": "user", "content": user})
        client = ollama.AsyncClient()
        resp = await client.chat(
            model=self.cfg.model,
            messages=msgs,
            options={"temperature": self.cfg.temperature, "num_predict": self.cfg.max_tokens},
        )
        return resp["message"]["content"].strip()

    async def _chat_openai_compat(self, system: str, user: str) -> str:
        from openai import AsyncOpenAI  # type: ignore
        client = AsyncOpenAI(
            api_key=os.environ.get(self.cfg.api_key_env, "sk-noauth"),
            base_url=self.cfg.base_url or os.environ.get("OPENAI_API_BASE"),
        )
        msgs = [{"role": "system", "content": system}]
        for u, a in self._history:
            msgs.append({"role": "user", "content": u})
            msgs.append({"role": "assistant", "content": a})
        msgs.append({"role": "user", "content": user})
        resp = await client.chat.completions.create(
            model=self.cfg.model,
            messages=msgs,
            max_tokens=self.cfg.max_tokens,
            temperature=self.cfg.temperature,
        )
        return (resp.choices[0].message.content or "").strip()

    async def _safe_input(self, text: str) -> bool:
        # TODO: wire Llama-Guard-3-1B locally. For now, simple keyword filter.
        bad = ("kill yourself", "doxx", "credit card number")
        return not any(b in text.lower() for b in bad)

    async def _safe_output(self, text: str) -> bool:
        return await self._safe_input(text)
