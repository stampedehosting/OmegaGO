# AI Streamer Persona Architecture: 24/7 Open-Source Stack on RTX 5090

**Author:** Manus AI
**Date:** April 23, 2026

This document outlines the architecture and build plan for deploying a fully autonomous, 24/7 AI streamer persona. The system is designed to ingest live chat from platforms like YouTube, Twitch, TikTok, and LinkedIn, generate contextual responses using a local Large Language Model (LLM), synthesize speech via a local Text-to-Speech (TTS) engine, and drive a real-time talking-head avatar. 

Crucially, this architecture is optimized for a single **NVIDIA RTX 5090 (32 GB VRAM, Blackwell architecture)**, ensuring that the entire pipeline runs locally without incurring ongoing API costs, while maintaining high fidelity and low latency.

## 1. Core Stack Selection

The RTX 5090 provides exceptional memory bandwidth and compute density, allowing us to run a 30B-class LLM, a high-quality TTS engine, and a real-time lipsync model concurrently.

### 1.1. Real-Time Avatar Generation
The visual component requires a model capable of generating high-quality lip synchronization at 30 frames per second (fps) or higher, without saturating the GPU memory needed by the LLM.

*   **Primary Choice: MuseTalk 1.5** [1]
    MuseTalk is an open-source (MIT License) latent-space inpainting model that modifies an existing video or portrait to match an audio track. It is highly optimized, capable of achieving 30 fps+ on older hardware (like the Tesla V100), meaning it will comfortably exceed 60 fps on an RTX 5090. It requires relatively low VRAM, leaving ample space for the LLM.
*   **Alternative: LivePortrait**
    For scenarios requiring higher fidelity expression and eye control, LivePortrait offers excellent quality. While heavier than MuseTalk, it can run in real-time on modern GPUs and serves as a good "premium mode" toggle.

### 1.2. Local Large Language Model (LLM)
The LLM acts as the "brain" of the persona, reading chat context and generating responses. We need a model that balances conversational quality with inference speed.

*   **Inference Engine: vLLM or Ollama** [2]
    vLLM provides the best throughput for concurrent requests and supports the Blackwell architecture (CUDA 12.8). However, for a single-stream conversation, Ollama (wrapping llama.cpp) offers a simpler development experience and sufficient performance.
*   **Model Choice: Qwen3-30B-A3B (Q4_K_M)** [3]
    This Mixture-of-Experts (MoE) model is extremely fast due to its low active parameter count (~3B), making it ideal for snappy, low-latency chat replies. It fits comfortably within the 32 GB VRAM limit alongside the other models.
*   **Alternative: Qwen2.5-32B-Instruct (AWQ/INT4)**
    For deeper conversational quality, this dense model requires ~20 GB VRAM and can achieve 30–50 tokens per second on the 5090.

### 1.3. Text-to-Speech (TTS)
The TTS engine must support streaming to minimize the time to first audio chunk, ensuring the avatar responds quickly.

*   **Primary Choice: Kokoro-82M** [4]
    Kokoro is a tiny, extremely fast model capable of sub-150ms streaming latency on consumer GPUs. It produces natural-sounding speech and is licensed under Apache-2.0.
*   **Alternative: F5-TTS**
    If voice cloning is required, F5-TTS offers streaming capabilities and zero-shot cloning under an MIT license.
*   **Orchestration: RealtimeTTS** [5]
    We will use the RealtimeTTS wrapper to handle stream-friendly chunking and orchestrate the underlying TTS engines.

## 2. Live Chat Ingestion and Platform Adapters

The system must read chat messages in real-time to maintain the illusion of a live interaction. Each platform requires a specific ingestion strategy.

| Platform | Ingestion Method | RTMP Streaming Requirements |
| :--- | :--- | :--- |
| **YouTube Live** | Official Data API v3 (`liveChatMessages.list`). Polling at ~2s cadence. | Open to all verified accounts. |
| **Twitch** | IRC over WebSocket (`wss://irc-ws.chat.twitch.tv:443`). | Open to all accounts. |
| **TikTok Live** | Unofficial `TikTokLive` Python library (reads internal WebSocket). | Requires 1,000+ followers for a stream key. Workaround: TikTok Studio + OBS Virtual Cam. |
| **LinkedIn Live** | No public real-time chat API. Requires scraping via authenticated browser or using a unified API like Restream. | Requires LinkedIn Live access approval and a third-party broadcasting tool. |

## 3. Streaming Output Pipeline

Once the avatar frames and TTS audio are generated, they must be composited and streamed to the target platforms. We propose two operational modes:

### 3.1. Local Development Mode (OBS WebSocket)
This mode is ideal for testing and manual intervention.
1.  The application pushes generated frames to a local virtual camera (e.g., NDI or `v4l2loopback`).
2.  Audio is pushed to a virtual sink (e.g., `pactl load-module module-null-sink`).
3.  OBS Studio captures the virtual camera and audio sink.
4.  OBS handles the RTMP stream to YouTube, Twitch, or TikTok (using the Multiple RTMP outputs plugin for simultaneous streaming).

### 3.2. 24/7 Server Mode (Headless FFmpeg)
This mode is designed for autonomous, continuous operation without a graphical interface.
1.  The application composites the avatar frames with an overlay PNG (containing the chat feed, viewer count, and UI elements).
2.  The composited video and audio are piped directly to FFmpeg.
3.  FFmpeg pushes the stream directly to the target RTMP URLs (`-f flv rtmp://...`).

## 4. 24/7 Operations and Hardware Management

Running a triple-load (LLM + TTS + lipsync) continuously on an RTX 5090 requires careful hardware management.

*   **Power and Thermals:** Sustained power draw will be approximately 575 W. Applying an undervolt and an 80% power limit can reduce power consumption by ~25% with minimal performance loss.
*   **Process Supervision:** Each component (LLM server, TTS engine, Avatar generator, Ingestion script) should run as a `systemd` service under a process supervisor to ensure automatic restarts on failure or Out-Of-Memory (OOM) events.
*   **State Management:** A lightweight state store (e.g., Redis or SQLite) is necessary to maintain the persona's context (recent chat history, current topic, viewer mood) without resending the entire history to the LLM on every turn.
*   **Safety and Moderation:** To comply with platform Terms of Service (especially YouTube and TikTok), a small local classifier (e.g., Llama-Guard-3-1B) should be implemented to filter both incoming chat and outgoing replies.

## 5. Hybrid API Mode

While the primary goal is a 100% local stack, the architecture supports a "hybrid mode" for scheduled, high-profile events where API costs are acceptable.

*   **LLM Swap:** Replace the local Qwen model with Claude, GPT-5, or Gemini via API keys for enhanced reasoning during complex Q&A sessions.
*   **TTS Swap:** Replace Kokoro with ElevenLabs for celebrity-quality, highly expressive voice synthesis.

## References

[1] MuseTalk GitHub Repository. https://github.com/TMElyralab/MuseTalk
[2] vLLM Project. https://github.com/vllm-project/vllm
[3] Qwen Models. https://qwenlm.github.io/
[4] Kokoro TTS. https://huggingface.co/hexgrad/Kokoro-82M
[5] RealtimeTTS GitHub Repository. https://github.com/KoljaB/RealtimeTTS
