"""TikTok Live chat reader using the (unofficial) TikTokLive library.

Note: TikTok has no public real-time chat API. The TikTokLive library connects
to TikTok's internal websocket. Be aware this can break with platform updates.
RTMP stream key access still requires 1,000+ followers on the broadcasting account.
"""

from __future__ import annotations

import asyncio
from loguru import logger

from .base import ChatSource
from ..types import ChatMessage, Platform


class TikTokLiveChat(ChatSource):
    name = "tiktok"

    async def run(self, out_q):
        try:
            from TikTokLive import TikTokLiveClient  # type: ignore
            from TikTokLive.events import CommentEvent, GiftEvent  # type: ignore
        except ImportError:
            logger.warning("[ingest:tiktok] TikTokLive not installed; install with `pip install TikTokLive`")
            await asyncio.Event().wait()
            return

        username = self.config["username"].lstrip("@")
        client = TikTokLiveClient(unique_id=f"@{username}")

        @client.on(CommentEvent)
        async def _on_comment(event):
            await out_q.put(
                ChatMessage.new(
                    Platform.TIKTOK,
                    event.user.nickname,
                    event.comment,
                )
            )

        @client.on(GiftEvent)
        async def _on_gift(event):
            # TikTok gifts can stream multiple events per gift; collapse on `streakable`.
            if event.gift.streakable and not event.streaking:
                await out_q.put(
                    ChatMessage.new(
                        Platform.TIKTOK,
                        event.user.nickname,
                        f"[gift x{event.repeat_count}] {event.gift.name}",
                        superchat_amount=event.gift.diamond_count * event.repeat_count * 0.005,  # rough USD
                    )
                )

        logger.info(f"[ingest:tiktok] connecting to @{username}")
        await client.start()
