# visual-limbs/router — master LiteLLM gateway

The single OpenAI-compatible front door for the OmegaGO agent mesh. Agents call
public model names (`qwen-coder`, `gemma`, `qwen-vl`, `bge-m3`); the router
walks a **3-lane waterfall**:

```
request ─▶ lane 1: brain card (local GPU, free)         http://127.0.0.1:808x
            │  error / timeout (queue saturation) / cooled down
            ▼
           lane 2: OpenRouter overflow (paid)           openrouter/*
            │  error (or OpenRouter key unset)
            ▼
           lane 3: parked media fleet (spare GPU hosts) FLEET_*_URL env vars
```

Lane 2 is skipped automatically for `bge-m3` — OpenRouter exposes no
embeddings API, so embeddings go local → fleet.

Retries: each lane gets `num_retries` attempts; after `allowed_fails`
consecutive errors a deployment is cooled down for `cooldown_time` seconds
and traffic falls through to the next lane.

## Files

| File | Purpose |
|---|---|
| `litellm_config.yaml` | model list, lane wiring, fallbacks, retry/cooldown policy |
| `issue_key.sh` | mint per-agent virtual keys (`sk-omega-agentNNN`) via `/key/generate`, appends `keys.jsonl` |
| `router_health.py` | FastAPI sidecar: per-backend slot saturation (`/health`, `/backends`) |
| `smoke_test.sh` | curls liveness, model list, one chat + one embed call per public name |
| `omegago-litellm-router.service` | systemd unit for the gateway (port 8000) |
| `omegago-router-health.service` | systemd unit for the health sidecar (port 8010) |
| `router.env.example` | env template → copy to `/etc/omegago/router.env` |
| `requirements.txt` | pinned Python deps |

## Ports

| Port | What |
|---|---|
| 8000 | LiteLLM router — OpenAI-compatible API + `/key/generate` admin |
| 8010 | `router_health.py` — `/health`, `/health/live`, `/backends` |
| 8081 | lane-1 `qwen-coder-32b` (32 parallel) |
| 8082 | lane-1 `gemma-31b` (48 parallel) |
| 8083 | lane-1 `qwen2.5-vl-32b` vision (24 parallel) |
| 8084 | lane-1 `bge-m3` embeddings |
| 8090 | Argon gateway on the control box (upstream of this router; not managed here) |

## Env vars (`/etc/omegago/router.env`, see `router.env.example`)

| Var | Required | Purpose |
|---|---|---|
| `LITELLM_MASTER_KEY` | yes | admin bearer for `/key/generate`; also usable as `ROUTER_API_KEY` |
| `OPENROUTER_API_KEY` | lane 2 | OpenRouter key; unset = lane 2 deployments just fail over to lane 3 |
| `DATABASE_URL` | for keys | LiteLLM Postgres DSN — required for `/key/generate` (virtual keys persist there) |
| `FLEET_QWEN_CODER_URL` / `FLEET_GEMMA_URL` / `FLEET_QWEN_VL_URL` / `FLEET_BGE_M3_URL` | lane 3 | OpenAI-compatible base URLs (`http://host:port/v1`) on parked fleet hosts |
| `ROUTER_URL` | scripts | default `http://127.0.0.1:8000` |
| `ROUTER_HEALTH_HOST` / `ROUTER_HEALTH_PORT` | no | sidecar bind, default `127.0.0.1:8010` |
| `HEALTH_PROBE_TIMEOUT` / `HEALTH_SATURATION_WARN` | no | probe timeout secs (2.5) and saturation warn threshold (0.9) |
| `ROUTER_API_KEY`, `KEY_MAX_BUDGET`, `KEY_DURATION`, `KEYS_FILE` | no | script overrides |

Local backends ignore bearer auth by default (`api_key: "EMPTY"` in the
config). If you start vLLM/llama-server with `--api-key`, put a real value in
the config deployments instead — still via env, never hard-coded.

## Run

```bash
# 1. venv + deps
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt

# 2. secrets
sudo mkdir -p /etc/omegago
sudo cp router.env.example /etc/omegago/router.env
sudoedit /etc/omegago/router.env   # set LITELLM_MASTER_KEY, OPENROUTER_API_KEY, ...
sudo chmod 600 /etc/omegago/router.env
source /etc/omegago/router.env     # for manual runs / smoke tests

# 3a. manual
.venv/bin/litellm --config litellm_config.yaml --host 127.0.0.1 --port 8000
.venv/bin/python router_health.py

# 3b. systemd
sudo cp omegago-litellm-router.service omegago-router-health.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now omegago-litellm-router omegago-router-health
```

## Agent keys

```bash
./issue_key.sh                    # -> sk-omega-agent001 (auto-numbered)
./issue_key.sh agent042 qwen-vl   # explicit id, vision-only key
cat keys.jsonl                    # one JSON line per issued key
```

Requires `DATABASE_URL` set — `/key/generate` writes to LiteLLM's Postgres
store. Without it the router still proxies fine; key issuance just fails.

## Verify

```bash
./smoke_test.sh                   # needs LITELLM_MASTER_KEY or ROUTER_API_KEY
SMOKE_SKIP_MODELS=1 ./smoke_test.sh   # liveness only, no paid lane calls
curl -s localhost:8010/health | jq    # slot saturation per backend
```

Agents then point at `http://<router-host>:8000/v1` with their
`sk-omega-agentNNN` key and ask for `qwen-coder`, `gemma`, `qwen-vl`, or
`bge-m3` — the waterfall is invisible to them.
