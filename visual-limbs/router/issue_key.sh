#!/usr/bin/env bash
# issue_key.sh — mint a per-agent LiteLLM virtual key (sk-omega-agentNNN)
# and append it to keys.jsonl.
#
# Usage:
#   ./issue_key.sh                  # auto-assigns next agentNNN from keys.jsonl
#   ./issue_key.sh agent007         # explicit agent id -> sk-omega-agent007
#   ./issue_key.sh agent007 qwen-coder qwen-vl   # restrict to these public models
#
# Env:
#   ROUTER_URL          default http://127.0.0.1:8000
#   LITELLM_MASTER_KEY  required (admin auth for /key/generate)
#   KEYS_FILE           default ./keys.jsonl next to this script
#   KEY_MAX_BUDGET      optional, e.g. 5.00 (USD); empty = unlimited
#   KEY_DURATION        optional, e.g. 30d; empty = never expires
#
# Requires the router to run with DATABASE_URL set — /key/generate persists
# virtual keys in the LiteLLM Postgres store.

set -euo pipefail

ROUTER_URL="${ROUTER_URL:-http://127.0.0.1:8000}"
KEYS_FILE="${KEYS_FILE:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/keys.jsonl}"
KEY_MAX_BUDGET="${KEY_MAX_BUDGET:-}"
KEY_DURATION="${KEY_DURATION:-}"

if [[ -z "${LITELLM_MASTER_KEY:-}" ]]; then
  echo "error: LITELLM_MASTER_KEY is not set" >&2
  exit 1
fi
command -v curl >/dev/null || { echo "error: curl not found" >&2; exit 1; }
command -v jq   >/dev/null || { echo "error: jq not found" >&2; exit 1; }

AGENT_ID="${1:-}"
shift || true

# Agent keys may only ever be scoped to the public model names. The
# -openrouter/-fleet deployments are router-internal: a key that could call
# them directly would bypass the waterfall and incur paid OpenRouter charges.
PUBLIC_MODELS=(qwen-coder gemma qwen-vl bge-m3)
MODELS=("$@")
if [[ ${#MODELS[@]} -eq 0 ]]; then
  MODELS=("${PUBLIC_MODELS[@]}")
else
  for m in "${MODELS[@]}"; do
    [[ " ${PUBLIC_MODELS[*]} " == *" $m "* ]] || {
      echo "error: '$m' is not a public model (allowed: ${PUBLIC_MODELS[*]})" >&2
      exit 1
    }
  done
fi

# Auto-number: next agentNNN after the highest alias already in keys.jsonl.
if [[ -z "$AGENT_ID" ]]; then
  next=1
  if [[ -f "$KEYS_FILE" ]]; then
    last=$(jq -r '.key_alias // empty' "$KEYS_FILE" 2>/dev/null \
      | grep -oE 'agent[0-9]+$' | grep -oE '[0-9]+$' | sort -n | tail -1 || true)
    [[ -n "$last" ]] && next=$((10#$last + 1))
  fi
  AGENT_ID=$(printf 'agent%03d' "$next")
fi

KEY_ALIAS="sk-omega-${AGENT_ID}"

# Idempotent: refuse to double-issue an alias that is already recorded.
if [[ -f "$KEYS_FILE" ]] && jq -e --arg a "$KEY_ALIAS" 'select(.key_alias==$a)' "$KEYS_FILE" >/dev/null 2>&1; then
  echo "error: $KEY_ALIAS already issued (see $KEYS_FILE)" >&2
  exit 1
fi

body=$(jq -n \
  --arg alias "$KEY_ALIAS" \
  --argjson models "$(printf '%s\n' "${MODELS[@]}" | jq -R . | jq -s .)" \
  --arg budget "$KEY_MAX_BUDGET" \
  --arg duration "$KEY_DURATION" \
  '{key_alias: $alias, models: $models}
   + (if $budget   != "" then {max_budget: ($budget|tonumber)} else {} end)
   + (if $duration != "" then {duration: $duration}            else {} end)')

resp=$(curl -sfS -X POST "$ROUTER_URL/key/generate" \
  -H "Authorization: Bearer $LITELLM_MASTER_KEY" \
  -H "Content-Type: application/json" \
  -d "$body")

key=$(jq -r '.key // empty' <<<"$resp")
if [[ -z "$key" ]]; then
  echo "error: /key/generate returned no key: $resp" >&2
  exit 1
fi

touch "$KEYS_FILE" && chmod 600 "$KEYS_FILE"
jq -cn \
  --arg ts "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --arg alias "$KEY_ALIAS" \
  --arg key "$key" \
  --argjson models "$(printf '%s\n' "${MODELS[@]}" | jq -R . | jq -s .)" \
  '{issued_at: $ts, key_alias: $alias, key: $key, models: $models}' \
  >> "$KEYS_FILE"

echo "$KEY_ALIAS -> $key (models: ${MODELS[*]}) appended to $KEYS_FILE"
