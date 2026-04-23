# ai_streamer — Autonomous AI Streamer Persona

A 24/7-capable open-source pipeline that turns a single RTX 5090 box into a live AI streamer:
**live chat → local LLM → local TTS → real-time talking-head avatar → RTMP / virtual cam**.

See the parent doc `../AI_STREAMER_ARCHITECTURE.md` for the full design rationale.

## Module layout

| Path | Role |
|---|---|
| `ingest/` | Per-platform chat readers (YouTube, Twitch, TikTok, LinkedIn) feeding a unified message bus |
| `llm/` | Local LLM client (Ollama / vLLM) with persona prompt + safety gate |
| `tts/` | Streaming TTS adapter (Kokoro primary, F5-TTS / ElevenLabs alternates) |
| `avatar/` | MuseTalk real-time inference wrapper, frame producer |
| `overlay/` | Live UI compositor (chat feed, viewer count, hearts) — produces an RGBA layer |
| `output/` | Two output backends: `obs_virtualcam.py` for dev, `ffmpeg_rtmp.py` for headless 24/7 |
| `state/` | Redis/SQLite persona memory + conversation window |
| `config/` | YAML configs: persona, models, platforms, output targets |
| `orchestrator.py` | Wires everything together with asyncio queues |

## Quick start (development, OBS mode)

```bash
# 1. System deps (Ubuntu 22.04+ with NVIDIA driver 575+ / CUDA 12.8)
sudo apt install -y ffmpeg v4l2loopback-dkms pulseaudio-utils
sudo modprobe v4l2loopback devices=1 video_nr=10 card_label="AIStreamer" exclusive_caps=1

# 2. Python env (CUDA 12.8 wheels)
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r ai_streamer/requirements.txt

# 3. Pull the LLM
ollama pull qwen3:30b-a3b-q4_K_M

# 4. Configure persona + platforms
cp ai_streamer/config/persona.example.yaml ai_streamer/config/persona.yaml
cp ai_streamer/config/platforms.example.yaml ai_streamer/config/platforms.yaml
$EDITOR ai_streamer/config/persona.yaml

# 5. Run
python -m ai_streamer.orchestrator --config ai_streamer/config/persona.yaml
```

## 24/7 server mode

Use `ai_streamer/output/ffmpeg_rtmp.py` and the `systemd` units in `deploy/systemd/`.
See the architecture doc, section 4.

## Status

This is a scaffold with runnable stubs. Each module has a documented interface and
a working in-memory mock so the orchestrator can be exercised end-to-end without GPUs.
Replace the mocks with the real backends as you bring up each component.
