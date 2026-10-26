#!/usr/bin/env python3
"""hands.py — the agent's actuators.

Executes the action JSON produced by the brain against the agent desktop.

Actuation order:
  1. Playwright over CDP (connects to the agent's own Chrome at
     CHROME_CDP_URL / port 9200+AGENT_INDEX) — precise DOM-level input.
  2. PyAutoGUI (humanized bezier mouse moves + typewrite) — anything on the
     desktop, browser chrome included.
  3. xdotool subprocess calls — always available on the X desktop.

Only whitelisted actions run: click, type, key, scroll, goto
("wait", "done", "none" are accepted as no-ops). Coordinates are clamped to
the 1024x768 frame the brain sees.

Daemon mode: POST /act {action json} -> executes -> {"ok": bool, ...}
             GET  /health -> actuator availability
"""

import json
import math
import os
import random
import shutil
import subprocess
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

import requests

# --- optional deps: degrade gracefully ---------------------------------------
try:
    from playwright.sync_api import sync_playwright
    HAS_PLAYWRIGHT = True
except ImportError:
    sync_playwright = None  # type: ignore
    HAS_PLAYWRIGHT = False

try:
    import pyautogui
    pyautogui.FAILSAFE = False  # headless Xvfb — no corner-abort surprise
    HAS_PYAUTOGUI = True
except Exception:  # ImportError or X connection failure at import time
    pyautogui = None  # type: ignore
    HAS_PYAUTOGUI = False

HAS_XDOTOOL = shutil.which("xdotool") is not None

FRAME_W = int(os.environ.get("EYES_WIDTH", "1024"))
FRAME_H = int(os.environ.get("EYES_HEIGHT", "768"))
ALLOWED_ACTIONS = {"click", "type", "key", "scroll", "goto",
                   "wait", "done", "none", "noop"}
NOOP_ACTIONS = {"wait", "done", "none", "noop"}
# Optional shared secret: when set, every endpoint requires
# "Authorization: Bearer <AGENT_TOKEN>" or "X-Agent-Token: <token>".
AGENT_TOKEN = os.environ.get("AGENT_TOKEN", "")
MAX_BODY = int(os.environ.get("HANDS_MAX_BODY", str(1024 * 1024)))  # 1 MB


def authorized(handler: BaseHTTPRequestHandler) -> bool:
    """Optional shared-secret gate — open when AGENT_TOKEN is unset."""
    if not AGENT_TOKEN:
        return True
    auth = handler.headers.get("Authorization", "")
    token = handler.headers.get("X-Agent-Token", "")
    return auth == f"Bearer {AGENT_TOKEN}" or token == AGENT_TOKEN


def auth_headers() -> dict:
    """Headers sibling daemons should attach when AGENT_TOKEN is set."""
    return {"Authorization": f"Bearer {AGENT_TOKEN}"} if AGENT_TOKEN else {}

_KEY_ALIASES = {
    "enter": "enter", "return": "enter", "esc": "escape", "escape": "escape",
    "tab": "tab", "backspace": "backspace", "delete": "delete", "space": "space",
    "up": "up", "down": "down", "left": "left", "right": "right",
    "home": "home", "end": "end", "pageup": "pageup", "pagedown": "pagedown",
}


def _clamp(v: float, hi: int) -> int:
    return int(max(0, min(hi, round(v))))


def _bezier_points(x0: float, y0: float, x1: float, y1: float,
                   steps: int = 25) -> list[tuple[float, float]]:
    """Cubic bezier with two randomized control points — human-ish path."""
    dx, dy = x1 - x0, y1 - y0
    dist = math.hypot(dx, dy) or 1.0
    spread = min(dist * 0.35, 120.0)
    c1 = (x0 + dx * random.uniform(0.2, 0.4) + random.uniform(-spread, spread),
          y0 + dy * random.uniform(0.2, 0.4) + random.uniform(-spread, spread))
    c2 = (x0 + dx * random.uniform(0.6, 0.8) + random.uniform(-spread, spread),
          y0 + dy * random.uniform(0.6, 0.8) + random.uniform(-spread, spread))
    pts = []
    for i in range(steps + 1):
        t = i / steps
        mt = 1 - t
        px = mt**3 * x0 + 3 * mt**2 * t * c1[0] + 3 * mt * t**2 * c2[0] + t**3 * x1
        py = mt**3 * y0 + 3 * mt**2 * t * c1[1] + 3 * mt * t**2 * c2[1] + t**3 * y1
        pts.append((px, py))
    return pts


