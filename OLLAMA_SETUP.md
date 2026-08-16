# Ollama Setup for Writer Project

## Current Status
✅ Python Ollama client installed  
✅ Config updated for Ollama (port 11434)  
✅ Model selected: `mistral:7b-instruct-v0.2-q5_K_M` (7B, quantized, lightweight)  
❌ Ollama server not running yet

---

## Why Ollama + Mistral 7B?

| Factor | Original (31B) | New (7B) |
|--------|---|---|
| **Model** | Gemma 4 31B | Mistral 7B |
| **RAM needed** | 16-24 GB | 8-10 GB |
| **GPU needed** | 6-8 GB | 4-6 GB |
| **Speed** | Slower | 2-3x faster |
| **Fit** | ❌ Too large | ✅ Perfect fit |

**7B model is ideal for your 16 GB RAM + 6 GB GPU setup.**

---

## Step 1: Download & Install Ollama

### On Linux (Debian/Ubuntu):

Download the binary from the official Ollama website:

```bash
# Option A: Using curl (latest version)
mkdir -p /tmp/ollama_install
cd /tmp/ollama_install
wget https://github.com/ollama/ollama/releases/download/v0.1.32/ollama-0.1.32-linux-amd64.tar.gz
# Or find latest at: https://github.com/ollama/ollama/releases

tar -xzf ollama-*-linux-amd64.tar.gz
sudo mv ollama/bin/ollama /usr/local/bin/

# Option B: Using the official script (if available)
curl -fsSL https://ollama.ai/install.sh | sh
```

Verify installation:
```bash
ollama --version
```

---

## Step 2: Start Ollama Server

In a new terminal (or background):

```bash
ollama serve
```

You should see:
```
Ollama is running at http://localhost:11434
```

**Keep this terminal running!** Ollama must stay running for the pipeline to work.

---

## Step 3: Download the 7B Model

In another terminal:

```bash
ollama pull mistral:7b-instruct-v0.2-q5_K_M
```

This will download ~5 GB and cache it locally. First run takes 5-10 minutes.

You can list available models with:
```bash
ollama list
```

Should show:
```
mistral:7b-instruct-v0.2-q5_K_M    latest    ...
```

---

## Step 4: Test the Setup

In your Writer project terminal:

```bash
cd /home/tusher/Writer
source venv/bin/activate

python3 << 'TEST'
import json
from src.lmstudio import LMStudio

cfg = json.load(open('config.json'))
lm = LMStudio(cfg['lmstudio']['base_url'])

print("Testing Ollama connection...")
if lm.is_available():
    print("✓ Ollama is REACHABLE")
    models = lm.list_models()
    print(f"✓ Available models: {models}")
    
    # Test chat
    print("\nTesting chat completion...")
    response = lm.chat(
        messages=[{"role": "user", "content": "Say 'Hello from Ollama' in one sentence"}],
        model=cfg['lmstudio']['model'],
        temperature=0.7,
        max_tokens=100
    )
    print(f"Response: {response}")
    print("\n✓ Ollama test PASSED")
else:
    print("✗ Ollama is NOT REACHABLE")
    print("Make sure 'ollama serve' is running in another terminal")
TEST
```

Expected output:
```
✓ Ollama is REACHABLE
✓ Available models: ['mistral']
Response: Hello from Ollama!
✓ Ollama test PASSED
```

---

## Step 5: Run the Full Pipeline

Once Ollama is running and tested:

```bash
cd /home/tusher/Writer
source venv/bin/activate

python -m src.pipeline \
  --genre fantasy \
  --topic "a young mage learning fire magic" \
  --length short \
  --stage all
```

---

## System Resource Usage

```
Stage 1: Story Generation (Ollama)
├─ Model: Mistral 7B (via Ollama)
├─ CPU: Full usage for inference (~5-10 min for short story)
├─ RAM: ~8-10 GB active
└─ GPU: Minimal (depends on Ollama config)

Stage 2: Image Generation (SD 1.5)
├─ Model: Stable Diffusion 1.5
├─ GPU: 2.06 GB VRAM reserved
├─ Duration: ~2 min
└─ No CPU offload

Stage 3: Audio Narration (Orpheus 3B)
├─ Model: Orpheus 3B 4-bit
├─ GPU: ~2-3 GB VRAM
├─ Duration: ~3-5 min
└─ Emotion-aware TTS

Total Time: ~10-20 minutes for a short story
Peak VRAM: ~5 GB (well under 6 GB limit)
```

---

## Troubleshooting

### "Ollama is NOT REACHABLE"
- Check if `ollama serve` is still running in the other terminal
- Try: `curl http://localhost:11434/api/tags`
- Check firewall: `netstat -tulpn | grep 11434`

### "Model not found"
- Run: `ollama pull mistral:7b-instruct-v0.2-q5_K_M`
- Wait for download to complete
- Verify with: `ollama list`

### Slow story generation
- This is normal for a CPU-based inference
- 7B model typically takes 30-60 sec per prompt on modern CPUs
- GPU acceleration can speed this up (Ollama supports it)

### "CUDA out of memory" during image generation
- Ollama is still using GPU memory
- Run `ollama list` to see running models
- Restart Ollama if needed

---

## Quick Reference

| Command | Purpose |
|---------|---------|
| `ollama serve` | Start the server (keep running) |
| `ollama pull mistral:7b-instruct-v0.2-q5_K_M` | Download the model |
| `ollama list` | Show available models |
| `ollama rm mistral:7b-instruct-v0.2-q5_K_M` | Delete a model |
| `curl http://localhost:11434/api/tags` | Check server status |

---

**Status**: 🔄 **Waiting for Ollama Installation**  
**Next Step**: Download Ollama → Start server → Run test
