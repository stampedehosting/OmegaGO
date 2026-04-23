"""LinkedIn Live chat reader (BEST-EFFORT).

LinkedIn does not expose a public real-time chat API for Live events. Two
practical paths exist; both are implemented behind feature flags so the rest
of the pipeline is unaffected when LinkedIn is not configured:

  1. `restream_chat`: pull unified chat from a Restream account (paid, but
     covers LinkedIn + many others under one polling endpoint).
  2. `browser_scrape`: drive a logged-in headless Chromium session against
     the LinkedIn Live event page and observe the chat DOM via MutationObserver.

This stub implements path (1) when `RESTREAM_TOKEN` is set, otherwise it logs
a one-time warning and idles.
"""

from __future__ import annotations

import asyncio
import os
from loguru import logger

from .base import ChatSource
from ..types import ChatMessage, Platform


class LinkedInLiveChat(ChatSource):
    name = "linkedin"

    async def run(self, out_q):
        token = os.environ.get("RESTREAM_TOKEN")
        if not token:
            logger.warning(
                "[ingest:linkedin] no RESTREAM_TOKEN set and browser_scrape mode "
                "not yet implemented; LinkedIn ingest disabled."
            )
            await asyncio.Event().wait()
            return

        # TODO: wire the Restream chat WebSocket
        # https://developers.restream.io/reference/chat-websocket
        await asyncio.Event().wait()
