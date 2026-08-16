# Story Model Testing Guide

## Current Status
✓ Python environment ready  
✓ Story generation code validated  
✓ Config: `offload_to_cpu: true` (allows CPU-resident large models)  
✗ **LM Studio is NOT running** — needs to be started

---

## How to Start LM Studio and Test

### Step 1: Start LM Studio Server

You need to:
1. **Download LM Studio** from https://lmstudio.ai/ (if not already installed)
2. **Open LM Studio** on your system
3. **Load a model** in the UI (search for `google/gemma-4-31b-qat` or `mistral` or any ~7-13B model)
4. Go to the **Developer tab** → click **"Start Server"**
5. Verify it says `Server running at http://localhost:1234/v1`

### Step 2: Run the Story Generation Test

Once LM Studio is running and showing "Server running", execute:

```bash
cd /home/tusher/Writer
source venv/bin/activate
python3 << 'STORYTEST'
import json
from src.lmstudio import LMStudio
from src.storygen import StoryGenerator
from src.config import load_config

cfg = load_config()
print("Connecting to LM Studio...")
lm = LMStudio(cfg["lmstudio"]["base_url"])

if not lm.is_available():
    print("ERROR: LM Studio not reachable. Did you start it?")
    exit(1)

models = lm.list_models()
print(f"✓ Connected. Available models: {models}")

# Pick a model
model = models[0] if models else "default"
print(f"\nTesting story generation with model: {model}")

gen = StoryGenerator(lm, model, cfg)
print("\nGenerating story outline...")

outline = gen.generate_outline(
    genre="fantasy",
    topic="a young mage learning to control fire",
    tone="epic",
    length="short"
)

print("\nOutline generated:")
print(json.dumps(outline, indent=2))
print("\n✓ Story model test PASSED")
STORYTEST
```

### Step 3: Run Full Pipeline Test (Once Story Model Works)

After the story model test passes, you can run the complete pipeline:

```bash
cd /home/tusher/Writer
source venv/bin/activate
python -m src.pipeline \
  --genre fantasy \
  --topic "a test story" \
  --length short \
  --stage all
```

---

## Expected Results

### Story Model Test Should Show:
```
✓ Connected. Available models: ['google/gemma-4-31b-qat']
Generating story outline...
Outline generated:
{
  "title": "...",
  "cover_prompt": "...",
  "sections": [...]
}
✓ Story model test PASSED
```

### Full Pipeline Should:
1. **Stage 1**: Generate story outline + chapters from LM Studio (uses CPU offload)
2. **Stage 2**: Generate cover image only via SD 1.5 (GPU, no CPU offload, stays under 6GB)
3. **Stage 3**: Narrate audiobook with Orpheus TTS (GPU-friendly, ~2-4 minutes)
4. **Output**: PDF with cover + text + audiobook in `output/`

---

## Memory Profile

- **Story Generation (LM Studio)**: Remote HTTP call, CPU-side processing with offload allowed
- **Image Generation (SD 1.5)**: GPU-resident, ~2.06 GB reserved, no CPU offload needed
- **TTS (Orpheus)**: GPU-resident with 4-bit quantization, ~2-3 GB reserved

Total peak VRAM: **~4-5 GB** (well under the 6 GB limit with one model loaded at a time)

---

## Troubleshooting

### "LM Studio is NOT REACHABLE"
- Ensure LM Studio is open and showing "Server running at http://localhost:1234/v1"
- Check firewall/port issues with: `netstat -tulpn | grep 1234`
- Try: `curl http://localhost:1234/v1/models`

### "Model not found"
- Load the model in LM Studio UI first
- Refresh LM Studio after loading a model
- The server needs an active model loaded to work

### Story generation is slow
- This is expected! A 13B model can take 30-60 seconds per prompt
- Smaller models (7B) are faster but lower quality
- LM Studio runs on CPU by default; GPU acceleration depends on your setup

### Image generation fails after story
- Restart LM Studio if it's still resident in memory
- The `_free_gpu()` call in the pipeline clears VRAM between stages
- Make sure at least 2.06 GB of free VRAM is available before the image stage
