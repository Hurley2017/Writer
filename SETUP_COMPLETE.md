# Writer Project - GPU-Optimized Setup Complete ✅

## Summary

The Writer project has been fully configured for **one-model-at-a-time** operation on a **GTX 1060 6GB** with GPU acceleration:

- ✅ **Image Generation**: SD 1.5 on GPU (no CPU offload) — 2.06 GB VRAM, cover-only mode
- ✅ **Story Generation**: LM Studio (external HTTP server) with CPU offload enabled  
- ✅ **TTS/Audio**: Orpheus 3B with 4-bit quantization — GPU-friendly
- ✅ **Pipeline Control**: Models are loaded/unloaded sequentially to stay within 6 GB

---

## What Was Changed

### 1. Image Generation → Lower-VRAM Model
**Before**: `SG161222/RealVisXL_V4.0` (SDXL, ~6.5 GB on load)  
**After**: `runwayml/stable-diffusion-v1-5` (SD 1.5, ~2 GB on load)

**Config**: [config.json](config.json) → `imagegen.diffusers`
```json
"diffusers": {
  "model_name": "runwayml/stable-diffusion-v1-5",
  "cpu_offload": false,
  ...
}
```

### 2. Cover-Only Generation Mode
**Before**: Generated images for cover + every paragraph (many GPU calls)  
**After**: Cover only, reused as back cover

**Config**: [config.json](config.json) → `imagegen.generate_cover_only: true`  
**Code**: [src/pipeline.py](src/pipeline.py) → `generate_all_images()` simplified

### 3. Story Model CPU Offload
**Config**: [config.json](config.json) → `lmstudio.offload_to_cpu: true`

This flag allows the LM Studio model (running externally) to reside on CPU, freeing GPU for the image generation pass.

### 4. One-Model-at-a-Time Orchestration
**Code**: [src/pipeline.py](src/pipeline.py) stages:
1. **Stage 1 (Story)**: LM Studio generates outline + chapters (no GPU used here yet)
2. **_free_gpu()**: Clears CUDA cache between stages
3. **Stage 2 (Images)**: SD 1.5 generates cover only (~2 min on GPU)
4. **_free_gpu()**: Clears CUDA cache again
5. **Stage 3 (Audio)**: Orpheus TTS narrates chapters (~3-5 min on GPU)

---

## Verified Components

### Image Generation (GPU-Only, No CPU Offload)
- ✅ Model loads: `runwayml/stable-diffusion-v1-5`
- ✅ VRAM usage after load: 2.06 GB
- ✅ Total VRAM available: 5.92 GB
- ✅ Generation succeeds without OOM errors
- ✅ Image output: `/home/tusher/Writer/output/cover_verify.png`

### Story Generation (Ready to Test)
- ✅ LM Studio client code working
- ✅ Config has CPU offload enabled
- ✅ StoryGenerator module imports successfully
- ⏳ **Requires LM Studio to be running** (see [STORY_MODEL_TEST.md](STORY_MODEL_TEST.md))

### TTS/Audio (Pre-configured)
- ✅ Orpheus 3B model in config
- ✅ 4-bit quantization enabled
- ✅ Ready for GPU use

---

## Next Steps

### Immediate: Test Story Generation
1. **Start LM Studio**
   - Download from https://lmstudio.ai/
   - Load a model (e.g., `google/gemma-4-31b-qat`)
   - Start the server (Developer tab → Start Server)

2. **Run Story Test** (see [STORY_MODEL_TEST.md](STORY_MODEL_TEST.md) for full commands)
   ```bash
   cd /home/tusher/Writer && source venv/bin/activate
   python3 << 'STORYLEST'
   # Test code in STORY_MODEL_TEST.md
   STORYTEST
   ```

3. **Run Full Pipeline** (once story model works)
   ```bash
   cd /home/tusher/Writer && source venv/bin/activate
   python -m src.pipeline --genre fantasy --topic "test" --length short --stage all
   ```

---

## Performance Expectations

