"""YouTube Live chat reader.

Uses the Data API v3 `liveChatMessages.list` endpoint with polling.
Quota cost per call is 1 unit; default daily quota is 10,000 units, so a 2s
poll for 24h costs ~43,200 units — request a quota increase or back off when
chat is quiet (the API returns a `pollingIntervalMillis` hint we honor).
"""

from __future__ import annotations

import asyncio
import os
from loguru import logger

from .base import ChatSource
from ..types import ChatMessage, Platform


class YouTubeLiveChat(ChatSource):
    name = "youtube"

    async def run(self, out_q):
        api_key = os.environ.get("YOUTUBE_API_KEY") or self.config.get("api_key")
        video_id = self.config["video_id"]
        if not api_key:
            logger.warning("[ingest:youtube] no YOUTUBE_API_KEY set; sleeping")
            await asyncio.Event().wait()
            return

        # Lazy import so the module is optional at runtime.
        from googleapiclient.discovery import build  # type: ignore

        yt = build("youtube", "v3", developerKey=api_key, cache_discovery=False)
        live_chat_id = self._resolve_live_chat_id(yt, video_id)

        page_token: str | None = None
        while True:
            req = yt.liveChatMessages().list(
                liveChatId=live_chat_id,
                part="id,snippet,authorDetails",
                pageToken=page_token,
            )
            resp = await asyncio.to_thread(req.execute)
            for item in resp.get("items", []):
                snip = item["snippet"]
                author = item["authorDetails"]
                await out_q.put(
                    ChatMessage(
                        id=item["id"],
                        platform=Platform.YOUTUBE,
                        user=author["displayName"],
                        text=snip.get("displayMessage", ""),
                        is_member=author.get("isChatSponsor", False),
                        is_mod=author.get("isChatModerator", False),
                        superchat_amount=float(
                            snip.get("superChatDetails", {}).get("amountMicros", 0)
                        ) / 1_000_000,
                    )
                )
            page_token = resp.get("nextPageToken")
            await asyncio.sleep(resp.get("pollingIntervalMillis", 2000) / 1000)

    @staticmethod
    def _resolve_live_chat_id(yt, video_id: str) -> str:
        resp = yt.videos().list(id=video_id, part="liveStreamingDetails").execute()
        items = resp.get("items", [])
        if not items:
            raise RuntimeError(f"YouTube video {video_id} not found / not live")
        return items[0]["liveStreamingDetails"]["activeLiveChatId"]
