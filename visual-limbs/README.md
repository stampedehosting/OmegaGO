# visual-limbs — P2P/OmegaGO agent mesh (eyes + hands)

Part of the OmegaGO "Visual Limbs" architecture: Cloudflare edge routing in
front of the control plane (Contabo), the GPU brain, and fleets of disposable
agent desktops.

## Layout

| Path | Component | Stack |
|---|---|---|
| `edge/` | Cloudflare Worker edge router (`/token`, `/mesh/*`, `/assets/*`, `/health`) | Workers + R2, zero deps beyond wrangler |

## Env vars

Worker-side (see `edge/README.md` for the full contract):

| Var / secret | Where | Purpose |
|---|---|---|
| `LIVEKIT_API_KEY` | wrangler secret | LiveKit token issuer |
| `LIVEKIT_API_SECRET` | wrangler secret | LiveKit token signing (HS256) |
| `LIVEKIT_URL` | var | `wss://` URL echoed to clients (LiveKit `:7880`) |
| `EDGE_AUTH_TOKEN` | wrangler secret | Bearer/`?access_token=` gate on `/token` + `/mesh/*` (closed by default) |
| `EDGE_OPEN` | var | dev-only opt-in to run unauthenticated (`"true"`) |
| `ROOM_PREFIX` | var | optional room allowlist prefix for `/token` |
| `CONTABO_URL` | var | fallback control node for `/mesh/*` |
| `NODES_JSON` | var | `{"name":"url"}` map of control nodes to latency-race |
| `PROBE_PATH` / `PROBE_TIMEOUT_MS` / `PROBE_CACHE_MS` | var | node-selection tuning |
| `ASSETS` | R2 binding | asset bucket behind `/assets/*` |

## Ports (mesh reference)

| Port(s) | Where | Service |
|---|---|---|
| 8787 | edge dev | `wrangler dev` local server |
| 8000 | brain / control | LiteLLM router (master API) |
| 8090 | control box | LiteLLM/Argon gateway |
| 8081–8084 | brain card (96GB PRO 6000) | qwen-coder-32b :8081 (32 par), gemma-31b :8082 (48 par), qwen2.5-vl-32b vision :8083 (24 par), bge-m3 embeddings :8084 |
| 7880 / 7881 | Contabo control node | LiveKit HTTP/WS and RTC |
| 50000–60000/udp | Contabo control node | LiveKit RTC media |
| 5060 | Contabo control node | SIP |
| 59001–59100 | agent desktops | x11vnc (Xvfb :1–:100) |
| 60801–60900 | agent desktops | noVNC web |
| 9201–9300 | agent desktops | Chrome CDP |
| 8501–8600 | agent desktops | agent daemon |

## Run it

```bash
cd visual-limbs/edge
npm install
npx wrangler secret put LIVEKIT_API_KEY     # once
npx wrangler secret put LIVEKIT_API_SECRET  # once
npx wrangler dev                            # local: http://127.0.0.1:8787
npx wrangler deploy                         # live on edge.p2pdojo.com
```

Smoke check after deploy:

```bash
curl https://edge.p2pdojo.com/health
curl 'https://edge.p2pdojo.com/token?room=lab&agent=a1'
```

See `edge/README.md` for routes, secrets, bindings, and zone-route details.
