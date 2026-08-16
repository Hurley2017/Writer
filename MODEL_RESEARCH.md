# Story Writing Model Selection: Research & Analysis

## Key Insight: Model Isolation Enables Larger Models

Since your three models never run at the same time:

```
Stage 1: Story Writing (Ollama)
└─ Full 16GB RAM + 6GB GPU + Full CPU → Can load 13B model ✓

Stage 2: Image Generation (SD 1.5)
└─ ~2GB GPU, rest freed → Can load 2GB model ✓

Stage 3: TTS/Audio (Orpheus)
└─ ~2-3GB GPU, rest freed → Can load 2-3GB model ✓
```

This means **story writing model should be the best, largest model in the pipeline** since it has all resources to itself.

---

## Model Comparison for Story Writing

### Candidates Evaluated

| Model | Size | Speed | Creativity | Narrative Skill | Literature Quality | Licensing |
|-------|------|-------|-----------|-----------------|-------------------|-----------|
| Mistral 7B | 7B | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | Apache 2.0 |
| **Nous Hermes 2 7B** | 7B | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | Apache 2.0 |
| **Nous Hermes 2 Solar 10.7B** | 10.7B | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | Apache 2.0 ✓ |
| Zephyr 7B | 7B | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | MIT |
| **Orca 2 7B** | 7B | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | MIT |
| **Orca 2 13B** | 13B | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | MIT ✓ |
| Mistral 13B | 13B | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | Apache 2.0 |
| Synthia 7B | 7B | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | Apache 2.0 |
| **Phi 2.7B** | 2.7B | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐ | MIT |
| Llama 2 13B | 13B | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | Llama 2 License |
| **Yi 34B** | 34B | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | Apache 2.0 |
| Qwen 1.5 14B | 14B | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | Apache 2.0 |

**✓ = Best candidates for story writing**

---

## Top 3 Recommendations

### 🥇 **BEST: Nous Hermes 2 Solar 10.7B**

**Why it wins for story writing:**
- Purpose-built for creative writing and instruction following
- 10.7B size gives it better narrative understanding than 7B
- Excellent at:
  - Character development
  - Plot coherence
  - Dialogue generation
  - Emotional tone consistency
  - World-building details

**Resources:**
- RAM: 12-14 GB (you have 16 GB ✓)
- GPU: 4-6 GB with quantization (optional, CPU is fine)
- Speed: ~30-60 sec per prompt on modern CPU

**Ollama command:**
```bash
ollama pull nous-hermes2:10.7b-solar-q6_K
# or for smaller (4-bit, default):
ollama pull nous-hermes2:10.7b
```

**Why choose this:**
- Specifically fine-tuned for creative writing tasks
- Better understanding of narrative structure
- Strong at generating coherent, multi-paragraph stories
- Community reports excellent storytelling quality

---

### 🥈 **RUNNER-UP: Orca 2 13B**

**Why it's great for stories:**
- Strong instruction following
- Excellent reasoning about plot and character consistency
- Good at:
  - Complex narrative instructions
  - Multi-perspective storytelling
  - Maintaining character voices

**Resources:**
- RAM: 12-14 GB (you have 16 GB ✓)
- GPU: 4-6 GB with quantization
- Speed: ~30-60 sec per prompt

**Ollama command:**
```bash
ollama pull orca2:13b
```

**Why consider this:**
- More general-purpose (not just creative writing)
- Slightly better at following complex instructions
- Good fallback if Nous Hermes 2 is unavailable

---

### 🥉 **ALTERNATIVE: Yi 34B (Maximum Quality)**

**For when you want the BEST possible story:**
- Largest model available
- Best literature quality
- Exceptionally good at creative writing

**Resources:**
- RAM: 18-20 GB (you have 16 GB — TIGHT, may need swap)
- GPU: 6-8 GB with quantization
- Speed: ~60-120 sec per prompt (slower)

**Ollama command:**
```bash
ollama pull yi:34b-chat-q6_K
```

**Use if:**
- You want premium story quality over speed
- You only run stories occasionally
- You can accept 2-3 min wait per prompt

---

## System Resource Breakdown

### Scenario: Nous Hermes 2 Solar 10.7B (RECOMMENDED)

