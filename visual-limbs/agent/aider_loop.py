#!/usr/bin/env python3
"""aider_loop.py — tmux-managed headless aider coding loop.

Runs aider in architect mode inside a tmux session on the agent desktop:

  architect model : OpenRouter (Claude/Argon) — plans & specs
  editor model    : local qwen-coder via BRAIN_URL (OpenAI-compatible :8081)

Loop:
  1. ensure the tmux session + aider process is up (restart if dead)
  2. watch the workdir for file modifications made by aider
  3. reload AIDER_APP_URL in the agent's Chrome (CDP), capture a screenshot
     and console logs
  4. feed a text visual-bug report back into aider's stdin via tmux send-keys
  5. repeat forever; exponential backoff (cap 5 min) on failures

Env:
  AGENT_INDEX          agent number (tmux session agentNNN-aider)
  AIDER_WORKDIR        repo/dir aider edits in (required to run)
  AIDER_APP_URL        app URL to reload for verification (required)
  AIDER_TASK           initial instruction sent to aider on start
  ARCHITECT_MODEL      openrouter model id (default anthropic/claude-sonnet-4)
  OPENROUTER_API_KEY   required (env only — never hardcoded)
  BRAIN_URL            editor model base URL (default http://127.0.0.1:8081/v1)
  BRAIN_MODEL          editor model name (default qwen-coder)
  CHROME_CDP_URL       agent chrome (default http://127.0.0.1:9200+N)
  AIDER_BIN            aider executable (default "aider")
  AIDER_IDLE_SECONDS   idle time before checking the app (default 20)
"""

import os
import subprocess
import sys
import time
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright
    HAS_PLAYWRIGHT = True
except ImportError:
    sync_playwright = None  # type: ignore
    HAS_PLAYWRIGHT = False

IDX = int(os.environ.get("AGENT_INDEX", "1"))
SESSION = f"agent{IDX:03d}-aider"
WORKDIR = Path(os.environ.get("AIDER_WORKDIR", ""))
APP_URL = os.environ.get("AIDER_APP_URL", "")
TASK = os.environ.get("AIDER_TASK", "")
ARCHITECT_MODEL = os.environ.get("ARCHITECT_MODEL",
                                 "anthropic/claude-sonnet-4")
BRAIN_URL = os.environ.get("BRAIN_URL", "http://127.0.0.1:8081/v1")
BRAIN_MODEL = os.environ.get("BRAIN_MODEL", "qwen-coder")
CDP_URL = os.environ.get("CHROME_CDP_URL", f"http://127.0.0.1:{9200 + IDX}")
AIDER_BIN = os.environ.get("AIDER_BIN", "aider")
IDLE_SECONDS = float(os.environ.get("AIDER_IDLE_SECONDS", "20"))
BACKOFF_MAX = 300.0


def tmux(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["tmux", *args], capture_output=True, text=True)


def session_alive() -> bool:
    return tmux("has-session", "-t", SESSION).returncode == 0


def aider_running() -> bool:
    out = tmux("list-panes", "-t", SESSION, "-F", "#{pane_current_command}")
    return "aider" in out.stdout


def start_session() -> None:
    env = (
        f"OPENROUTER_API_KEY='{os.environ.get('OPENROUTER_API_KEY', '')}' "
        f"OPENAI_API_BASE='{BRAIN_URL}' "
        f"OPENAI_API_KEY='{os.environ.get('BRAIN_API_KEY', 'sk-local')}'"
    )
    cmd = (
        f"{env} {AIDER_BIN} --architect "
        f"--model 'openrouter/{ARCHITECT_MODEL}' "
        f"--editor-model 'openai/{BRAIN_MODEL}' "
        f"--no-auto-commits --yes-always --dark-mode"
    )
    tmux("new-session", "-d", "-s", SESSION, "-c", str(WORKDIR), cmd)
    print(f"[aider] started tmux session {SESSION} in {WORKDIR}", flush=True)


def send_to_aider(text: str) -> None:
    """Type a message into aider's prompt and hit enter."""
    # send-keys with -l types literally (no key name interpretation)
    tmux("send-keys", "-t", SESSION, "-l", text)
    tmux("send-keys", "-t", SESSION, "Enter")


def snapshot_mtimes(root: Path) -> dict[str, float]:
    mtimes: dict[str, float] = {}
    skip = {".git", ".aider", "node_modules", "__pycache__", ".venv"}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in skip]
        for f in filenames:
            p = Path(dirpath) / f
            try:
                mtimes[str(p)] = p.stat().st_mtime
            except OSError:
                pass
    return mtimes


def capture_app_state() -> tuple[str, list[str]]:
    """Reload APP_URL in agent chrome; return (screenshot_path, console logs)."""
    if not (HAS_PLAYWRIGHT and APP_URL):
        return "", ["playwright unavailable or AIDER_APP_URL unset"]
    logs: list[str] = []
    shot = f"/tmp/{SESSION}-shot.png"
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.connect_over_cdp(CDP_URL)
            ctx = browser.contexts[0] if browser.contexts else \
                browser.new_context()
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            page.on("console",
                    lambda m: logs.append(f"[{m.type}] {m.text}"))
            page.on("pageerror", lambda e: logs.append(f"[pageerror] {e}"))
            page.goto(APP_URL, wait_until="networkidle", timeout=30000)
            page.wait_for_timeout(1500)
            page.screenshot(path=shot)
            return shot, logs[-50:]
    except Exception as exc:
        return "", [f"capture failed: {exc}"]


def build_bug_report(shot: str, logs: list[str]) -> str:
    lines = [
        "Visual verification report from the live app (automated check):",
        f"- App URL: {APP_URL}",
    ]
    if shot:
        lines.append(f"- Screenshot captured at {shot} "
                     f"(inspect with /read-only {shot} if useful).")
    if logs:
        lines.append("- Browser console output:")
        lines.extend(f"    {l}" for l in logs)
    else:
        lines.append("- Console: clean, no errors or warnings.")
    lines.append("If anything looks broken, fix it; otherwise say DONE.")
    return "\n".join(lines)


def main() -> int:
    if not WORKDIR or not WORKDIR.is_dir():
        print(f"[aider] AIDER_WORKDIR {WORKDIR!r} missing — exiting.", flush=True)
        return 1
    if not APP_URL:
        print("[aider] AIDER_APP_URL unset — exiting.", flush=True)
        return 1

    backoff = 5.0
    baseline: dict[str, float] = {}
    while True:
        try:
            if not session_alive() or not aider_running():
                start_session()
                time.sleep(8)  # let aider boot
                if TASK:
                    send_to_aider(TASK)
                baseline = snapshot_mtimes(WORKDIR)
            else:
                current = snapshot_mtimes(WORKDIR)
                changed = {p for p, m in current.items()
                           if baseline.get(p) != m}
                if changed and _idle(IDLE_SECONDS, current):
                    shot, logs = capture_app_state()
                    send_to_aider(build_bug_report(shot, logs))
                    baseline = snapshot_mtimes(WORKDIR)
                    time.sleep(5)
            backoff = 5.0
            time.sleep(5)
        except Exception as exc:
            print(f"[aider] error: {exc} (retry in {backoff:.0f}s)", flush=True)
            time.sleep(backoff)
            backoff = min(backoff * 2, BACKOFF_MAX)


def _idle(seconds: float, mtimes: dict[str, float]) -> bool:
    """True if the newest file change is older than `seconds`."""
    newest = max(mtimes.values(), default=0.0)
    return (time.time() - newest) >= seconds


if __name__ == "__main__":
    sys.exit(main())
