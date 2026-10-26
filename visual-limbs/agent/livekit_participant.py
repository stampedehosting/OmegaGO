#!/usr/bin/env python3
"""livekit_participant.py — the agent's voice/presence in a LiveKit room.

Joins the room as `agentNNN`, publishes the desktop as a screen-share video
track (frames pulled from the local eyes /frame endpoint), and subscribes to
audio tracks so voice commands reach the mesh.

LiveKit layout on the control node (per blueprint):
    :7880 HTTP/WS   :7881 RTC   UDP 50000-60000   SIP :5060

Env:
    LIVEKIT_URL      ws(s)://<control>:7880   (required to run)
    LIVEKIT_TOKEN    join token               (required, env only)
    LIVEKIT_IDENTITY participant name         (default agentNNN)
    EYES_URL         frame source             (default http://127.0.0.1:8700+N)

If the `livekit` package isn't installed the module still imports and
`main()` exits cleanly with code 0 after logging — other limbs keep working.
"""

import asyncio
import io
import os
import sys

import requests

try:
    from livekit import rtc
    HAS_LIVEKIT = True
except ImportError:
    rtc = None  # type: ignore
    HAS_LIVEKIT = False

IDX = int(os.environ.get("AGENT_INDEX", "1"))
LIVEKIT_URL = os.environ.get("LIVEKIT_URL", "")
LIVEKIT_TOKEN = os.environ.get("LIVEKIT_TOKEN", "")
IDENTITY = os.environ.get("LIVEKIT_IDENTITY", f"agent{IDX:03d}")
EYES_URL = os.environ.get("EYES_URL",
                          f"http://127.0.0.1:{8700 + IDX}").rstrip("/")
PUBLISH_FPS = float(os.environ.get("LIVEKIT_FPS", "2"))  # screen share is slow-mo
WIDTH = int(os.environ.get("EYES_WIDTH", "1024"))
HEIGHT = int(os.environ.get("EYES_HEIGHT", "768"))


def _fetch_frame_jpeg() -> bytes | None:
    try:
        r = requests.get(f"{EYES_URL}/frame", timeout=10)
        if r.ok:
            return r.content
    except Exception:
        pass
    return None


def _jpeg_to_video_frame(jpeg: bytes):
    """Decode JPEG -> I420 VideoFrame for the rtc.VideoSource."""
    import cv2
    import numpy as np
    arr = np.frombuffer(jpeg, dtype=np.uint8)
    bgr = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if bgr is None:
        return None
    bgr = cv2.resize(bgr, (WIDTH, HEIGHT))
    yuv = cv2.cvtColor(bgr, cv2.COLOR_BGR2YUV_I420)
    return rtc.VideoFrame(WIDTH, HEIGHT,
                          rtc.VideoBufferType.I420, yuv.tobytes())


async def run() -> None:
    room = rtc.Room()

    @room.on("track_subscribed")
    def on_track(track, publication, participant):  # audio in -> log it
        if track.kind == rtc.TrackKind.KIND_AUDIO:
            print(f"[livekit] subscribed to audio from "
                  f"{participant.identity}", flush=True)

    print(f"[livekit] connecting {LIVEKIT_URL} as {IDENTITY}", flush=True)
    await room.connect(LIVEKIT_URL, LIVEKIT_TOKEN)
    print(f"[livekit] joined room {room.name!r}", flush=True)

    # Publish the desktop as a screen-share track.
    source = rtc.VideoSource(WIDTH, HEIGHT)
    track = rtc.LocalVideoTrack.create_video_track("screen", source)
    await room.local_participant.publish_track(
        track,
        rtc.TrackPublishOptions(source=rtc.TrackSource.SOURCE_SCREENSHARE),
    )
    print("[livekit] publishing screen share track", flush=True)

    interval = 1.0 / PUBLISH_FPS
    try:
        while room.connection_state == rtc.ConnectionState.CONN_CONNECTED:
            jpeg = _fetch_frame_jpeg()
            if jpeg:
                frame = _jpeg_to_video_frame(jpeg)
                if frame is not None:
                    source.capture_frame(frame)
            await asyncio.sleep(interval)
    finally:
        await room.disconnect()
        print("[livekit] disconnected", flush=True)


def main() -> int:
    if not HAS_LIVEKIT:
        print("[livekit] 'livekit' package not installed — "
              "voice lane disabled, other limbs unaffected.", flush=True)
        return 0
    if not (LIVEKIT_URL and LIVEKIT_TOKEN):
        print("[livekit] LIVEKIT_URL/LIVEKIT_TOKEN unset — nothing to join.",
              flush=True)
        return 0
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