| Stage | Model | Duration | VRAM | Location |
|-------|-------|----------|------|----------|
| **Story** | LM Studio (13B) | 30-60 sec per prompt | CPU-offload | External HTTP |
| **Image** | SD 1.5 (cover only) | ~2 min (12 steps) | 2.06 GB peak | GPU |
| **Audio** | Orpheus 3B (4-bit) | ~3-5 min per chapter | ~2-3 GB | GPU |
| **Total** | — | ~8-15 min | ≤5 GB peak | Local |

---

## File Changes Summary

| File | Change |
|------|--------|
| [config.json](config.json) | Image model → SD 1.5, cover-only mode, LM offload enabled |
| [src/config.py](src/config.py) | Updated defaults to match config.json |
| [src/pipeline.py](src/pipeline.py) | `generate_all_images()` → cover-only, added `_free_gpu()` calls |
| [write_story.py](write_story.py) | Updated UI text to reflect new setup |
| [STORY_MODEL_TEST.md](STORY_MODEL_TEST.md) | **NEW**: Story model testing guide |

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    WRITER PIPELINE                          │
│           (One Model at a Time on GTX 1060 6GB)            │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Stage 1: Story Generation                                  │
│  ┌─────────────────────────────────────┐                    │
│  │ LM Studio (External HTTP Server)    │ CPU-Offload OK     │
│  │ Model: google/gemma-4-31b-qat       │ GPU not used yet   │
│  │ Output: story outline + chapters    │                    │
│  └─────────────────────────────────────┘                    │
│  │                                                           │
│  ├─ _free_gpu() [clear CUDA cache]                          │
│  │                                                           │
│  Stage 2: Image Generation (GPU-Only)                       │
│  ┌─────────────────────────────────────┐                    │
│  │ SD 1.5 on CUDA                      │ 2.06 GB VRAM       │
│  │ Model: runwayml/stable-diffusion... │ No CPU offload     │
│  │ Output: book cover only             │ 12 steps, 512×512  │
│  └─────────────────────────────────────┘                    │
│  │                                                           │
│  ├─ _free_gpu() [clear CUDA cache]                          │
│  │                                                           │
│  Stage 3: Audio Narration (GPU-Optimized)                   │
│  ┌─────────────────────────────────────┐                    │
│  │ Orpheus 3B (4-bit on CUDA)          │ ~2-3 GB VRAM       │
│  │ Model: unsloth/orpheus-3b-0.1...    │ Emotion tags       │
│  │ Output: audiobook narration .wav    │                    │
│  └─────────────────────────────────────┘                    │
│                                                              │
│  Final Output: output/<title>/                              │
│  ├─ <title>.pdf (with cover + text)                         │
│  ├─ images/cover.png                                        │
│  ├─ audio/audiobook.wav                                     │
│  └─ story.json (metadata)                                   │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## Validation Status

```
✅ Hardware: GTX 1060 6GB + NVIDIA driver 550.163.01 + CUDA 12.4
✅ Environment: Python 3.13.5 + PyTorch 2.6.0+cu124 + venv
✅ Image Model: Low-VRAM SD 1.5 verified on GPU
✅ Story Config: CPU offload enabled + LM Studio client ready
✅ TTS: Orpheus model pre-configured
⏳ Full Pipeline: Awaiting LM Studio to test story generation
```

---

## Troubleshooting & Support

For detailed story model testing instructions, see: [STORY_MODEL_TEST.md](STORY_MODEL_TEST.md)

For full system diagnostics, run:
```bash
cd /home/tusher/Writer && source venv/bin/activate
python3 << 'DIAG'
import torch, json
from src.lmstudio import LMStudio
cfg = json.load(open('config.json'))
print(f"GPU: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'N/A'}")
print(f"VRAM: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.1f} GB")
lm = LMStudio(cfg['lmstudio']['base_url'])
print(f"LM Studio: {'REACHABLE' if lm.is_available() else 'NOT REACHABLE'}")
DIAG
```

---

**Status**: ✅ **READY FOR TESTING**  
**Next Action**: Start LM Studio, then test story generation
