#!/usr/bin/env python3
"""router_health.py — per-backend slot saturation reporter for the visual-limbs router.

Polls each lane-1 brain-card backend (and any configured lane-3 fleet
endpoints) and reports how full it is, so agents and dashboards can see
when the router is about to spill to OpenRouter.

Probe order per backend (first that answers wins):
  GET /slots    — llama.cpp llama-server: [{"is_processing": bool, ...}]
  GET /metrics  — vLLM/prometheus: vllm:num_requests_running / _waiting
  GET /health   — liveness only, no slot data

Endpoints:
  GET /health      full report (status, per-backend saturation, lane advice)
  GET /health/live always-200 liveness probe
  GET /backends    backend inventory without a fresh probe (uses last poll)

Run:
  uvicorn router_health:app --host 127.0.0.1 --port 8010
"""

import asyncio
import os
import re
import time

import httpx
from fastapi import FastAPI

PROBE_TIMEOUT = float(os.getenv("HEALTH_PROBE_TIMEOUT", "2.5"))
SATURATION_WARN = float(os.getenv("HEALTH_SATURATION_WARN", "0.9"))

# name -> (port, advertised parallel slots, model served)
DEFAULT_BACKENDS = {
    "qwen-coder": {"url": "http://127.0.0.1:8081", "slots": 32, "model": "qwen-coder-32b"},
    "gemma":      {"url": "http://127.0.0.1:8082", "slots": 48, "model": "gemma-31b"},
    "qwen-vl":    {"url": "http://127.0.0.1:8083", "slots": 24, "model": "qwen2.5-vl-32b"},
    "bge-m3":     {"url": "http://127.0.0.1:8084", "slots": 32, "model": "bge-m3"},
}

# Lane-3 fleet endpoints are optional and env-provided.
FLEET_ENV = {
    "qwen-coder": "FLEET_QWEN_CODER_URL",
    "gemma": "FLEET_GEMMA_URL",
    "qwen-vl": "FLEET_QWEN_VL_URL",
    "bge-m3": "FLEET_BGE_M3_URL",
}

VLLM_RUNNING = re.compile(r"^vllm:num_requests_running\s+([\d.]+)", re.M)
VLLM_WAITING = re.compile(r"^vllm:num_requests_waiting\s+([\d.]+)", re.M)

app = FastAPI(title="visual-limbs router health", version="1.0.0")


def _base(url: str) -> str:
    return url.rstrip("/").removesuffix("/v1")


def _backends() -> dict:
    out = {}
    for name, spec in DEFAULT_BACKENDS.items():
        out[name] = {"lane": 1, **spec}
        fleet_url = os.getenv(FLEET_ENV[name])
        if fleet_url:
            out[f"{name}-fleet"] = {
                "lane": 3,
                "url": _base(fleet_url),
                "slots": spec["slots"],
                "model": spec["model"],
            }
    return out


async def _probe(client: httpx.AsyncClient, name: str, spec: dict) -> dict:
    url = _base(spec["url"])
    result = {
        "lane": spec["lane"],
        "url": url,
        "model": spec["model"],
        "slots_total": spec["slots"],
        "reachable": False,
        "probe": "none",
        "slots_busy": None,
        "queue": None,
        "saturation": None,
        "error": None,
    }
    # 1) llama.cpp /slots — exact per-slot occupancy
    try:
        r = await client.get(f"{url}/slots", timeout=PROBE_TIMEOUT)
        if r.status_code == 200 and isinstance(r.json(), list):
            slots = r.json()
            busy = sum(1 for s in slots if s.get("is_processing"))
            total = len(slots) or spec["slots"]
            result.update(
                reachable=True, probe="slots", slots_busy=busy,
                queue=0, slots_total=total,
                saturation=round(busy / total, 3),
            )
            return result
    except Exception:
        pass

    # 2) vLLM /metrics — running/waiting request gauges
    try:
        r = await client.get(f"{url}/metrics", timeout=PROBE_TIMEOUT)
        if r.status_code == 200:
            running = VLLM_RUNNING.search(r.text)
            waiting = VLLM_WAITING.search(r.text)
            busy = int(float(running.group(1))) if running else 0
            queue = int(float(waiting.group(1))) if waiting else 0
            result.update(
                reachable=True, probe="metrics", slots_busy=busy,
                queue=queue, saturation=round(busy / spec["slots"], 3),
            )
            return result
    except Exception:
        pass

    # 3) /health — reachable but no occupancy info
    try:
        r = await client.get(f"{url}/health", timeout=PROBE_TIMEOUT)
        if r.status_code == 200:
            result.update(reachable=True, probe="health")
            return result
    except Exception as e:
        result["error"] = f"{type(e).__name__}: {e}"

    return result


def _lane_advice(backends: dict) -> dict:
    advice = {}
    for name in DEFAULT_BACKENDS:
        local = backends.get(name, {})
        fleet = backends.get(f"{name}-fleet", {})
        if local.get("reachable") and (local.get("saturation") or 0) < SATURATION_WARN:
            lane = 1
        elif os.getenv("OPENROUTER_API_KEY") and name != "bge-m3":
            lane = 2  # OpenRouter has no embeddings -> bge-m3 skips lane 2
        elif fleet.get("reachable"):
            lane = 3
        else:
            lane = None
        advice[name] = lane
    return advice


async def _collect() -> dict:
    specs = _backends()
    async with httpx.AsyncClient() as client:
        reports = await asyncio.gather(
            *(_probe(client, n, s) for n, s in specs.items())
        )
    backends = dict(zip(specs.keys(), reports))
    reachable = [b for b in backends.values() if b["reachable"]]
    saturated = [
        b for b in reachable
        if b["saturation"] is not None and b["saturation"] >= SATURATION_WARN
    ]
    status = (
        "down" if not reachable
        else "degraded" if len(reachable) < len(backends) or saturated
        else "ok"
    )
    return {
        "status": status,
        "ts": int(time.time()),
        "saturation_warn_at": SATURATION_WARN,
        "backends": backends,
        "recommended_lane": _lane_advice(backends),
    }


@app.get("/health")
async def health():
    return await _collect()


@app.get("/health/live")
async def liveness():
    return {"status": "alive"}


@app.get("/backends")
async def backends():
    return await _collect()


@app.get("/")
async def root():
    return {"service": "visual-limbs router health", "endpoints": ["/health", "/health/live", "/backends"]}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host=os.getenv("ROUTER_HEALTH_HOST", "127.0.0.1"),
        port=int(os.getenv("ROUTER_HEALTH_PORT", "8010")),
    )
