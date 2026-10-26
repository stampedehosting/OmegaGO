# visual-limbs/edge — Cloudflare Worker edge router

Single Worker that fronts the visual-limbs agent mesh from Cloudflare's edge.

## Routes

| Route | Method | What it does |
|---|---|---|
| `/health` | GET | Liveness JSON (`{ok, service, colo, time}`). |
| `/token?room=R&agent=N` | GET | Mints a LiveKit access token (HS256 JWT, `video.roomJoin` grant for room `R`, identity `N`, TTL 1h). Returns `{token, room, agent, expires_in, livekit_url}`. |
| `/mesh/*` | ANY | Proxies to the lowest-latency control node (`latency.js` races `GET {node}/probe` from the edge colo). Method, body and headers are preserved; upstream path = node base + path after `/mesh`. Adds `x-mesh-node` / `x-mesh-latency-ms` to the response. |
| `/assets/*` | GET, HEAD | Serves objects from the `ASSETS` R2 bucket. Supports `Range: bytes=...` → `206` + `Content-Range`, conditional requests (`If-None-Match`/`If-Modified-Since` → `304`), and `Accept-Ranges: bytes`. |

CORS is open (`*`) — the token and asset endpoints are meant to be called from browser agents.

## Required secrets, vars and bindings

**Secrets** (`wrangler secret put <NAME>` — never commit values):

| Secret | Used for |
|---|---|
| `LIVEKIT_API_KEY` | `iss` of minted LiveKit tokens |
| `LIVEKIT_API_SECRET` | HS256 signing key for LiveKit tokens |

**Vars** (`[vars]` in `wrangler.toml`):

| Var | Default | Meaning |
|---|---|---|
| `CONTABO_URL` | `https://control.p2pdojo.com` | Fallback / primary control node (Contabo control box: LiteLLM/Argon gateway, LiveKit host). |
| `NODES_JSON` | `{"contabo":"https://control.p2pdojo.com"}` | `{"name":"url"}` map (or `[{"name","url"}]` list) of control nodes to race. |
| `PROBE_PATH` | `/probe` | Health endpoint hit on each candidate node. |
| `PROBE_TIMEOUT_MS` | `1500` | Per-node probe timeout. |
| `PROBE_CACHE_MS` | `10000` | How long an isolate reuses its winner before re-probing. Set `0` to probe every request. |
| `LIVEKIT_URL` | `""` | WebSocket URL echoed in `/token` responses, e.g. `wss://rtc.p2pdojo.com` (LiveKit `:7880`). |

**Bindings** (`wrangler.toml`):

| Binding | Type | Target |
|---|---|---|
| `ASSETS` | R2 bucket | `visual-limbs-assets` |

## Deploy

```bash
cd visual-limbs/edge
npm install                    # installs pinned wrangler

# create the R2 bucket once
npx wrangler r2 bucket create visual-limbs-assets

# secrets
npx wrangler secret put LIVEKIT_API_KEY
npx wrangler secret put LIVEKIT_API_SECRET

# edit [vars]: CONTABO_URL, NODES_JSON, LIVEKIT_URL, and pick a route style
npx wrangler deploy
```

## Zone route pattern

Two supported styles — pick one in `wrangler.toml`:

1. **Custom domain (recommended):** `edge.p2pdojo.com` → all routes live under it
   (`https://edge.p2pdojo.com/token`, `/mesh/...`, `/assets/...`, `/health`).
2. **Wildcard path routes** on the existing zone:
   `*.p2pdojo.com/mesh/*`, `*.p2pdojo.com/token`, `*.p2pdojo.com/assets/*`, `*.p2pdojo.com/health`.

Both require `p2pdojo.com` to be an active zone in the Cloudflare account
(`CLOUDFLARE_ACCOUNT_ID` is set on the dashboard right sidebar; wrangler picks
it up from `~/.wrangler` / `CLOUDFLARE_API_TOKEN` when deploying).

## Control-node side

Each node in `NODES_JSON` must answer `GET /probe` with any 2xx quickly — a bare
`204` is ideal. `/mesh/*` requests are forwarded unchanged to `node + <path after /mesh>`.

## Local dev

```bash
npm install
npx wrangler dev            # serves on http://127.0.0.1:8787
curl 'http://127.0.0.1:8787/health'
curl 'http://127.0.0.1:8787/token?room=lab&agent=a1'
```

In `wrangler dev`, secrets come from `.dev.vars` (gitignored — create it with
`LIVEKIT_API_KEY=...` / `LIVEKIT_API_SECRET=...`), and R2 bindings are emulated locally.
