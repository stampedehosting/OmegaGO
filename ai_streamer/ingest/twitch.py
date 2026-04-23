"""Twitch chat reader.

Twitch IRC over WebSocket is the simplest path. Anonymous read uses
nickname `justinfan<random>` with no oauth token, which is enough for read-only
chat ingestion. Set `TWITCH_OAUTH` in the environment to chat as a real user.
"""

from __future__ import annotations

import asyncio
import os
import random
import re
from loguru import logger

from .base import ChatSource
from ..types import ChatMessage, Platform


_PRIVMSG = re.compile(r":(?P<user>[^!]+)![^ ]+ PRIVMSG #[^ ]+ :(?P<text>.*)")


class TwitchChat(ChatSource):
    name = "twitch"

    async def run(self, out_q):
        import aiohttp

        channel = self.config["channel"].lower().lstrip("#")
        nick = os.environ.get("TWITCH_NICK") or f"justinfan{random.randint(10000, 99999)}"
        oauth = os.environ.get("TWITCH_OAUTH", "SCHMOOPIIE")  # anon-friendly placeholder

        async with aiohttp.ClientSession() as session:
            async with session.ws_connect("wss://irc-ws.chat.twitch.tv:443") as ws:
                await ws.send_str(f"PASS oauth:{oauth}" if oauth.startswith("oauth:") is False and oauth != "SCHMOOPIIE" else f"PASS {oauth}")
                await ws.send_str(f"NICK {nick}")
                await ws.send_str(f"JOIN #{channel}")
                logger.info(f"[ingest:twitch] joined #{channel} as {nick}")

                async for msg in ws:
                    if msg.type != aiohttp.WSMsgType.TEXT:
                        continue
                    for line in msg.data.splitlines():
                        if line.startswith("PING"):
                            await ws.send_str("PONG :tmi.twitch.tv")
                            continue
                        m = _PRIVMSG.search(line)
                        if not m:
                            continue
                        await out_q.put(
                            ChatMessage.new(
                                Platform.TWITCH,
                                m.group("user"),
                                m.group("text").strip(),
                            )
                        )
