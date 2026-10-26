#!/usr/bin/env python3
"""brain_client.py — vision brain client + the agent's perception loop.

Sends the latest frame plus parsed UI boxes to the vision lane
(qwen2.5-vl-32b, OpenAI-compatible) and asks for a single action JSON:

    {"action": "click|type|key|scroll|goto|wait|done|none",
     "x": <int>, "y": <int>, "text": "...", "key": "...",
     "delta_y": <int>, "url": "...", "reason": "..."}

Primary endpoint:  BRAIN_URL            (e.g. http://127.0.0.1:8000/v1 LiteLLM,
                                        or http://<brain>:8083/v1 direct)
Overflow endpoint: BRAIN_OVERFLOW_URL   (OpenRouter-compatible base) used on
                                        timeout / 429 / 503 (slot full).

Daemon mode (`python3 brain_client.py`) is the wiring loop:
    poll EYES_URL/seq -> on change GET /frame -> parser_client.parse_frame
    -> decide() -> POST the action to HANDS_URL/act.
"""

import base64
import json
import os
import re
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

import requests

try:
    from parser_client import parse_frame
except ImportError:  # allow running from repo root
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from parser_client import parse_frame

BRAIN_URL = os.environ.get("BRAIN_URL", "").rstrip("/")
BRAIN_MODEL = os.environ.get("BRAIN_MODEL", "qwen-vl")
BRAIN_API_KEY = os.environ.get("BRAIN_API_KEY", "sk-local")
BRAIN_TIMEOUT = float(os.environ.get("BRAIN_TIMEOUT", "60"))

BRAIN_OVERFLOW_URL = os.environ.get("BRAIN_OVERFLOW_URL", "").rstrip("/")
BRAIN_OVERFLOW_MODEL = os.environ.get(
    "BRAIN_OVERFLOW_MODEL", "qwen/qwen2.5-vl-32b-instruct")
BRAIN_OVERFLOW_API_KEY = os.environ.get("BRAIN_OVERFLOW_API_KEY", "")

EYES_URL = os.environ.get("EYES_URL", "").rstrip("/")
HANDS_URL = os.environ.get("HANDS_URL", "").rstrip("/")
POLL_INTERVAL = float(os.environ.get("BRAIN_POLL_INTERVAL", "0.5"))
# Re-run decide() on an unchanged screen after this many seconds when the
# last action wasn't terminal (done/none) — lets the agent keep working a
# goal even when pixels stall.
STALL_SECONDS = float(os.environ.get("BRAIN_STALL_SECONDS", "30"))
# Optional shared secret for the limb endpoints (see hands.py / README).
AGENT_TOKEN = os.environ.get("AGENT_TOKEN", "")
MAX_BODY = 1024 * 1024


def _headers() -> dict:
    return {"Authorization": f"Bearer {AGENT_TOKEN}"} if AGENT_TOKEN else {}


def _authorized(handler: BaseHTTPRequestHandler) -> bool:
    if not AGENT_TOKEN:
        return True
    auth = handler.headers.get("Authorization", "")
    token = handler.headers.get("X-Agent-Token", "")
    return auth == f"Bearer {AGENT_TOKEN}" or token == AGENT_TOKEN

ACTIONS_DOC = (
    'Reply with ONE JSON object only, no prose. Schema: '
    '{"action": "click"|"type"|"key"|"scroll"|"goto"|"wait"|"done"|"none", '
    '"x": <int 0-1024>, "y": <int 0-768>, "text": "<string, for type>", '
    '"key": "<e.g. enter, tab, ctrl+s>", "delta_y": <int px, for scroll>, '
    '"url": "<for goto>", "reason": "<short>"}. '
    'Coordinates are in the 1024x768 frame you are shown. '
    'Use "done" when the goal is complete, "wait" if the screen is loading, '
    '"none" if no useful action exists.'
)


class BrainError(Exception):
    """Raised when both primary and overflow brain calls fail."""