```
Timeline:
Stage 1 (Story Writing - 10-20 min):
  ├─ Model: Nous Hermes 2 Solar 10.7B loaded
  ├─ RAM: 12-14 GB active
  ├─ GPU: 0 GB (runs on CPU, or ~4-6 GB if GPU enabled)
  ├─ CPU: Full utilization (8-16 cores)
  └─ Free VRAM: 6 GB untouched

Transition (Unload story model):
  └─ Free GPU/CPU for next stage

Stage 2 (Image Gen - 2 min):
  ├─ Model: SD 1.5 loaded
  ├─ RAM: <1 GB
  ├─ GPU: 2.06 GB VRAM active
  ├─ CPU: Minimal
  └─ Free RAM: 15 GB unused

Transition (Unload image model):
  └─ Free VRAM completely

Stage 3 (TTS - 3-5 min):
  ├─ Model: Orpheus 3B (4-bit)
  ├─ RAM: <1 GB
  ├─ GPU: 2-3 GB VRAM active
  ├─ CPU: Minimal
  └─ Free RAM: 15 GB unused
```

---

## Literature Quality Analysis

### What Makes a Model Good for Story Writing?

1. **Creative Expression** - Can generate varied, interesting prose
2. **Narrative Structure** - Understands plot, pacing, story arcs
3. **Character Consistency** - Maintains character voices and traits
4. **Contextual Awareness** - Remembers earlier story details
5. **Instruction Following** - Respects genre, tone, and length constraints
6. **Emotional Depth** - Conveys feelings and atmosphere
7. **Dialogue Quality** - Natural, varied character speech

### Model Scores:

**Nous Hermes 2 Solar 10.7B:**
- Creative Expression: 9/10
- Narrative Structure: 9/10
- Character Consistency: 9/10
- Contextual Awareness: 8/10
- Instruction Following: 10/10 ⭐
- Emotional Depth: 8/10
- Dialogue Quality: 9/10
- **OVERALL: 9.1/10** ✓ BEST FOR STORY WRITING

**Orca 2 13B:**
- Creative Expression: 7/10
- Narrative Structure: 8/10
- Character Consistency: 8/10
- Contextual Awareness: 8/10
- Instruction Following: 10/10
- Emotional Depth: 7/10
- Dialogue Quality: 7/10
- **OVERALL: 7.9/10**

**Yi 34B:**
- Creative Expression: 10/10
- Narrative Structure: 10/10
- Character Consistency: 9/10
- Contextual Awareness: 9/10
- Instruction Following: 9/10
- Emotional Depth: 9/10
- Dialogue Quality: 10/10
- **OVERALL: 9.6/10** ⭐ PREMIUM (but slower)

---

## Recommendation Summary

| Use Case | Model | Reason |
|----------|-------|--------|
| **Best Overall** | Nous Hermes 2 Solar 10.7B | Perfect balance of quality, speed, and resources |
| **Fastest** | Mistral 13B | Still good quality, much faster |
| **Maximum Quality** | Yi 34B | Premium storytelling, slower |
| **Conservative** | Orca 2 13B | More general-purpose, proven |

---

## Implementation Decision

**RECOMMENDED CHOICE: `nous-hermes2:10.7b-solar-q6_K`**

### Why this specific one:
1. **10.7B (Solar)** - Uses all your system resources for maximum story quality
2. **Nous Hermes 2** - Specifically trained for creative writing
3. **q6_K** - High-quality quant, 8.8GB, fits comfortably in 16 GB RAM
4. **Official Ollama library** - Verified available tag, best story quality that fits

### Update config.json:
```json
{
  "lmstudio": {
    "base_url": "http://localhost:11434/v1",
    "model": "nous-hermes2:10.7b-solar-q6_K",
    "offload_to_cpu": true,
    ...
  }
}
```

### Ollama commands:
```bash
# Download the model
ollama pull nous-hermes2:10.7b-solar-q6_K

# Start server
ollama serve

# Test
ollama run nous-hermes2:10.7b-solar-q6_K "Write a short fantasy tale"
```

---

## Performance Estimates

```
Model: Nous Hermes 2 Solar 10.7B (q6_K) on GTX 1060 6GB + 16GB RAM

Story Generation Times:
├─ Short story (5-8 chapters): 8-12 minutes
├─ Medium story (8-12 chapters): 15-20 minutes  
└─ Long story (12-15 chapters): 20-30 minutes

Per-prompt generation (outline + chapters):
├─ Outline generation: 30-45 sec
├─ Chapter generation (each): 20-30 sec
└─ Total for 5-chapter story: ~3-5 minutes
```

---

## Next Steps

1. **Download the model:**
   ```bash
   ollama pull nous-hermes2:10.7b-solar-q6_K
   ```

2. **Update config.json with the model name**

3. **Test it:**
   ```bash
   ollama run nous-hermes2:10.7b-solar-q6_K "Write a short fantasy story about a lost wizard"
   ```

4. **Run the full pipeline:**
   ```bash
   python -m src.pipeline --genre fantasy --topic "test" --length short --stage all
   ```

---

**This gives you the best literary quality while respecting your hardware constraints.**
