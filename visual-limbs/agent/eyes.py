#!/usr/bin/env python3
"""eyes.py — per-desktop screen watcher ("the eyes").

Grabs the agent's X display ($DISPLAY) with mss, diffs each frame against the
last emitted frame with cv2.absdiff, and only emits a new frame when enough
pixels actually changed. Emitted frames are center-cropped/resized to
1024x768 and JPEG-encoded so downstream components (parser -> brain) always
see a fixed-size image.

Also serves a tiny HTTP API so other processes can pull frames:

    GET /frame   -> latest changed frame as image/jpeg (503 if none yet)
    GET /seq     -> {"seq": <int>} incremented every time a frame is emitted
    GET /health  -> {"ok": true, "frames_emitted": <int>, "display": ":N"}

Run standalone:      python3 eyes.py
Import:              from eyes import ScreenDiffWatcher, FrameStore
"""

import json
import os
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import cv2
import mss
import numpy as np

# --- config (all overridable via env) ---------------------------------------
WIDTH = int(os.environ.get("EYES_WIDTH", "1024"))
HEIGHT = int(os.environ.get("EYES_HEIGHT", "768"))
# Per-pixel abs difference (0-255) that counts as "this pixel changed".
PIXEL_THRESHOLD = float(os.environ.get("EYES_PIXEL_THRESHOLD", "12"))
# Fraction of pixels that must change to emit a frame (0.002 = 0.2%).
CHANGED_FRACTION = float(os.environ.get("EYES_CHANGED_FRACTION", "0.002"))
POLL_INTERVAL = float(os.environ.get("EYES_POLL_INTERVAL", "0.25"))
JPEG_QUALITY = int(os.environ.get("EYES_JPEG_QUALITY", "80"))
MONITOR = int(os.environ.get("EYES_MONITOR", "1"))  # mss monitor index; 1 = primary


class FrameStore:
    """Thread-safe holder for the latest emitted frame."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.jpeg: bytes | None = None
        self.seq = 0
        self.emitted_at = 0.0

    def put(self, jpeg: bytes) -> int:
        with self._lock:
            self.jpeg = jpeg
            self.seq += 1
            self.emitted_at = time.time()
            return self.seq

    def get(self) -> tuple[bytes | None, int]:
        with self._lock:
            return self.jpeg, self.seq


def _grab_bgr(sct: mss.mss) -> np.ndarray:
    """Capture the primary monitor and return a BGR image."""
    shot = sct.grab(sct.monitors[MONITOR])
    frame = np.asarray(shot, dtype=np.uint8)  # BGRA
    return frame[:, :, :3]  # drop alpha -> BGR


def _fit(frame: np.ndarray) -> np.ndarray:
    """Center-crop to the target aspect ratio, then resize to WxH."""
    h, w = frame.shape[:2]
    target_ratio = WIDTH / HEIGHT
    src_ratio = w / h
    if src_ratio > target_ratio:  # too wide -> crop sides
        new_w = int(h * target_ratio)
        x0 = (w - new_w) // 2
        frame = frame[:, x0 : x0 + new_w]
    elif src_ratio < target_ratio:  # too tall -> crop top/bottom
        new_h = int(w / target_ratio)
        y0 = (h - new_h) // 2
        frame = frame[y0 : y0 + new_h, :]
    return cv2.resize(frame, (WIDTH, HEIGHT), interpolation=cv2.INTER_AREA)


def changed_fraction(prev: np.ndarray, cur: np.ndarray) -> float:
    """Fraction of pixels whose abs diff exceeds PIXEL_THRESHOLD."""
    diff = cv2.absdiff(prev, cur)
    gray = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
    return float(np.count_nonzero(gray > PIXEL_THRESHOLD)) / gray.size


class ScreenDiffWatcher:
    """Polls the display and emits 1024x768 JPEGs only when pixels change."""

    def __init__(self, store: FrameStore | None = None) -> None:
        self.store = store or FrameStore()
        self.frames_emitted = 0
        self.running = False

    def _encode(self, frame_bgr: np.ndarray) -> bytes:
        ok, buf = cv2.imencode(
            ".jpg", frame_bgr, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY]
        )
        if not ok:
            raise RuntimeError("cv2.imencode failed")
        return buf.tobytes()

    def run(self) -> None:
        self.running = True
        display = os.environ.get("DISPLAY", "<unset>")
        print(f"[eyes] watching DISPLAY={display} monitor={MONITOR} "
              f"poll={POLL_INTERVAL}s threshold={PIXEL_THRESHOLD} "
              f"fraction={CHANGED_FRACTION}", flush=True)
        last_emitted: np.ndarray | None = None
        with mss.mss() as sct:
            while self.running:
                try:
                    frame = _fit(_grab_bgr(sct))
                except Exception as exc:  # display hiccup — keep polling
                    print(f"[eyes] grab failed: {exc}", flush=True)
                    time.sleep(POLL_INTERVAL * 4)
                    continue

                if last_emitted is None or (
                    changed_fraction(last_emitted, frame) >= CHANGED_FRACTION
                ):
                    seq = self.store.put(self._encode(frame))
                    self.frames_emitted = seq
                    last_emitted = frame
                time.sleep(POLL_INTERVAL)


def make_handler(store: FrameStore, watcher: ScreenDiffWatcher):
    class Handler(BaseHTTPRequestHandler):
        def _send(self, code: int, body: bytes, ctype: str) -> None:
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _json(self, code: int, obj: dict) -> None:
            self._send(code, json.dumps(obj).encode(), "application/json")

        def do_GET(self) -> None:  # noqa: N802 (BaseHTTPRequestHandler API)
            if self.path == "/frame":
                jpeg, _ = store.get()
                if jpeg is None:
                    self._json(503, {"error": "no frame emitted yet"})
                else:
                    self._send(200, jpeg, "image/jpeg")
            elif self.path == "/seq":
                _, seq = store.get()
                self._json(200, {"seq": seq})
            elif self.path == "/health":
                self._json(200, {
                    "ok": True,
                    "frames_emitted": watcher.frames_emitted,
                    "display": os.environ.get("DISPLAY", ""),
                    "size": [WIDTH, HEIGHT],
                })
            else:
                self._json(404, {"error": "unknown path",
                                 "paths": ["/frame", "/seq", "/health"]})

        def log_message(self, fmt, *args) -> None:  # keep stdout clean
            pass

    return Handler


def serve(port: int) -> None:
    store = FrameStore()
    watcher = ScreenDiffWatcher(store)
    t = threading.Thread(target=watcher.run, daemon=True)
    t.start()
    server = ThreadingHTTPServer(("127.0.0.1", port), make_handler(store, watcher))
    print(f"[eyes] serving /frame on 127.0.0.1:{port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        watcher.running = False
        server.shutdown()


def main() -> int:
    port = int(os.environ.get("EYES_PORT", "0") or 0)
    if port <= 0:
        idx = int(os.environ.get("AGENT_INDEX", "1"))
        port = 8700 + idx  # eyes frame server range 8701-8800
    serve(port)
    return 0


if __name__ == "__main__":
    sys.exit(main())
