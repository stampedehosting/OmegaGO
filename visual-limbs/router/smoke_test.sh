#!/usr/bin/env bash
# smoke_test.sh — curl every public endpoint of the visual-limbs router.
# Exits non-zero if any check fails.
#
# Env:
#   ROUTER_URL         default http://127.0.0.1:8000
#   HEALTH_URL         default http://127.0.0.1:8010
#   ROUTER_API_KEY     a virtual key (sk-omega-agentNNN) or LITELLM_MASTER_KEY
#   LITELLM_MASTER_KEY used as fallback for ROUTER_API_KEY
#   SMOKE_SKIP_MODELS  set to 1 to only check liveness, not real model calls

set -uo pipefail

ROUTER_URL="${ROUTER_URL:-http://127.0.0.1:8000}"
HEALTH_URL="${HEALTH_URL:-http://127.0.0.1:8010}"
API_KEY="${ROUTER_API_KEY:-${LITELLM_MASTER_KEY:-}}"
SKIP_MODELS="${SMOKE_SKIP_MODELS:-0}"

fail=0

check() { # name url expected_substring [curl extra args...]
  local name="$1" url="$2" expect="$3"; shift 3
  local out
  out=$(curl -sS -m 15 "$@" "$url" 2>&1)
  if [[ $? -ne 0 ]]; then
    echo "FAIL  $name  (curl error: $out)"; fail=1; return
  fi
  if grep -qi "$expect" <<<"$out"; then
    echo "PASS  $name"
  else
    echo "FAIL  $name  (missing '$expect' in: ${out:0:300})"; fail=1
  fi
}

chat() { # public-model-name
  local model="$1"
  check "chat:$model" "$ROUTER_URL/v1/chat/completions" '"content"\|"choices"' \
    -X POST -H "Authorization: Bearer $API_KEY" -H "Content-Type: application/json" \
    -d "{\"model\":\"$model\",\"messages\":[{\"role\":\"user\",\"content\":\"reply with the word ok\"}],\"max_tokens\":8}"
}

echo "== router liveness =="
check "liveliness"   "$ROUTER_URL/health/liveliness" "alive"
check "model list"   "$ROUTER_URL/v1/models" '"qwen-coder"' -H "Authorization: Bearer $API_KEY"

echo "== health sidecar =="
check "router_health" "$HEALTH_URL/health" '"backends"\|"status"'

if [[ "$SKIP_MODELS" != "1" ]]; then
  if [[ -z "$API_KEY" ]]; then
    echo "SKIP  model calls (set ROUTER_API_KEY or LITELLM_MASTER_KEY)"
  else
    echo "== model calls (lane resolution exercised) =="
    chat qwen-coder
    chat gemma
    chat qwen-vl
    check "embed:bge-m3" "$ROUTER_URL/v1/embeddings" '"data"\|"embedding"' \
      -X POST -H "Authorization: Bearer $API_KEY" -H "Content-Type: application/json" \
      -d '{"model":"bge-m3","input":"smoke test"}'
  fi
fi

if [[ $fail -eq 0 ]]; then echo "smoke: all checks passed"; else echo "smoke: FAILURES above"; fi
exit $fail
