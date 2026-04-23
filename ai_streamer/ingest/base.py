"""Base classes for chat ingestion sources.

Every platform adapter inherits ChatSource and implements `run(out_q)`,
pushing ChatMessage objects onto the shared queue.
"""

from __future__ import annotations

import abc
import asyncio
from loguru import logger

from ..types import ChatMessage


class ChatSource(abc.ABC):
    """Abstract chat source. One instance per (platform, channel)."""

    name: str = "base"

    def __init__(self, config: dict):
        self.config = config
        self._task: asyncio.Task | None = None

    @abc.abstractmethod
    async def run(self, out_q: "asyncio.Queue[ChatMessage]") -> None: ...

    def start(self, out_q: "asyncio.Queue[ChatMessage]") -> asyncio.Task:
        logger.info(f"[ingest:{self.name}] starting")
        self._task = asyncio.create_task(self._safe_run(out_q), name=f"ingest-{self.name}")
        return self._task

    async def _safe_run(self, out_q):
        backoff = 1
        while True:
            try:
                await self.run(out_q)
                return
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.exception(f"[ingest:{self.name}] crashed: {e}; restarting in {backoff}s")
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 60)


class Multiplexer:
    """Owns N ChatSource instances, fan-in to a single queue."""

    def __init__(self, sources: list[ChatSource]):
        self.sources = sources

    def start(self, out_q: "asyncio.Queue[ChatMessage]") -> list[asyncio.Task]:
        return [s.start(out_q) for s in self.sources]