def _chat(base_url: str, model: str, api_key: str, messages: list) -> str:
    """One OpenAI-compatible chat.completions call -> content string."""
    resp = requests.post(
        f"{base_url}/chat/completions",
        headers={"Authorization": f"Bearer {api_key}"},
        json={"model": model, "messages": messages,
              "temperature": 0.1, "max_tokens": 256},
        timeout=BRAIN_TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def _extract_json(text: str) -> dict:
    """Pull the first JSON object out of the model's reply."""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text,
                      flags=re.MULTILINE).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if match:
            return json.loads(match.group(0))
        raise


def _is_overflowable(exc: Exception) -> bool:
    """Network failure or slot-full/rate-limit failures justify overflow."""
    if isinstance(exc, (requests.Timeout, requests.ConnectionError)):
        return True
    resp = getattr(exc, "response", None)
    code = getattr(resp, "status_code", None)
    return code in (408, 409, 425, 429, 500, 502, 503, 504)


def decide(instruction: str, frame_jpeg: bytes, boxes: list | None = None) -> dict:
    """Ask the vision brain for the next action. Returns the action JSON."""
    b64 = base64.b64encode(frame_jpeg).decode()
    boxes_text = json.dumps(boxes or [], ensure_ascii=False)
    user_text = (
        f"GOAL: {instruction}\n\n"
        f"UI boxes detected on screen (label, x, y, w, h): {boxes_text}\n\n"
        f"{ACTIONS_DOC}"
    )
    messages = [
        {"role": "system", "content": (
            "You are the action brain of a desktop automation agent. You look "
            "at a screenshot and a list of detected UI elements and choose the "
            "single next action that moves toward the goal. Always answer with "
            "one JSON object and nothing else.")},
        {"role": "user", "content": [
            {"type": "text", "text": user_text},
            {"type": "image_url", "image_url": {
                "url": f"data:image/jpeg;base64,{b64}"}},
        ]},
    ]

    errors = []
    if BRAIN_URL:
        try:
            return _extract_json(_chat(BRAIN_URL, BRAIN_MODEL,
                                       BRAIN_API_KEY, messages))
        except Exception as exc:
            errors.append(f"primary({BRAIN_URL}): {exc}")
            if not _is_overflowable(exc) or not BRAIN_OVERFLOW_URL:
                raise BrainError("; ".join(errors)) from exc
    else:
        errors.append("BRAIN_URL not set")

    if BRAIN_OVERFLOW_URL:
        try:
            return _extract_json(_chat(BRAIN_OVERFLOW_URL, BRAIN_OVERFLOW_MODEL,
                                       BRAIN_OVERFLOW_API_KEY, messages))
        except Exception as exc:
            errors.append(f"overflow({BRAIN_OVERFLOW_URL}): {exc}")

    raise BrainError("; ".join(errors) or "no brain endpoint configured")


def post_action(hands_url: str, action: dict) -> dict:
    resp = requests.post(f"{hands_url.rstrip('/')}/act",
                         json=action, headers=_headers(), timeout=30)
    resp.raise_for_status()
    return resp.json()


