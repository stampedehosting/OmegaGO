#!/usr/bin/env python3
"""parser_client.py — OmniParser/YOLO pre-filter client.

Sends a frame (JPEG bytes) to the OmniParser/YOLO11 endpoint and normalizes
whatever shape it returns into a flat list of labeled UI boxes in 1024x768
pixel coordinates:

    {"label": str, "kind": "text"|"icon"|"box", "x": int, "y": int,
     "w": int, "h": int, "confidence": float}

If the parser endpoint is down or times out, `parse_frame` degrades
gracefully and returns `{"boxes": [], "raw": true}` so the brain can act on
the raw frame alone.

Daemon mode (run standalone) exposes:

    POST /parse   -> body: JPEG bytes (or multipart file "image") => boxes JSON
    GET  /boxes   -> parse the latest frame from EYES_URL and return boxes
    GET  /health  -> {"ok": true, "parser": "<url or null>"}
"""

import io
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlparse

import requests

OMNIPARSER_URL = os.environ.get("OMNIPARSER_URL", "").rstrip("/")
PARSER_TIMEOUT = float(os.environ.get("PARSER_TIMEOUT", "10"))
FRAME_W = int(os.environ.get("EYES_WIDTH", "1024"))
FRAME_H = int(os.environ.get("EYES_HEIGHT", "768"))
# Optional shared secret for the limb endpoints (see hands.py / README).
AGENT_TOKEN = os.environ.get("AGENT_TOKEN", "")
MAX_BODY = int(os.environ.get("PARSER_MAX_BODY", str(8 * 1024 * 1024)))


def _headers() -> dict:
    return {"Authorization": f"Bearer {AGENT_TOKEN}"} if AGENT_TOKEN else {}


def _authorized(handler: BaseHTTPRequestHandler) -> bool:
    if not AGENT_TOKEN:
        return True
    auth = handler.headers.get("Authorization", "")
    token = handler.headers.get("X-Agent-Token", "")
    return auth == f"Bearer {AGENT_TOKEN}" or token == AGENT_TOKEN


def _clamp(v: float, lo: float, hi: float) -> int:
    return int(max(lo, min(hi, round(v))))


def _norm_box(raw: Any) -> dict | None:
    """Normalize one detection record into our box schema (best-effort).

    Handles the common OmniParser / YOLO response shapes:
      {"bbox": [x1,y1,x2,y2], "content"/"label"/"name", "type", "confidence"}
      {"box":  [x1,y1,x2,y2], "class"/"label", "confidence"/"score"}
      [x1, y1, x2, y2] or [x, y, w, h, label?, conf?]
    Coordinates may be absolute pixels or normalized 0-1 fractions.
    """
    if not isinstance(raw, (dict, list)):
        return None

    if isinstance(raw, dict):
        bbox = raw.get("bbox") or raw.get("box") or raw.get("bounding_box")
        label = (raw.get("label") or raw.get("content") or raw.get("name")
                 or raw.get("class") or raw.get("text") or "")
        kind = raw.get("type") or raw.get("kind") or "box"
        conf = raw.get("confidence", raw.get("score", 1.0))
    else:
        if len(raw) < 4:
            return None
        bbox, label, kind, conf = raw[:4], "", "box", raw[4] if len(raw) > 4 else 1.0

    if not bbox or len(bbox) < 4:
        return None
    x1, y1, x2, y2 = (float(bbox[i]) for i in range(4))

    # Some parsers emit [x, y, w, h] instead of corners — if x2/y2 look
    # smaller than x1/y1 the record is ambiguous, so also accept the
    # documented corner convention first; only reinterpret when clearly wh.
    if x2 <= x1 or y2 <= y1:
        x2, y2 = x1 + x2, y1 + y2

    # Normalized coords (0..1) -> pixels.
    if max(abs(x1), abs(y1), abs(x2), abs(y2)) <= 1.5:
        x1, x2 = x1 * FRAME_W, x2 * FRAME_W
        y1, y2 = y1 * FRAME_H, y2 * FRAME_H

    x1, x2 = sorted((x1, x2))
    y1, y2 = sorted((y1, y2))
    return {
        "label": str(label)[:200],
        "kind": str(kind),
        "x": _clamp(x1, 0, FRAME_W),
        "y": _clamp(y1, 0, FRAME_H),
        "w": _clamp(x2 - x1, 0, FRAME_W),
        "h": _clamp(y2 - y1, 0, FRAME_H),
        "confidence": float(conf) if isinstance(conf, (int, float)) else 1.0,
    }


