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
# Optional shared secret — when set, all endpoints require a bearer token.
AGENT_TOKEN = os.environ.get("AGENT_TOKEN", "")


def _authorized(handler: BaseHTTPRequestHandler) -> bool:
    if not AGENT_TOKEN:
        return True
    auth = handler.headers.get("Authorization", "")
    token = handler.headers.get("X-Agent-Token", "")
    return auth == f"Bearer {AGENT_TOKEN}" or token == AGENT_TOKEN


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


def _grab_bgr(sct: mss.mss) -> tuple[np.ndarray, int, int]:
    """Capture the primary monitor -> (BGR image, monitor_x0, monitor_y0)."""
    mon = sct.monitors[MONITOR]
    shot = sct.grab(mon)
    frame = np.asarray(shot, dtype=np.uint8)[:, :, :3]  # drop alpha -> BGR
    return frame, int(mon["left"]), int(mon["top"])


def _fit(frame: np.ndarray) -> np.ndarray:
    """Center-crop to the target aspect ratio, then resize to WxH."""
    x0, y0, cw, ch, _, _ = fit_geometry(frame.shape[1], frame.shape[0])
    frame = frame[y0 : y0 + ch, x0 : x0 + cw]
    return cv2.resize(frame, (WIDTH, HEIGHT), interpolation=cv2.INTER_AREA)


def fit_geometry(src_w: int, src_h: int) -> tuple:
    """The crop+scale eyes applies: (x0, y0, crop_w, crop_h, scale_x, scale_y).

    Inverse mapping used by hands: display_x = x0 + fx * crop_w/WIDTH.
    """
    target_ratio = WIDTH / HEIGHT
    src_ratio = src_w / src_h
    if src_ratio > target_ratio:  # too wide -> crop sides
        crop_w, crop_h = int(src_h * target_ratio), src_h
        x0, y0 = (src_w - crop_w) // 2, 0
    else:  # too tall -> crop top/bottom
        crop_w, crop_h = src_w, int(src_w / target_ratio)
        x0, y0 = 0, (src_h - crop_h) // 2
    return x0, y0, crop_w, crop_h, crop_w / WIDTH, crop_h / HEIGHT


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
        self.last_error: str | None = None
        # Frame->display transform, kept current for /geometry so hands can
        # inverse-map brain coordinates back to native display pixels.
        self.geometry: dict = {}

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
        # Re-open the mss context on failure too — the display may not be up
        # yet when the agent launcher starts.
        while self.running:
            try:
                with mss.mss() as sct:
                    self.last_error = None
                    while self.running:
                        try:
                            raw, mon_x0, mon_y0 = _grab_bgr(sct)
                            x0, y0, cw, ch, sx, sy = fit_geometry(
                                raw.shape[1], raw.shape[0])
                            self.geometry = {
                                "monitor_x0": mon_x0, "monitor_y0": mon_y0,
                                "src_w": raw.shape[1], "src_h": raw.shape[0],
                                "crop_x0": x0, "crop_y0": y0,
                                "crop_w": cw, "crop_h": ch,
                                "frame_w": WIDTH, "frame_h": HEIGHT,
                                "scale_x": sx, "scale_y": sy,
                            }
                            frame = _fit(raw)
                            self.last_error = None  # healthy again
                        except Exception as exc:
                            print(f"[eyes] grab failed: {exc}", flush=True)
                            self.last_error = str(exc)
                            time.sleep(POLL_INTERVAL * 4)
                            continue

                        if last_emitted is None or (
                            changed_fraction(last_emitted, frame)
                            >= CHANGED_FRACTION
                        ):
                            seq = self.store.put(self._encode(frame))
                            self.frames_emitted = seq
                            last_emitted = frame
                        time.sleep(POLL_INTERVAL)
            except Exception as exc:  # e.g. X display not up yet
                self.last_error = str(exc)
                print(f"[eyes] display open failed: {exc}; retry in 5s",
                      flush=True)
                time.sleep(5)


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
            if not _authorized(self):
                self._json(401, {"error": "unauthorized"})
                return
            if self.path == "/frame":
                jpeg, _ = store.get()
                if jpeg is None:
                    self._json(503, {"error": "no frame emitted yet"})
                else:
                    self._send(200, jpeg, "image/jpeg")
            elif self.path == "/seq":
                _, seq = store.get()
                self._json(200, {"seq": seq})
            elif self.path == "/geometry":
                # display_x = monitor_x0 + crop_x0 + frame_x * scale_x
                self._json(200, watcher.geometry or {"error": "no frame yet"})
            elif self.path == "/health":
                self._json(200, {
                    "ok": watcher.last_error is None,
                    "frames_emitted": watcher.frames_emitted,
                    "watcher_error": watcher.last_error,
                    "display": os.environ.get("DISPLAY", ""),
                    "size": [WIDTH, HEIGHT],
                })
            else:
                self._json(404, {"error": "unknown path",
                                 "paths": ["/frame", "/seq", "/geometry",
                                           "/health"]})

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