class Hands:
    """Executes whitelisted actions; lazily connects actuators."""

    def __init__(self, cdp_url: str | None = None) -> None:
        idx = int(os.environ.get("AGENT_INDEX", "1"))
        self.cdp_url = (cdp_url or os.environ.get("CHROME_CDP_URL")
                        or f"http://127.0.0.1:{9200 + idx}")
        self.eyes_url = os.environ.get(
            "EYES_URL", f"http://127.0.0.1:{8700 + idx}").rstrip("/")
        self._pw = None
        self._browser = None
        self._page = None
        self._geo_cache: dict | None = None
        self._geo_at = 0.0

    # -- playwright lane ------------------------------------------------------
    def _reset_pw(self) -> None:
        try:
            if self._pw is not None:
                self._pw.stop()
        except Exception:
            pass
        self._pw = self._browser = self._page = None

    def _get_page(self):
        if not HAS_PLAYWRIGHT:
            return None
        try:
            if self._browser is None:
                # (Re)connect every call until it succeeds — Chrome may start
                # after the hands daemon.
                if self._pw is None:
                    self._pw = sync_playwright().start()
                self._browser = self._pw.chromium.connect_over_cdp(self.cdp_url)
            ctx = self._browser.contexts[0] if self._browser.contexts else None
            if ctx is None:
                return None
            pages = ctx.pages
            if pages:
                self._page = pages[0]
                return self._page
        except Exception as exc:
            print(f"[hands] playwright/CDP unavailable: {exc}", flush=True)
            self._reset_pw()  # drop the half-open session, retry next action
        return self._page

    # -- coordinate mapping ----------------------------------------------------
    def _eyes_geometry(self) -> dict | None:
        """The exact crop/scale/monitor-origin eyes applies (cached ~5s)."""
        now = time.time()
        if self._geo_cache and now - self._geo_at < 5.0:
            return self._geo_cache
        try:
            r = requests.get(f"{self.eyes_url}/geometry",
                             headers=auth_headers(), timeout=5)
            geo = r.json()
            if r.ok and "scale_x" in geo:
                self._geo_cache, self._geo_at = geo, now
        except Exception:
            pass
        return self._geo_cache

    def _display_size(self) -> tuple[int, int]:
        """Native display size for inverse frame->display mapping."""
        if HAS_PYAUTOGUI:
            try:
                size = pyautogui.size()
                return int(size.width), int(size.height)
            except Exception:
                pass
        if HAS_XDOTOOL:
            try:
                out = subprocess.run(
                    ["xdotool", "getdisplaygeometry"],
                    capture_output=True, text=True, timeout=10)
                if out.returncode == 0:
                    w, h = out.stdout.split()[:2]
                    return int(w), int(h)
            except Exception:
                pass
        return FRAME_W, FRAME_H

    def _to_display(self, fx: float, fy: float) -> tuple[int, int]:
        """Inverse of eyes' center-crop+scale: frame px -> display px.

        Prefers eyes' own /geometry — the monitor origin and crop it actually
        used — so secondary monitors map correctly. Falls back to deriving
        the transform from whole-display dimensions (primary monitor).
        """
        geo = self._eyes_geometry()
        if geo:
            return (int(geo["monitor_x0"] + geo["crop_x0"]
                        + fx * geo["scale_x"]),
                    int(geo["monitor_y0"] + geo["crop_y0"]
                        + fy * geo["scale_y"]))
        dw, dh = self._display_size()
        target_ratio = FRAME_W / FRAME_H
        if dw / dh > target_ratio:  # sides were cropped
            crop_w, crop_h, x0, y0 = int(dh * target_ratio), dh, \
                (dw - int(dh * target_ratio)) // 2, 0
        else:  # top/bottom were cropped
            crop_w, crop_h = dw, int(dw / target_ratio)
            x0, y0 = 0, (dh - crop_h) // 2
        return (int(x0 + fx * crop_w / FRAME_W),
                int(y0 + fy * crop_h / FRAME_H))

    @staticmethod
    def _to_viewport(page, dx: int, dy: int) -> tuple[int, int] | None:
        """Display px -> page viewport px, or None when outside the content
        area. Browser chrome/toolbar sit between the frame's top edge and the
        page, so raw scaling is wrong — subtract the window's content origin.
        """
        session = None
        try:
            session = page.context.new_cdp_session(page)
            bounds = session.send("Browser.getWindowForTarget")["bounds"]
        except Exception:
            return None
        finally:
            if session is not None:
                try:
                    session.detach()
                except Exception:
                    pass
        vp = page.viewport_size
        if not vp:
            return None
        ox = int(bounds.get("left", 0))
        oy = int(bounds.get("top", 0)) + (
            int(bounds.get("height", 0)) - int(vp["height"]))
        vx, vy = dx - ox, dy - oy
        if 0 <= vx < vp["width"] and 0 <= vy < vp["height"]:
            return vx, vy
        return None

    # -- pyautogui lane -------------------------------------------------------
    @staticmethod
    def _pg_move(x: int, y: int) -> None:
        x0, y0 = pyautogui.position()
        for px, py in _bezier_points(x0, y0, x, y):
            pyautogui.moveTo(px, py, _pause=False)
            time.sleep(random.uniform(0.002, 0.012))

    # -- xdotool lane ---------------------------------------------------------
    @staticmethod
    def _xdo(*args: str) -> bool:
        if not HAS_XDOTOOL:
            return False
        try:
            subprocess.run(["xdotool", *args], check=True,
                           timeout=10, capture_output=True)
            return True
        except Exception as exc:
            print(f"[hands] xdotool {args[:1]} failed: {exc}", flush=True)
            return False

    # -- individual actions ----------------------------------------------------
    def click(self, x: int, y: int) -> dict:
        fx, fy = _clamp(x, FRAME_W), _clamp(y, FRAME_H)
        dx, dy = self._to_display(fx, fy)
        page = self._get_page()
        if page is not None:
            try:
                vp = self._to_viewport(page, dx, dy)
                if vp is not None:
                    page.mouse.move(vp[0], vp[1],
                                    steps=random.randint(10, 25))
                    page.mouse.click(vp[0], vp[1])
                    return {"ok": True, "via": "playwright", "at": list(vp)}
                # point is outside page content (browser chrome, desktop) —
                # desktop input lands it regardless.
            except Exception:
                self._page = None  # fall through to desktop input
        if HAS_PYAUTOGUI:
            self._pg_move(dx, dy)
            time.sleep(random.uniform(0.05, 0.15))
            pyautogui.click(dx, dy)
            return {"ok": True, "via": "pyautogui", "at": [dx, dy]}
        if self._xdo("mousemove", str(dx), str(dy), "click", "1"):
            return {"ok": True, "via": "xdotool", "at": [dx, dy]}
        return {"ok": False, "error": "no click actuator available"}

    def type(self, text: str) -> dict:
        if not text:
            return {"ok": False, "error": "empty text"}
        page = self._get_page()
        if page is not None:
            try:
                page.keyboard.type(text, delay=random.randint(30, 90))
                return {"ok": True, "via": "playwright", "chars": len(text)}
            except Exception:
                self._page = None
        if HAS_PYAUTOGUI:
            pyautogui.typewrite(text, interval=random.uniform(0.03, 0.09))
            return {"ok": True, "via": "pyautogui", "chars": len(text)}
        if self._xdo("type", "--delay", "50", "--", text):
            return {"ok": True, "via": "xdotool", "chars": len(text)}
        return {"ok": False, "error": "no type actuator available"}

    def key(self, key: str) -> dict:
        k = _KEY_ALIASES.get(key.strip().lower(), key.strip().lower())
        page = self._get_page()
        if page is not None:
            try:
                page.keyboard.press(k)
                return {"ok": True, "via": "playwright", "key": k}
            except Exception:
                self._page = None
        if HAS_PYAUTOGUI:
            pyautogui.press(k)
            return {"ok": True, "via": "pyautogui", "key": k}
        if self._xdo("key", k):
            return {"ok": True, "via": "xdotool", "key": k}
        return {"ok": False, "error": "no key actuator available"}

    def scroll(self, delta_y: int) -> dict:
        delta = int(delta_y or 0)
        page = self._get_page()
        if page is not None:
            try:
                page.mouse.wheel(0, delta)
                return {"ok": True, "via": "playwright", "delta_y": delta}
            except Exception:
                self._page = None
        clicks = max(1, min(20, abs(delta) // 120))
        button = "4" if delta < 0 else "5"  # x11: 4=up, 5=down
        if HAS_PYAUTOGUI:
            pyautogui.scroll(-clicks if delta > 0 else clicks)
            return {"ok": True, "via": "pyautogui", "delta_y": delta}
        if self._xdo("click", "--repeat", str(clicks), button):
            return {"ok": True, "via": "xdotool", "delta_y": delta}
        return {"ok": False, "error": "no scroll actuator available"}

    def goto(self, url: str) -> dict:
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        page = self._get_page()
        if page is not None:
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=20000)
                return {"ok": True, "via": "playwright", "url": page.url}
            except Exception as exc:
                self._page = None
                return {"ok": False, "error": f"goto failed: {exc}"}
        # Desktop fallback: focus chrome's address bar (ctrl+l) and type it.
        focused = self._xdo("key", "ctrl+l")
        if not focused and HAS_PYAUTOGUI:
            try:
                pyautogui.hotkey("ctrl", "l")
                focused = True
            except Exception:
                focused = False
        if focused:
            self.type(url)
            self.key("enter")
            return {"ok": True, "via": "desktop", "url": url}
        return {"ok": False, "error": "goto needs playwright or desktop input"}

    # -- dispatch --------------------------------------------------------------
    def execute(self, action: dict) -> dict:
        if not isinstance(action, dict):
            return {"ok": False, "error": "action must be a JSON object"}
        name = str(action.get("action", "")).strip().lower()
        if name not in ALLOWED_ACTIONS:
            return {"ok": False, "error": f"action {name!r} not whitelisted"}
        if name in NOOP_ACTIONS:
            return {"ok": True, "via": "noop", "action": name,
                    "reason": action.get("reason", "")}
        try:
            if name == "click":
                return self.click(float(action.get("x", 0)),
                                  float(action.get("y", 0)))
            if name == "type":
                return self.type(str(action.get("text", "")))
            if name == "key":
                return self.key(str(action.get("key", "")))
            if name == "scroll":
                return self.scroll(int(action.get("delta_y",
                                                  action.get("y", 240))))
            if name == "goto":
                return self.goto(str(action.get("url",
                                                action.get("text", ""))))
        except Exception as exc:
            return {"ok": False, "action": name, "error": str(exc)}
        return {"ok": False, "error": f"unhandled action {name!r}"}


def serve(hands: Hands, port: int) -> None:
    class Handler(BaseHTTPRequestHandler):
        def _json(self, code: int, obj: dict) -> None:
            body = json.dumps(obj).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self) -> None:  # noqa: N802
            if not authorized(self):
                self._json(401, {"ok": False, "error": "unauthorized"})
                return
            if self.path != "/act":
                self._json(404, {"error": "unknown path"})
                return
            try:
                length = int(self.headers.get("Content-Length", "0") or 0)
            except ValueError:
                self._json(400, {"ok": False, "error": "bad Content-Length"})
                return
            if length > MAX_BODY:
                self._json(413, {"ok": False,
                                 "error": f"body exceeds {MAX_BODY} bytes"})
                return
            try:
                action: Any = json.loads(self.rfile.read(length) or b"{}")
            except Exception as exc:
                self._json(400, {"ok": False, "error": f"bad json: {exc}"})
                return
            self._json(200, hands.execute(action))

        def do_GET(self) -> None:  # noqa: N802
            if not authorized(self):
                self._json(401, {"ok": False, "error": "unauthorized"})
                return
            if self.path == "/health":
                self._json(200, {
                    "ok": True,
                    "playwright": HAS_PLAYWRIGHT,
                    "pyautogui": HAS_PYAUTOGUI,
                    "xdotool": HAS_XDOTOOL,
                    "cdp_url": hands.cdp_url,
                })
            else:
                self._json(404, {"error": "unknown path",
                                 "paths": ["/act", "/health"]})

        def log_message(self, fmt, *args) -> None:
            pass

    print(f"[hands] playwright={HAS_PLAYWRIGHT} pyautogui={HAS_PYAUTOGUI} "
          f"xdotool={HAS_XDOTOOL} cdp={hands.cdp_url} "
          f"listening on 127.0.0.1:{port}", flush=True)
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()


def main() -> int:
    idx = int(os.environ.get("AGENT_INDEX", "1"))
    port = int(os.environ.get("HANDS_PORT", "0") or 0) or 8500 + idx
    serve(Hands(), port)
    return 0


if __name__ == "__main__":
    sys.exit(main())
