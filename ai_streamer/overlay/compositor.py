"""Overlay compositor.

Renders the live UI layer (chat feed, viewer count, hearts) as an RGBA image
and alpha-composites it onto each VideoFrame from the avatar engine.

Designed to be cheap (CPU, ~1 ms per 720p frame) using OpenCV. The chat list
is read from StreamContext, so the orchestrator just keeps that updated.
"""

from __future__ import annotations

import time
from collections import deque
import numpy as np
import cv2

from ..types import StreamContext


class OverlayCompositor:
    def __init__(self, ctx: StreamContext, max_chat_lines: int = 6):
        self.ctx = ctx
        self.max_chat_lines = max_chat_lines
        self._hearts: deque[tuple[float, int, int]] = deque(maxlen=24)  # (born_at, x, y)

    def add_heart(self, x: int, y: int):
        self._hearts.append((time.monotonic(), x, y))

    def composite(self, bgr: np.ndarray) -> np.ndarray:
        h, w = bgr.shape[:2]
        out = bgr.copy()

        # Header: viewer count
        cv2.rectangle(out, (16, 16), (260, 64), (0, 0, 0), -1)
        cv2.putText(out, f"LIVE  {self.ctx.viewer_count:,} viewers",
                    (28, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2, cv2.LINE_AA)

        # Chat feed (bottom-left)
        recent = self.ctx.recent_chat[-self.max_chat_lines:]
        y = h - 24 - 30 * len(recent)
        for msg in recent:
            line = f"{msg.user}: {msg.text}"
            (tw, th), _ = cv2.getTextSize(line, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 1)
            cv2.rectangle(out, (12, y - th - 6), (12 + tw + 16, y + 8), (0, 0, 0), -1)
            cv2.putText(out, line, (20, y), cv2.FONT_HERSHEY_SIMPLEX,
                        0.55, (240, 240, 240), 1, cv2.LINE_AA)
            y += 30

        # Hearts (right edge, floating up)
        now = time.monotonic()
        live = []
        for born, x, base_y in self._hearts:
            age = now - born
            if age > 2.5:
                continue
            live.append((born, x, base_y))
            cy = int(base_y - age * 120)
            cv2.circle(out, (x, cy), 12, (0, 0, 255), -1)
        self._hearts = deque(live, maxlen=24)

        return out
