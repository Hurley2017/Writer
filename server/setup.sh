#!/usr/bin/env bash
# =====================================================================
# AI Story Writer - headless Debian server bootstrap
#
#   i3-10105F | 16 GB RAM | 256 GB disk | GTX 1060 6 GB (Pascal, sm_61)
#
# Installs and wires up every model the pipeline needs, as network
# services the Windows machine (d:\Writer) calls:
#
#   * llama.cpp LLM server  -> :1234  (OpenAI-compatible)  story writer LLM
#   * Stable Diffusion WebUI-> :7860  (AUTOMATIC1111 API)  image backend
#   * Orpheus 3B TTS        -> :8000  (HTTP /synthesize)   audiobook voice
#
# Usage (as root, from the folder that also contains tts_server.py):
#     sudo bash setup.sh
#
# Phase 1 installs the NVIDIA driver and asks you to REBOOT once;
# after the reboot, re-run the SAME command and it continues to Phase 2.
# =====================================================================
set -euo pipefail

SERVER_DIR="${SERVER_DIR:-/opt/ai-server}"
TTS_PORT="${TTS_PORT:-8000}"
LM_PORT="${LM_PORT:-1234}"
SD_PORT="${SD_PORT:-7860}"
HF_CACHE="$SERVER_DIR/hf_cache"
VENV_TTS="$SERVER_DIR/venv-tts"
LLAMA_DIR="$SERVER_DIR/llama-cpp"
SD_DIR="$SERVER_DIR/sd-webui"
MODELS="$SERVER_DIR/models"

LLM_MODEL_URL="https://huggingface.co/Qwen/Qwen2.5-7B-Instruct-GGUF/resolve/main/qwen2.5-7b-instruct-q4_k_m.gguf"
LLM_MODEL="$MODELS/qwen2.5-7b-instruct-q4_k_m.gguf"
RV_URL="https://huggingface.co/SG161222/Realistic_Vision_V5.1_noVAE/resolve/main/Realistic_Vision_V5.1_fp16-no-ema.safetensors"
# SDXL is optional on 6 GB (slow + OOM risk). Set SKIP_XL=0 to download it too.
SKIP_XL="${SKIP_XL:-1}"
XL_URL="https://huggingface.co/SG161222/RealVisXL_V4.0/resolve/main/RealVisXL_V4.0.safetensors"

log() { echo -e "\n\033[1;32m[setup]\033[0m $*"; }
die() { echo -e "\n\033[1;31m[setup][ERROR]\033[0m $*" >&2; exit 1; }

# ---------------------------------------------------------------- PHASE 0
log "Phase 0: system packages + NVIDIA driver"
# make sure contrib/non-free are enabled (nvidia-driver lives in non-free)
if ! grep -rqs "non-free" /etc/apt/sources.list /etc/apt/sources.list.d/ 2>/dev/null; then
  sed -i 's/^\(deb .*\) main$/\1 main contrib non-free non-free-firmware/' \
    /etc/apt/sources.list 2>/dev/null || true
  apt-get update -y
fi
apt-get update -y
DEBIAN_FRONTEND=noninteractive apt-get install -y \
  curl wget git unzip zip pkg-config build-essential cmake \
  python3 python3-venv python3-pip \
  libfuse2 libssl-dev libcurl4-openssl-dev zlib1g-dev \
  nvidia-driver firmware-misc-nonfree nvidia-cuda-toolkit

if ! command -v nvidia-smi >/dev/null 2>&1; then
  die "NVIDIA driver is installed but not active yet. REBOOT the server, then re-run:  sudo bash setup.sh"
fi
log "GPU: $(nvidia-smi --query-gpu=name,memory.total --format=csv,noheader)"

mkdir -p "$SERVER_DIR" "$MODELS" "$HF_CACHE"

# ---------------------------------------------------------------- firewall
if command -v ufw >/dev/null 2>&1; then
  ufw allow 22/tcp   >/dev/null 2>&1 || true
  ufw allow "$LM_PORT/tcp" >/dev/null 2>&1 || true
  ufw allow "$SD_PORT/tcp" >/dev/null 2>&1 || true
  ufw allow "$TTS_PORT/tcp" >/dev/null 2>&1 || true
  ufw reload >/dev/null 2>&1 || true
fi

# ---------------------------------------------------------------- TTS venv
log "Phase 1: PyTorch + Orpheus TTS venv (CUDA 12.1 - Pascal compatible)"
if [ ! -d "$VENV_TTS" ]; then
  python3 -m venv "$VENV_TTS"
