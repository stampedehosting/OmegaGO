"""Chat ingestion subsystem."""

from .base import ChatSource, Multiplexer
from .mock import MockChat
from .youtube import YouTubeLiveChat
from .twitch import TwitchChat
from .tiktok import TikTokLiveChat
from .linkedin import LinkedInLiveChat


_REGISTRY: dict[str, type[ChatSource]] = {
    "mock": MockChat,
    "youtube": YouTubeLiveChat,
    "twitch": TwitchChat,
    "tiktok": TikTokLiveChat,
    "linkedin": LinkedInLiveChat,
}


def build_sources(platform_configs: list[dict]) -> list[ChatSource]:
    """Instantiate ChatSource objects from a list of `{type, ...}` config dicts."""
    sources: list[ChatSource] = []
    for cfg in platform_configs:
        kind = cfg["type"]
        cls = _REGISTRY.get(kind)
        if not cls:
            raise ValueError(f"Unknown ingest source: {kind!r}")
        sources.append(cls(cfg))
    return sources


__all__ = ["ChatSource", "Multiplexer", "build_sources"]
