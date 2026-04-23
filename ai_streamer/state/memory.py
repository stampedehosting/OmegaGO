"""Lightweight persona/conversation memory.

For the scaffold we use an in-process dict + deque. The interface is small
enough to swap for Redis or SQLite without touching callers.
"""

from __future__ import annotations

from collections import deque
from typing import Iterable
from ..types import ChatMessage, LLMReply


class PersonaMemory:
    def __init__(self, chat_window: int = 60, reply_window: int = 30):
        self._chat: deque[ChatMessage] = deque(maxlen=chat_window)
        self._replies: deque[LLMReply] = deque(maxlen=reply_window)

    def remember_chat(self, msg: ChatMessage) -> None:
        self._chat.append(msg)

    def remember_reply(self, reply: LLMReply) -> None:
        self._replies.append(reply)

    def recent_chat(self, n: int = 10) -> Iterable[ChatMessage]:
        return list(self._chat)[-n:]

    def recent_replies(self, n: int = 5) -> Iterable[LLMReply]:
        return list(self._replies)[-n:]
