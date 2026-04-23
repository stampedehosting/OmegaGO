"""ai_streamer orchestrator.

Wires the four async stages together via bounded queues:

    [ingest sources] -> chat_q -> [llm] -> reply_q -> [tts] -> audio_q -> [avatar]
                                                                |
                                                                v
                                                            [overlay] -> [output sink]

Run with:
    python -m ai_streamer.orchestrator --persona ai_streamer/config/persona.yaml \\
                                       --platforms ai_streamer/config/platforms.yaml

The default mock-everything config will produce log lines proving the pipeline
end-to-end without GPUs or API keys.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import random
import string
import time
from pathlib import Path
import yaml
from loguru import logger

from .types import ChatMessage, LLMReply, AudioChunk, VideoFrame, StreamContext, Platform
from .ingest import build_sources, Multiplexer
from .llm import LLMClient, LLMConfig
from .tts import TTSConfig, build_tts
from .avatar import AvatarConfig, build_avatar
from .overlay import OverlayCompositor
from .output import OutputConfig, build_sink
from .state import PersonaMemory


def _expand_env(value):
    if isinstance(value, str):
        return os.path.expandvars(value)
    if isinstance(value, list):
        return [_expand_env(v) for v in value]
    if isinstance(value, dict):
        return {k: _expand_env(v) for k, v in value.items()}
    return value


def load_yaml(path: str) -> dict:
    with open(path) as f:
        return _expand_env(yaml.safe_load(f))


async def _llm_stage(chat_q: asyncio.Queue, reply_q: asyncio.Queue,
                     client: LLMClient, mem: PersonaMemory, ctx: StreamContext,
                     idle_cfg: dict):
    """Reads chat, calls LLM, pushes replies. Also generates idle filler."""
    last_activity = time.monotonic()
    filler_after = float(idle_cfg.get("filler_after_seconds", 25))
    topics = idle_cfg.get("topics", [])

    async def _on_message(msg: ChatMessage):
        nonlocal last_activity
        mem.remember_chat(msg)
        ctx.recent_chat = list(mem.recent_chat(20))
        reply = await client.generate(msg)
        if reply:
            mem.remember_reply(reply)
            await reply_q.put(reply)
            last_activity = time.monotonic()
            ctx.last_reply_at = last_activity

    while True:
        try:
            msg = await asyncio.wait_for(chat_q.get(), timeout=1.0)
            await _on_message(msg)
        except asyncio.TimeoutError:
            if topics and time.monotonic() - last_activity > filler_after:
                synthetic = ChatMessage.new(
                    Platform.LOCAL, "host_cue", random.choice(topics),
                )
                await _on_message(synthetic)


async def _tts_stage(reply_q: asyncio.Queue, audio_q: asyncio.Queue, engine):
    while True:
        reply: LLMReply = await reply_q.get()
        logger.info(f"[tts] speaking reply {reply.id}: {reply.text!r}")
        async for chunk in engine.stream(reply):
            await audio_q.put(chunk)


async def _render_and_output(avatar, overlay: OverlayCompositor, sink,
                              audio_q: asyncio.Queue, audio_sink_q: asyncio.Queue):
    """Pull audio for the avatar, composite overlay, push to sink. Audio is
    duplicated: one path drives lipsync, the other is muxed by the sink."""
    async for frame in avatar.render(audio_q):
        frame.bgr = overlay.composite(frame.bgr)
        await sink.push_frame(frame)


async def _audio_pump(audio_q_in: asyncio.Queue, audio_q_avatar: asyncio.Queue,
                       sink):
    """Tee audio into the avatar queue and the output sink simultaneously."""
    while True:
        chunk: AudioChunk = await audio_q_in.get()
        await audio_q_avatar.put(chunk)
        await sink.push_audio(chunk)


async def main_async(persona_path: str, platforms_path: str):
    persona_cfg = load_yaml(persona_path)
    platforms_cfg = load_yaml(platforms_path)

    ctx = StreamContext(
        persona_name=persona_cfg["persona"]["name"],
        viewer_count=random.randint(40, 120),
        config=persona_cfg,
    )

    # ---- build components -------------------------------------------------
    sources = build_sources(platforms_cfg["ingest"])
    mux = Multiplexer(sources)

    llm_cfg = LLMConfig(**persona_cfg["llm"])
    llm = LLMClient(llm_cfg, persona_cfg["persona"]["prompt"], ctx)

    tts = build_tts(TTSConfig(**persona_cfg["tts"]))
    avatar = build_avatar(AvatarConfig(**persona_cfg["avatar"]))

    output_cfg = OutputConfig(
        **{**persona_cfg["output"],
           "rtmp_urls": [d["url"] for d in platforms_cfg.get("stream", {}).get("destinations", [])]}
    )
    sink = build_sink(output_cfg)
    overlay = OverlayCompositor(ctx)

    mem = PersonaMemory()

    # ---- queues -----------------------------------------------------------
    chat_q: asyncio.Queue[ChatMessage] = asyncio.Queue(maxsize=200)
    reply_q: asyncio.Queue[LLMReply] = asyncio.Queue(maxsize=20)
    audio_q_in: asyncio.Queue[AudioChunk] = asyncio.Queue(maxsize=200)
    audio_q_avatar: asyncio.Queue[AudioChunk] = asyncio.Queue(maxsize=200)

    # ---- start ------------------------------------------------------------
    logger.info(f"[orchestrator] starting persona={ctx.persona_name!r}")
    ingest_tasks = mux.start(chat_q)
    tasks = ingest_tasks + [
        asyncio.create_task(_llm_stage(chat_q, reply_q, llm, mem, ctx,
                                        persona_cfg.get("idle", {})), name="llm"),
        asyncio.create_task(_tts_stage(reply_q, audio_q_in, tts), name="tts"),
        asyncio.create_task(_audio_pump(audio_q_in, audio_q_avatar, sink), name="audio_pump"),
        asyncio.create_task(_render_and_output(avatar, overlay, sink, audio_q_avatar,
                                                None), name="render"),
    ]

    try:
        await asyncio.gather(*tasks)
    except asyncio.CancelledError:
        pass
    finally:
        await sink.close()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--persona", default="ai_streamer/config/persona.yaml")
    p.add_argument("--platforms", default="ai_streamer/config/platforms.yaml")
    args = p.parse_args()

    if not Path(args.persona).exists():
        # First-run convenience: fall back to example configs.
        args.persona = args.persona.replace(".yaml", ".example.yaml")
    if not Path(args.platforms).exists():
        args.platforms = args.platforms.replace(".yaml", ".example.yaml")

    try:
        asyncio.run(main_async(args.persona, args.platforms))
    except KeyboardInterrupt:
        logger.info("bye")


if __name__ == "__main__":
    main()
