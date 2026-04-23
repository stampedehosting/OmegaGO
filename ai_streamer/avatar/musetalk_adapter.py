"""Avatar frame producer.

Takes AudioChunk stream + a reference portrait/video and yields VideoFrame
objects at the configured fps.

Two implementations:
  * `IdleLoopAvatar` — plays a pre-recorded "idle" loop of the persona,
    optionally tinting brightness with audio RMS so it visibly reacts. No GPU
    required; great for the scaffold and for fallbacks.
  * `MuseTalkAvatar` — wraps the upstream MuseTalk realtime_inference. Fed
    audio chunks, emits 25 fps lipsynced frames. Heavy lift; see TODO.
"""

from __future__ import annotations

import abc
import asyncio
import time
from dataclasses import dataclass
from typing import AsyncIterator
import numpy as np

from ..types import AudioChunk, VideoFrame


@dataclass
class AvatarConfig:
    engine: str = "idle_loop"        # "idle_loop" | "musetalk"
    portrait_path: str = ""          # source image / idle video
    fps: int = 25
    width: int = 768
    height: int = 1280               # 9:16 for TikTok / Shorts default
    musetalk_repo_dir: str = "third_party/MuseTalk"


class AvatarEngine(abc.ABC):
    def __init__(self, cfg: AvatarConfig):
        self.cfg = cfg

    @abc.abstractmethod
    async def render(self, audio_iter: "asyncio.Queue[AudioChunk]") -> AsyncIterator[VideoFrame]: ...


class IdleLoopAvatar(AvatarEngine):
    """Plays a colored placeholder; useful when there's no GPU available."""

    async def render(self, audio_iter):
        frame_dt = 1.0 / self.cfg.fps
        t0 = time.monotonic()
        i = 0
        rms = 0.0
        while True:
            # Drain audio queue non-blocking to compute envelope
            try:
                while True:
                    chunk: AudioChunk = audio_iter.get_nowait()
                    samples = np.frombuffer(chunk.pcm, dtype=np.int16).astype(np.float32)
                    if samples.size:
                        rms = float(np.sqrt(np.mean(samples ** 2))) / 32768.0
            except asyncio.QueueEmpty:
                rms *= 0.85   # decay

            frame = self._draw(i, rms)
            yield VideoFrame(reply_id=None, bgr=frame, pts_ms=int((time.monotonic() - t0) * 1000))
            i += 1
            await asyncio.sleep(frame_dt)

    def _draw(self, i: int, rms: float) -> "np.ndarray":
        h, w = self.cfg.height, self.cfg.width
        # gentle gradient + audio-reactive brightness so you can see it move
        base = np.zeros((h, w, 3), dtype=np.uint8)
        base[..., 0] = 60 + int(30 * rms * 4)        # B
        base[..., 1] = 30                             # G
        base[..., 2] = 90 + int((i % 60))             # R wave
        return base


class MuseTalkAvatar(AvatarEngine):
    async def render(self, audio_iter):
        # TODO: wire upstream MuseTalk's realtime_inference. The library expects
        # a prepared avatar (one-time `preparation=True`) and consumes WAV files.
        # For real-time, we'll fork its loop to accept PCM chunks via a queue.
        # For the scaffold, fall back to IdleLoopAvatar so the pipeline runs.
        async for f in IdleLoopAvatar(self.cfg).render(audio_iter):
            yield f


def build_avatar(cfg: AvatarConfig) -> AvatarEngine:
    return {"idle_loop": IdleLoopAvatar, "musetalk": MuseTalkAvatar}[cfg.engine](cfg)
