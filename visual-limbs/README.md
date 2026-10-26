# visual-limbs

Per-desktop agent runtime for the P2P/OmegaGO agent mesh — the **eyes + hands
+ voice** layer that sits on each agent desktop and talks to the shared brain
card.

```
            ┌────────────────────────── agent desktop N ─────────────────────────┐
            │  Xvfb :N ──► eyes.py ──► parser_client ──► brain_client ──► hands  │
            │   screen     mss diff      OmniParser/       qwen-vl        Chrome  │
            │   frames     1024x768      YOLO boxes        action JSON    CDP /   │
            │                                                          pyautogui│
            │  aider_loop: tmux aider (architect→editor) + app reload + console   │
            │  livekit_participant: screen-share track out, audio in            │
            └──────────────────────────────────────────────────────────────────┘
                    │                                    ▲
                    ▼                                    │
   OmniParser endpoint            Brain card 96GB PRO 6000 (OpenAI-compatible)
   OMNIPARSER_URL                 LiteLLM :8000 · qwen-coder :8081 · gemma :8082
                                  qwen2.5-vl :8083 · bge-m3 :8084
```

## Files

| File | Role |
|---|---|
| `agent/eyes.py` | mss screen-diff watcher on `$DISPLAY`; emits 1024x768 JPEGs only when pixels change. Serves `GET /frame` (latest JPEG), `GET /seq`, `GET /health`. |
| `agent/parser_client.py` | POSTs frames to `OMNIPARSER_URL` (OmniParser/YOLO11), normalizes labeled UI boxes. Falls back to raw frame when the parser is down. Optional daemon: `POST /parse`, `GET /boxes`. |
| `agent/brain_client.py` | Sends frame+boxes to the vision lane (OpenAI-compatible `BRAIN_URL`, model `qwen-vl`) for action JSON. Retries to `BRAIN_OVERFLOW_URL` (OpenRouter) on timeout/429/503. Daemon = the perception loop (eyes → parser → brain → hands) with `GET /last`, `POST /instruction`. |
| `agent/hands.py` | Executes action JSON. Playwright-over-CDP first, PyAutoGUI humanized bezier mouse + typewrite fallback, xdotool last resort. Daemon: `POST /act`, `GET /health`. |
| `agent/aider_loop.py` | tmux-managed aider in `--architect` mode (OpenRouter architect + local qwen-coder editor). After edits land it reloads the app in agent Chrome, captures screenshot + console logs, and feeds a bug report back to aider. Non-stop, exponential backoff. |
| `agent/livekit_participant.py` | Joins the LiveKit room as `agentNNN`, publishes the screen as a share track, subscribes to audio. No-ops cleanly without the `livekit` package. |
| `agent/run.sh` | Launcher: `./run.sh <AGENT_INDEX>` wires every limb for one desktop. |
| `agent/requirements.txt` | Pinned minimal deps. `pyautogui` and `livekit` are optional — imports are guarded so missing extras degrade instead of crashing. |

## Per-agent port map (AGENT_INDEX = N, 1–100)

| Thing | Port/host |
|---|---|
| Xvfb display | `:$N` |
| x11vnc | `5900+N` |
| noVNC | `6080+N` |
| Chrome CDP | `9200+N` |
| hands daemon (`/act`) | `8500+N` |
| eyes server (`/frame`, `/seq`) | `8700+N` |
| parser daemon (`/parse`) | `8800+N` |
| brain status (`/last`, `/instruction`) | `8900+N` |

Mesh side: LiveKit `ws://<control>:7880` (RTC 7881, UDP 50000-60000, SIP 5060);
LiteLLM router `http://<control>:8000/v1`; qwen-coder `:8081`, gemma `:8082`,
qwen-vl `:8083`, bge-m3 `:8084`; LiteLLM/Argon gateway `http://127.0.0.1:8090`.

## Env vars

