# Running all models on the headless Debian server

The pipeline normally runs every model on the Windows machine. This folder lets
you run them on the **Debian server** (i3-10105F, 16 GB RAM, GTX 1060 6 GB) and
have `d:\Writer` talk to it over the LAN:

| Service           | Port | Runs on server         | Used by                                  |
|-------------------|------|------------------------|------------------------------------------|
| llama.cpp (LLM)   | 1234 | Qwen2.5-7B-Instruct Q4 | `src/storygen.py` (outline + chapters)   |
| SD WebUI (A1111)  | 7860 | Realistic Vision V5.1  | `src/imagegen.py` (cover + abstract art) |
| Orpheus 3B (TTS)  | 8000 | Orpheus 3B 4-bit fp16  | `src/tts.py` (audiobook)                 |

## Why these choices (GTX 1060 6 GB / Pascal)

- **LLM:** a 7B GGUF in 4-bit (~4.7 GB) fits almost entirely in VRAM. Qwen2.5-7B
  is excellent at the strict-JSON output `storygen.py` needs.
- **Images:** SD 1.5 (Realistic Vision V5.1) is the realistic look, ~2 GB, fast
  on 6 GB. RealVisXL (SDXL) is ~6.5 GB and very slow / OOM-prone on 6 GB —
  optional (`SKIP_XL=0`), not recommended.
- **TTS:** Orpheus 3B 4-bit (~2.4 GB VRAM) loads in **float16** because Pascal
  has no bfloat16 support (see `tts_server.py`).

## 1. Copy the folder to the server

```bash
# from PowerShell on the Windows machine:
scp -r d:\Writer\server root@192.168.0.103:/root/server
```

## 2. Run the setup (one reboot)

```bash
ssh root@192.168.0.103
cd /root/server
sudo bash setup.sh        # phase 1: drivers  -> it tells you to reboot
sudo reboot
# after reboot:
sudo bash setup.sh        # phase 2: everything else (models download + build)
```

First start of `sd-webui` and `tts-server` downloads their models/builds their
venvs, so they take a while. Watch with:

```bash
systemctl status llm-server tts-server sd-webui
journalctl -u sd-webui -f
```

Verify from the Windows machine:

```powershell
curl http://192.168.0.103:1234/v1/models          # LLM up
curl http://192.168.0.103:7860/sdapi/v1/sd-models # images up
curl http://192.168.0.103:8000/health             # TTS up
```

## 3. Point the pipeline at the server

`config.json` in the repo root is already set to:

```jsonc
"lmstudio": { "base_url": "http://192.168.0.103:1234/v1", "model": "" },
"imagegen": { "backend": "sdwebui", "sdwebui_url": "http://192.168.0.103:7860" },
"tts":      { "backend": "orpheus-http", "server_url": "http://192.168.0.103:8000" }
```

Run `story_writer.bat` as usual — story, images, and audiobook now all come from
the server. To go back to fully local, restore the local URLs / `diffusers` /
`orpheus` backend.

## Optional: let Copilot manage the server over SSH

Passwordless (key) SSH lets me run commands on the box for you. On Windows:

```powershell
# (run once) create a key if you don't have one
ssh-keygen -t ed25519 -N "" -f $env:USERPROFILE\.ssh\id_ed25519

# print the PUBLIC key, then paste it into the server:
Get-Content $env:USERPROFILE\.ssh\id_ed25519.pub
```

On the server:

```bash
mkdir -p ~/.ssh && chmod 700 ~/.ssh
echo "<paste the public key>" >> ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys
```

## Troubleshooting

- **LLM slow** → the CUDA build may have fallen back or `-ngl` is too low; try
  `-ngl 99` and check `journalctl -u llm-server`.
- **SD WebUI won't start on 6 GB** → confirm `--medvram` is in `webui-user.sh`;
  SDXL images will OOM — stick to Realistic Vision V5.1 for the server.
- **Orpheus fails to load 4-bit** → `pip install bitsandbytes==0.43.3` in
  `/opt/ai-server/venv-tts` (newer bitsandbytes dropped Pascal support).
- **Firewall** → `sudo ufw allow 22,1234,7860,8000/tcp` (setup.sh does this).
