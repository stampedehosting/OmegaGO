"""Output sinks consume the final composited frames + audio."""

from __future__ import annotations

import abc
import asyncio
import os
import shutil
import subprocess
from dataclasses import dataclass
from loguru import logger
import numpy as np

from ..types import VideoFrame, AudioChunk


@dataclass
class OutputConfig:
    sink: str = "preview"            # "preview" | "virtualcam" | "rtmp"
    rtmp_urls: list[str] = None      # one or more rtmp://... destinations
    width: int = 768
    height: int = 1280
    fps: int = 25
    audio_sample_rate: int = 24000


class OutputSink(abc.ABC):
    def __init__(self, cfg: OutputConfig):
        self.cfg = cfg

    @abc.abstractmethod
    async def push_frame(self, frame: VideoFrame): ...

    @abc.abstractmethod
    async def push_audio(self, chunk: AudioChunk): ...

    async def close(self): ...


class PreviewSink(OutputSink):
    """Logs framerate; useful for headless smoke tests."""

    def __init__(self, cfg: OutputConfig):
        super().__init__(cfg)
        self._n = 0
        self._t0 = None
        self._audio_bytes = 0

    async def push_frame(self, frame: VideoFrame):
        import time
        if self._t0 is None:
            self._t0 = time.monotonic()
        self._n += 1
        if self._n % (self.cfg.fps * 5) == 0:
            dt = time.monotonic() - self._t0
            logger.info(f"[output:preview] {self._n} frames, {self._n / dt:.1f} fps avg, "
                        f"{self._audio_bytes/1024:.1f} KiB audio")

    async def push_audio(self, chunk: AudioChunk):
        self._audio_bytes += len(chunk.pcm)


class VirtualCamSink(OutputSink):
    """Push frames to a v4l2loopback device via pyvirtualcam; audio via PulseAudio sink."""

    def __init__(self, cfg: OutputConfig):
        super().__init__(cfg)
        self._cam = None

    async def push_frame(self, frame: VideoFrame):
        if self._cam is None:
            import pyvirtualcam  # type: ignore
            self._cam = pyvirtualcam.Camera(width=self.cfg.width, height=self.cfg.height,
                                            fps=self.cfg.fps,
                                            fmt=pyvirtualcam.PixelFormat.BGR)
            logger.info(f"[output:virtualcam] device={self._cam.device}")
        self._cam.send(frame.bgr)
        self._cam.sleep_until_next_frame()

    async def push_audio(self, chunk: AudioChunk):
        # On Linux, write to a PulseAudio null-sink the user wired up.
        # Implementation: see deploy/scripts/setup_audio_sink.sh
        pass

    async def close(self):
        if self._cam:
            self._cam.close()


class FfmpegRtmpSink(OutputSink):
    """Pipes raw video + PCM into ffmpeg, which encodes and pushes RTMP.

    Single ffmpeg process per RTMP URL. For multi-platform fanout, run
    multiple instances or use `tee` with `-f tee "[f=flv]rtmp://a|[f=flv]rtmp://b"`.
    """

    def __init__(self, cfg: OutputConfig):
        super().__init__(cfg)
        self._procs: list[subprocess.Popen] = []

    def _spawn(self, url: str) -> subprocess.Popen:
        if not shutil.which("ffmpeg"):
            raise RuntimeError("ffmpeg not found on PATH")
        cmd = [
            "ffmpeg", "-y",
            "-f", "rawvideo", "-pix_fmt", "bgr24",
            "-s", f"{self.cfg.width}x{self.cfg.height}",
            "-r", str(self.cfg.fps),
            "-i", "pipe:0",
            "-f", "s16le", "-ar", str(self.cfg.audio_sample_rate), "-ac", "1",
            "-thread_queue_size", "1024",
            "-i", "pipe:3",
            "-c:v", "h264_nvenc", "-preset", "p4", "-tune", "ll",
            "-b:v", "4500k", "-maxrate", "5000k", "-bufsize", "9000k",
            "-pix_fmt", "yuv420p", "-g", str(self.cfg.fps * 2),
            "-c:a", "aac", "-b:a", "128k",
            "-f", "flv", url,
        ]
        # We need a second pipe (fd=3) for audio; use pass_fds + os.pipe.
        a_r, a_w = os.pipe()
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, pass_fds=(a_r,))
        proc._audio_w = a_w  # type: ignore[attr-defined]
        os.close(a_r)
        return proc

    async def push_frame(self, frame: VideoFrame):
        if not self._procs:
            for url in self.cfg.rtmp_urls or []:
                self._procs.append(self._spawn(url))
            logger.info(f"[output:rtmp] streaming to {len(self._procs)} destination(s)")
        data = np.ascontiguousarray(frame.bgr).tobytes()
        for p in self._procs:
            assert p.stdin is not None
            p.stdin.write(data)

    async def push_audio(self, chunk: AudioChunk):
        for p in self._procs:
            os.write(p._audio_w, chunk.pcm)  # type: ignore[attr-defined]

    async def close(self):
        for p in self._procs:
            try:
                if p.stdin: p.stdin.close()
                os.close(p._audio_w)  # type: ignore[attr-defined]
                p.wait(timeout=5)
            except Exception:
                p.kill()


def build_sink(cfg: OutputConfig) -> OutputSink:
    return {
        "preview": PreviewSink,
        "virtualcam": VirtualCamSink,
        "rtmp": FfmpegRtmpSink,
    }[cfg.sink](cfg)