| Var | Default | Purpose |
|---|---|---|
| `AGENT_INDEX` | `1` | Agent number; derives DISPLAY and all ports. |
| `DISPLAY` | `:$AGENT_INDEX` | X display to watch/drive. |
| `EYES_PORT` / `HANDS_PORT` / `PARSER_PORT` / `BRAIN_PORT` | `8700/8500/8800/8900 + N` | Local daemon ports. |
| `EYES_URL` / `HANDS_URL` / `CHROME_CDP_URL` | `127.0.0.1:<port above>` | Limb endpoints / agent Chrome. |
| `EYES_PIXEL_THRESHOLD` | `12` | Per-pixel abs-diff (0–255) that counts as changed. |
| `EYES_CHANGED_FRACTION` | `0.002` | Fraction of changed pixels needed to emit a frame. |
| `EYES_POLL_INTERVAL` | `0.25` | Capture poll seconds. `EYES_WIDTH`/`EYES_HEIGHT` = frame size (1024x768). |
| `OMNIPARSER_URL` | unset | OmniParser/YOLO endpoint base. Unset/down → raw frames only. |
| `PARSER_TIMEOUT` | `10` | Parser call timeout (s). |
| `BRAIN_URL` | unset | OpenAI-compatible base for the vision model (e.g. `http://<control>:8000/v1` via LiteLLM, or `http://<brain>:8083/v1` direct). |
| `BRAIN_MODEL` | `qwen-vl` | Model name on `BRAIN_URL`. |
| `BRAIN_API_KEY` | `sk-local` | Bearer for `BRAIN_URL` (LiteLLM master/virtual key). |
| `BRAIN_TIMEOUT` | `60` | Brain call timeout (s). |
| `BRAIN_OVERFLOW_URL` | unset | OpenRouter base (`https://openrouter.ai/api/v1`) for overflow when the primary is full/down. |
| `BRAIN_OVERFLOW_MODEL` | `qwen/qwen2.5-vl-32b-instruct` | Overflow model id. |
| `BRAIN_OVERFLOW_API_KEY` | unset | OpenRouter key — **env only, never hardcode**. |
| `AGENT_INSTRUCTION` | `Wait for further instructions.` | Goal the brain acts toward; also settable live via `POST /instruction`. |
| `BRAIN_POLL_INTERVAL` | `0.5` | Loop poll seconds. |
| `AIDER_WORKDIR` | unset | Directory aider edits. Required for the aider limb. |
| `AIDER_APP_URL` | unset | App URL reloaded for visual verification. Required for the aider limb. |
| `AIDER_TASK` | unset | Initial instruction sent to aider on start. |
| `ARCHITECT_MODEL` | `anthropic/claude-sonnet-4` | OpenRouter model id for aider `--model`. |
| `OPENROUTER_API_KEY` | unset | OpenRouter key for the architect — env only. |
| `AIDER_BIN` | `aider` | aider executable. `AIDER_IDLE_SECONDS` = quiet period before app check (20). |
| `LIVEKIT_URL` / `LIVEKIT_TOKEN` | unset | Room ws URL + join token. Both required for the voice lane. |
| `LIVEKIT_IDENTITY` | `agentNNN` | Participant name. `LIVEKIT_FPS` = share rate (2). |

## Action JSON contract

The brain returns exactly one JSON object (fences/prose stripped by
`brain_client`). `hands.py` executes only whitelisted actions and clamps
coordinates to the 1024x768 frame:

```json
{
  "action": "click | type | key | scroll | goto | wait | done | none",
  "x": 512,              // int, 0-1024  (click)
  "y": 384,              // int, 0-768   (click)
  "text": "hello",       // string       (type; also used as goto URL fallback)
  "key": "enter",        // key name or chord (key)
  "delta_y": 240,        // int px       (scroll; +down / -up)
  "url": "https://...",  // string       (goto)
  "reason": "why this action"
}
```

- **click** — move to `x,y` (bezier path on the pyautogui lane) then left-click.
- **type** — type `text` into whatever has focus.
- **key** — press `key` (`enter`, `tab`, `esc`, arrows, `ctrl+l`, …).
- **scroll** — mouse wheel `delta_y` pixels.
- **goto** — navigate the agent Chrome to `url`.
- **wait / done / none** — accepted no-ops (loop pauses next frame anyway).

`POST /act` response: `{"ok": true, "via": "playwright|pyautogui|xdotool|noop", ...}`
or `{"ok": false, "error": "..."}` — including `action '<x>' not whitelisted`.

## Run

```bash
cd visual-limbs/agent
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt        # core + playwright
playwright install chromium            # once, for the CDP lane

# per agent N (desktop :N, chrome --remote-debugging-port=9200+N already up):
AGENT_INDEX=1 \
BRAIN_URL=http://127.0.0.1:8000/v1 \
OMNIPARSER_URL=http://127.0.0.1:8901 \
AGENT_INSTRUCTION="Open the dashboard and click Deploy" \
./run.sh 1

# optional lanes:
START_PARSER=1                          # standalone parser daemon
OPENROUTER_API_KEY=... AIDER_WORKDIR=/srv/app AIDER_APP_URL=http://127.0.0.1:3000 \
  ./run.sh 1                            # + aider limb
LIVEKIT_URL=ws://<control>:7880 LIVEKIT_TOKEN=... ./run.sh 1   # + voice
```

Sanity checks:

```bash
curl -s http://127.0.0.1:8701/health          # eyes emitting?
curl -s http://127.0.0.1:8701/frame -o f.jpg  # latest 1024x768 jpeg
curl -s http://127.0.0.1:8501/health          # which actuators are live
curl -s http://127.0.0.1:8901/last            # last brain action + result
curl -s -XPOST http://127.0.0.1:8501/act \
     -d '{"action":"click","x":100,"y":100}'  # poke the hands directly
```

## Graceful degradation

- `livekit` package missing → voice lane logs and exits 0; everything else runs.
- `pyautogui` missing → hands use playwright → xdotool.
- `OMNIPARSER_URL` unset/down → brain sees the raw frame with `boxes: []`.
- `BRAIN_URL` timeout / 429 / 503 → one retry against `BRAIN_OVERFLOW_URL`.
- Display hiccups → eyes keeps polling instead of dying.

All secrets come from env vars only — nothing is hardcoded.
