#!/usr/bin/env bash
# Creates a virtual audio sink + virtual camera that OBS / RTMP can read from.
# Idempotent: safe to run multiple times.
set -euo pipefail

SINK_NAME="ai_streamer"

echo "[+] Installing v4l2loopback + ffmpeg + pulseaudio-utils"
sudo apt-get update -qq
sudo apt-get install -y v4l2loopback-dkms ffmpeg pulseaudio-utils

echo "[+] Loading v4l2loopback (video device /dev/video10)"
if ! lsmod | grep -q v4l2loopback; then
  sudo modprobe v4l2loopback devices=1 video_nr=10 \
    card_label="AIStreamer" exclusive_caps=1
fi

echo "[+] Creating PulseAudio null-sink '$SINK_NAME'"
if ! pactl list short modules | grep -q "sink_name=$SINK_NAME"; then
  pactl load-module module-null-sink \
    sink_name="$SINK_NAME" \
    sink_properties=device.description="AIStreamer"
fi

echo "[+] Done. Use Video Capture Device /dev/video10 + 'AIStreamer' audio input in OBS."
