#!/usr/bin/env bash
# run.sh — launch one visual-limbs agent for a given AGENT_INDEX.
#
#   ./run.sh <AGENT_INDEX>     (default AGENT_INDEX=1)
#
# Port/display scheme per agent N (matches the fleet blueprint):
#   DISPLAY        :N            Xvfb desktop
#   x11vnc         5900+N        (external, not started here)
#   noVNC          6080+N        (external)
#   Chrome CDP     9200+N        chrome --remote-debugging-port
#   hands daemon   8500+N        POST /act
#   eyes server    8700+N        GET /frame /seq /health
#   parser server  8800+N        POST /parse (only if START_PARSER=1)
#   brain status   8900+N        GET /last, POST /instruction
#
# Required env for full function (see ../README.md):
#   BRAIN_URL, OMNIPARSER_URL, AGENT_INSTRUCTION, OPENROUTER_API_KEY,
#   AIDER_WORKDIR, AIDER_APP_URL, LIVEKIT_URL, LIVEKIT_TOKEN
set -euo pipefail

AGENT_INDEX="${1:-${AGENT_INDEX:-1}}"
export AGENT_INDEX
export DISPLAY="${DISPLAY:-:$AGENT_INDEX}"

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="${LOG_DIR:-$DIR/logs}"
mkdir -p "$LOG_DIR"

export EYES_PORT="${EYES_PORT:-$((8700 + AGENT_INDEX))}"
export HANDS_PORT="${HANDS_PORT:-$((8500 + AGENT_INDEX))}"
export PARSER_PORT="${PARSER_PORT:-$((8800 + AGENT_INDEX))}"
export BRAIN_PORT="${BRAIN_PORT:-$((8900 + AGENT_INDEX))}"
export CHROME_CDP_URL="${CHROME_CDP_URL:-http://127.0.0.1:$((9200 + AGENT_INDEX))}"
export EYES_URL="${EYES_URL:-http://127.0.0.1:$EYES_PORT}"
export HANDS_URL="${HANDS_URL:-http://127.0.0.1:$HANDS_PORT}"

PY="${PYTHON:-python3}"
PIDS=()

start() {  # start <name> <cmd...>
    local name="$1"; shift
    echo "[run] starting $name (agent$AGENT_INDEX)"
    "$@" >>"$LOG_DIR/$name.log" 2>&1 &
    PIDS+=($!)
}

cleanup() {
    echo "[run] stopping agent$AGENT_INDEX"
    kill "${PIDS[@]}" 2>/dev/null || true
}
trap cleanup INT TERM EXIT

# eyes + hands are the always-on limbs.
start eyes   "$PY" "$DIR/eyes.py"
sleep 1
start hands  "$PY" "$DIR/hands.py"

# parser daemon is optional — brain_client calls OMNIPARSER_URL directly too.
if [ "${START_PARSER:-0}" = "1" ]; then
    start parser "$PY" "$DIR/parser_client.py"
fi

# brain loop: eyes -> parser -> brain -> hands.
start brain  "$PY" "$DIR/brain_client.py"

# aider coding limb — only when a workdir + app URL are configured.
if [ -n "${AIDER_WORKDIR:-}" ] && [ -n "${AIDER_APP_URL:-}" ]; then
    start aider "$PY" "$DIR/aider_loop.py"
else
    echo "[run] AIDER_WORKDIR/AIDER_APP_URL unset — aider limb skipped"
fi

# voice lane — degrades to a no-op if livekit deps/env are missing.
if [ -n "${LIVEKIT_URL:-}" ] && [ -n "${LIVEKIT_TOKEN:-}" ]; then
    start livekit "$PY" "$DIR/livekit_participant.py"
else
    echo "[run] LIVEKIT_URL/LIVEKIT_TOKEN unset — voice lane skipped"
fi

echo "[run] agent$AGENT_INDEX limbs up on DISPLAY=$DISPLAY"
echo "[run] eyes=$EYES_URL hands=$HANDS_URL brain-status=http://127.0.0.1:$BRAIN_PORT"
wait