class PerceptionLoop:
    """eyes -> parser -> brain -> hands, forever."""

    def __init__(self, eyes_url: str, hands_url: str,
                 parser_url: str | None = None, instruction: str = "") -> None:
        self.eyes_url = eyes_url.rstrip("/")
        self.hands_url = hands_url.rstrip("/")
        self.parser_url = parser_url
        self.instruction = instruction or os.environ.get(
            "AGENT_INSTRUCTION", "Wait for further instructions.")
        self.last_action: dict[str, Any] = {}
        self.running = False
        # Bumped by POST /instruction — a new goal reprocesses the frame even
        # when the screen has not changed.
        self.instruction_rev = 0
        self._seen_seq = -1
        self._seen_rev = -1
        self._last_decide_at = 0.0
        self._last_terminal = True

    def _get(self, path: str) -> requests.Response:
        r = requests.get(f"{self.eyes_url}{path}", headers=_headers(),
                         timeout=15)
        r.raise_for_status()
        return r

    def step(self) -> None:
        seq = self._get("/seq").json().get("seq", 0)
        new_instruction = self.instruction_rev != self._seen_rev
        stalled = (
            not self._last_terminal and self._last_decide_at
            and time.time() - self._last_decide_at >= STALL_SECONDS
        )
        if seq <= self._seen_seq and not new_instruction and not stalled:
            return
        frame = self._get("/frame").content
        parsed = parse_frame(frame, self.parser_url)
        # Snapshot the goal BEFORE deciding — a /instruction POST can land
        # while decide() is in flight.
        instruction, rev = self.instruction, self.instruction_rev
        action = self._sanitize(decide(instruction, frame, parsed.get("boxes")))
        self._seen_seq = seq
        self._seen_rev = rev  # record only the revision we decided with
        self._last_decide_at = time.time()
        self._last_terminal = action.get("action") in ("done", "none")
        if self.instruction_rev != rev:
            # Goal changed mid-decide — don't execute a stale action; the
            # next step re-decides with the new instruction.
            print(f"[brain] instruction changed mid-decide; discarding "
                  f"{action.get('action')!r}", flush=True)
            return
        self.last_action = {"action": action, "seq": seq,
                            "boxes": parsed.get("count", 0),
                            "parser_raw": parsed.get("raw", True),
                            "at": self._last_decide_at}
        if self.hands_url:
            try:
                self.last_action["result"] = post_action(self.hands_url, action)
            except Exception as exc:
                self.last_action["result"] = {"ok": False, "error": str(exc)}
        print(f"[brain] seq={seq} action={action.get('action')} "
              f"raw={parsed.get('raw')}", flush=True)

    @staticmethod
    def _sanitize(action: dict) -> dict:
        if not isinstance(action, dict) or "action" not in action:
            return {"action": "none", "reason": "unparseable brain reply"}
        return action

    def run(self) -> None:
        self.running = True
        backoff = POLL_INTERVAL
        print(f"[brain] loop eyes={self.eyes_url} hands={self.hands_url} "
              f"instruction={self.instruction!r}", flush=True)
        while self.running:
            try:
                self.step()
                backoff = POLL_INTERVAL
            except Exception as exc:
                print(f"[brain] loop error: {exc} (retry in {backoff:.1f}s)",
                      flush=True)
                time.sleep(backoff)
                backoff = min(backoff * 2, 30)
                continue
            time.sleep(POLL_INTERVAL)


def serve(loop: PerceptionLoop, port: int) -> None:
    class Handler(BaseHTTPRequestHandler):
        def _json(self, code: int, obj: dict) -> None:
            body = json.dumps(obj).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:  # noqa: N802
            if not _authorized(self):
                self._json(401, {"ok": False, "error": "unauthorized"})
                return
            if self.path == "/health":
                self._json(200, {"ok": True, "running": loop.running})
            elif self.path == "/last":
                self._json(200, loop.last_action or {"action": None})
            else:
                self._json(404, {"error": "unknown path",
                                 "paths": ["/health", "/last"]})

        def do_POST(self) -> None:  # noqa: N802
            if not _authorized(self):
                self._json(401, {"ok": False, "error": "unauthorized"})
                return
            # POST /instruction {"instruction": "..."} — retarget the agent.
            if self.path == "/instruction":
                length = int(self.headers.get("Content-Length", "0") or 0)
                if length > MAX_BODY:
                    self._json(413, {"error": "body too large"})
                    return
                try:
                    body = json.loads(self.rfile.read(length) or b"{}")
                    loop.instruction = str(body["instruction"])
                    loop.instruction_rev += 1  # force a re-decide next step
                    self._json(200, {"ok": True,
                                     "instruction": loop.instruction})
                except Exception as exc:
                    self._json(400, {"error": str(exc)})
            else:
                self._json(404, {"error": "unknown path"})

        def log_message(self, fmt, *args) -> None:
            pass

    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()


def main() -> int:
    idx = int(os.environ.get("AGENT_INDEX", "1"))
    port = int(os.environ.get("BRAIN_PORT", "0") or 0) or 8900 + idx
    eyes_url = EYES_URL or f"http://127.0.0.1:{8700 + idx}"
    hands_url = HANDS_URL or f"http://127.0.0.1:{8500 + idx}"
    parser_url = os.environ.get("OMNIPARSER_URL") or None

    loop = PerceptionLoop(eyes_url, hands_url, parser_url)
    import threading
    threading.Thread(target=loop.run, daemon=True).start()
    print(f"[brain] status on 127.0.0.1:{port}", flush=True)
    serve(loop, port)
    return 0


if __name__ == "__main__":
    sys.exit(main())