def _extract_detections(payload: Any) -> list:
    """Pull the detection list out of the response body."""
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("boxes", "detections", "parsed_content_list",
                    "elements", "results", "predictions"):
            if isinstance(payload.get(key), list):
                return payload[key]
        # single-detection responses
        if payload.get("bbox") or payload.get("box"):
            return [payload]
    return []


def parse_frame(jpeg_bytes: bytes, parser_url: str | None = None) -> dict:
    """POST the frame to OmniParser/YOLO; fall back to raw on any failure."""
    url = (parser_url or OMNIPARSER_URL).rstrip("/")
    if not url:
        return {"boxes": [], "raw": True, "source": "raw",
                "error": "OMNIPARSER_URL not set"}
    try:
        resp = requests.post(
            f"{url}/parse",
            files={"image": ("frame.jpg", io.BytesIO(jpeg_bytes), "image/jpeg")},
            timeout=PARSER_TIMEOUT,
        )
        if resp.status_code == 404:  # some deployments serve /predict or /
            resp = requests.post(
                url,
                files={"image": ("frame.jpg", io.BytesIO(jpeg_bytes), "image/jpeg")},
                timeout=PARSER_TIMEOUT,
            )
        resp.raise_for_status()
        detections = _extract_detections(resp.json())
    except Exception as exc:
        return {"boxes": [], "raw": True, "source": "raw", "error": str(exc)}

    boxes = [b for b in (_norm_box(d) for d in detections) if b]
    return {"boxes": boxes, "raw": False, "source": url,
            "count": len(boxes)}


def _read_body(handler: BaseHTTPRequestHandler) -> bytes:
    """Accept raw JPEG bodies or multipart uploads."""
    ctype = handler.headers.get("Content-Type", "")
    length = int(handler.headers.get("Content-Length", "0") or 0)
    body = handler.rfile.read(length)
    if "multipart/form-data" in ctype:
        # grab the first file part's payload
        marker = b"\r\n\r\n"
        start = body.find(marker)
        if start != -1:
            payload = body[start + len(marker):]
            end = payload.rfind(b"\r\n--")
            return payload[:end] if end != -1 else payload
    return body


def serve(port: int) -> None:
    eyes_url = os.environ.get("EYES_URL", "").rstrip("/")

    class Handler(BaseHTTPRequestHandler):
        def _json(self, code: int, obj: dict) -> None:
            body = json.dumps(obj).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self) -> None:  # noqa: N802
            if not _authorized(self):
                self._json(401, {"error": "unauthorized"})
                return
            length = int(self.headers.get("Content-Length", "0") or 0)
            if length > MAX_BODY:
                self._json(413, {"error": "body too large"})
                return
            if self.path == "/parse":
                jpeg = _read_body(self)
                if not jpeg:
                    self._json(400, {"error": "empty body"})
                    return
                self._json(200, parse_frame(jpeg))
            else:
                self._json(404, {"error": "unknown path"})

        def do_GET(self) -> None:  # noqa: N802
            if not _authorized(self):
                self._json(401, {"error": "unauthorized"})
                return
            if self.path == "/health":
                self._json(200, {"ok": True,
                                 "parser": OMNIPARSER_URL or None})
            elif self.path == "/boxes":
                if not eyes_url:
                    self._json(503, {"error": "EYES_URL not set"})
                    return
                try:
                    r = requests.get(f"{eyes_url}/frame", headers=_headers(),
                                     timeout=10)
                    r.raise_for_status()
                except Exception as exc:
                    self._json(502, {"error": f"eyes unreachable: {exc}"})
                    return
                self._json(200, parse_frame(r.content))
            else:
                self._json(404, {"error": "unknown path",
                                 "paths": ["/parse", "/boxes", "/health"]})

        def log_message(self, fmt, *args) -> None:
            pass

    print(f"[parser] OMNIPARSER_URL={OMNIPARSER_URL or '<unset>'} "
          f"listening on 127.0.0.1:{port}", flush=True)
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()


def main() -> int:
    port = int(os.environ.get("PARSER_PORT", "0") or 0)
    if port <= 0:
        idx = int(os.environ.get("AGENT_INDEX", "1"))
        port = 8800 + idx  # parser range 8801-8900
    serve(port)
    return 0


if __name__ == "__main__":
    sys.exit(main())