fi
"$VENV_TTS/bin/pip" install --upgrade pip wheel >/dev/null
"$VENV_TTS/bin/pip" install "torch==2.4.1" --index-url https://download.pytorch.org/whl/cu121
"$VENV_TTS/bin/pip" install transformers snac bitsandbytes soundfile flask numpy
# NOTE: if the 4-bit Orpheus load fails on this GPU, try an older bitsandbytes:
#   "$VENV_TTS/bin/pip" install "bitsandbytes==0.43.3"

cp -f tts_server.py "$SERVER_DIR/tts_server.py"

# ---------------------------------------------------------------- llama.cpp
log "Phase 2: llama.cpp LLM server (CUDA, arch 61)"
if [ ! -f "$LLAMA_DIR/build/bin/llama-server" ]; then
  git clone --depth 1 https://github.com/ggml-org/llama.cpp "$LLAMA_DIR" 2>/dev/null || true
  cmake -S "$LLAMA_DIR" -B "$LLAMA_DIR/build" \
    -DGGML_CUDA=ON -DCMAKE_CUDA_ARCHITECTURES=61 -DCMAKE_BUILD_TYPE=Release
  cmake --build "$LLAMA_DIR/build" --config Release -j"$(nproc)"
fi
if [ ! -f "$LLM_MODEL" ]; then
  log "Downloading Qwen2.5-7B-Instruct Q4_K_M (~4.7 GB) ..."
  wget -q --show-progress -O "$LLM_MODEL" "$LLM_MODEL_URL"
fi

# ---------------------------------------------------------------- SD WebUI
log "Phase 3: Stable Diffusion WebUI (AUTOMATIC1111)"
if [ ! -d "$SD_DIR" ]; then
  git clone --depth 1 https://github.com/AUTOMATIC1111/stable-diffusion-webui.git "$SD_DIR"
fi
mkdir -p "$SD_DIR/models/Stable-diffusion"
if [ ! -f "$SD_DIR/models/Stable-diffusion/Realistic_Vision_V5.1_fp16-no-ema.safetensors" ]; then
  log "Downloading Realistic Vision V5.1 (SD 1.5, realistic, ~2 GB) ..."
  wget -q --show-progress -O "$SD_DIR/models/Stable-diffusion/Realistic_Vision_V5.1_fp16-no-ema.safetensors" "$RV_URL"
fi
if [ "${SKIP_XL}" != "1" ] && [ ! -f "$SD_DIR/models/Stable-diffusion/RealVisXL_V4.0.safetensors" ]; then
  log "Downloading RealVisXL V4.0 (SDXL, ~6.5 GB - optional on 6 GB) ..."
  wget -q --show-progress -O "$SD_DIR/models/Stable-diffusion/RealVisXL_V4.0.safetensors" "$XL_URL"
fi
cat > "$SD_DIR/webui-user.sh" <<EOF
export COMMANDLINE_ARGS="--api --listen --port $SD_PORT --medvram --xformers"
EOF

# ---------------------------------------------------------------- systemd
log "Phase 4: systemd units"
cat > /etc/systemd/system/llm-server.service <<EOF
[Unit]
Description=llama.cpp LLM server (OpenAI-compatible)
After=network.target

[Service]
ExecStart=$LLAMA_DIR/build/bin/llama-server -m $LLM_MODEL --host 0.0.0.0 --port $LM_PORT --ctx-size 8192 -ngl 99
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

cat > /etc/systemd/system/sd-webui.service <<EOF
[Unit]
Description=Stable Diffusion WebUI (AUTOMATIC1111 API)
After=network.target

[Service]
WorkingDirectory=$SD_DIR
ExecStart=/bin/bash $SD_DIR/webui.sh
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

cat > /etc/systemd/system/tts-server.service <<EOF
[Unit]
Description=Orpheus 3B TTS HTTP service
After=network.target

[Service]
Environment=HF_HOME=$HF_CACHE
Environment=HF_HUB_CACHE=$HF_CACHE/hub
Environment=HF_HUB_DISABLE_SYMLINKS=1
Environment=TTS_PORT=$TTS_PORT
ExecStart=$VENV_TTS/bin/python $SERVER_DIR/tts_server.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now llm-server tts-server sd-webui || true

log "Setup complete!"
log "  LLM    : http://192.168.0.103:$LM_PORT/v1/models   (llama.cpp)"
log "  Images : http://192.168.0.103:$SD_PORT/sdapi/v1/sd-models   (A1111)"
log "  TTS    : http://192.168.0.103:$TTS_PORT/health   (Orpheus)"
log "First starts download the models and build A1111's venv - check with:"
log "  systemctl status llm-server tts-server sd-webui"
log "  journalctl -u sd-webui -f"
