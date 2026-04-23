"""Mock chat source — emits canned messages on a timer so the rest of the
pipeline can be exercised end-to-end without any real platform credentials.
"""

from __future__ import annotations

import asyncio
import random

from .base import ChatSource
from ..types import ChatMessage, Platform


_SAMPLE = [
    ("nova_42", "yo what's your favorite game right now?"),
    ("midnight_dev", "is this an AI streamer? lol"),
    ("kira", "say hi to my cat please"),
    ("zeke", "drop a hot take on vibe coding"),
    ("astra", "what's the best open source LLM in 2026?"),
    ("pixelmage", "do you sleep?"),
    ("juno", "how do you stay live 24/7?"),
]


class MockChat(ChatSource):
    name = "mock"

    async def run(self, out_q):
        interval = float(self.config.get("interval_seconds", 6))
        while True:
            await asyncio.sleep(interval)
            user, text = random.choice(_SAMPLE)
            await out_q.put(ChatMessage.new(Platform.LOCAL, user, text))
