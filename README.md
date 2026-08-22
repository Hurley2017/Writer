# Writer — Local AI Story Writer

An AI agent that writes **illustrated stories**, renders them into a **PDF book** that
matches the exact layout of your sample book (`Second Light of March.pdf`), and narrates
them into an **audiobook** — all local.

## How it works (three stages)

```
story_writer.bat  →  write_story.py   (one script, no VS Code needed)
      │  asks you: genre, premise, tone, length, title, author, language
      ▼
┌─────────────────────────┐   ┌──────────────────────┐   ┌──────────────────┐
│ STAGE 1 - draft         │   │ STAGE 2 - images     │   │ STAGE 3 - audio   │
│ LM Studio (Gemma 31B)   │──►│ RealVisXL (SDXL)     │──►│ Orpheus 3B TTS    │
│ writes outline+chapters │   │ fills every paragraph│   │ narrates with     │
│ + draft PDF with        │   │ placeholder with a   │   │ emotion tags +    │
│ placeholder images      │   │ real illustration    │   │ rebuilds audiobook│
└─────────────────────────┘   └──────────────────────┘   └──────────────────┘
```

1. **STAGE 1 — Draft**: the local LLM (**Gemma 31B** in LM Studio) writes the book
   (outline → sections → chapters), and for each chapter produces the paragraphs,
   an **image prompt per paragraph**, and an **emotion per paragraph**. A fast draft
   PDF is built with placeholder images.
2. **STAGE 2 — Images**: **RealVisXL (SDXL)** generates the **cover** as a real picture
   from the story, and one **abstract art** piece per paragraph (themed by that
   paragraph's emotion - calm, sad, tense, joyful...), then rebuilds the final PDF.
   The SDXL model is unloaded from the GPU as soon as the images are done.
3. **STAGE 3 — Audio**: **Orpheus 3B** (local, GPU-accelerated, ~2.4 GB VRAM in 4-bit)
   narrates with **dual voices**: each chapter title is ANNOUNCED by one voice and the
   story body is READ by the other. The narrator voice follows the protagonist's gender
   (female → `jess`, male → `zac`), decided automatically from the story's
   `protagonist_gender` field (with `--narrator` override). Emotion tags (`<sigh>`,
   `<gasp>`, `<laugh>`...) are injected INLINE (after the first sentence) so the model
   performs them. Output is 24 kHz, per-chapter WAVs + one `audiobook.wav`.

## Quick start

1. Make sure **LM Studio** is running with the local server enabled
   (Developer tab → Start Server, default `http://localhost:1234/v1`) and **Gemma 31B**
   loaded.
2. Double-click **`story_writer.bat`** (or run `write_story.py` with the venv Python).
   No VS Code needed.
3. Answer the questions (genre, premise, tone, length, title, author, language).
4. Wait — it runs all three stages: story → draft PDF → real illustrations → final PDF
   → audiobook, then opens the finished PDF.

The first run downloads Orpheus' 4-bit weights (~2.2 GB) and RealVisXL is used from
`D:\stable-diffusion-webui\models\Stable-diffusion\`; everything is cached on `D:`.

You can also run stages independently (advanced / power use):

```bat
:: full pipeline
py -3 -m src.pipeline --genre "fantasy" --topic "a young cartographer maps an
    uncharted sea" --tone "epic" --length medium

:: only fill real images for an existing story
py -3 -m src.pipeline --stage images --story output/<book>/story.json

:: only generate the audiobook (Orpheus)
py -3 -m src.pipeline --stage audio --story output/<book>/story.json
```

## Choosing the image model

Image generation produces the **cover** (front + back) **and one illustration per
paragraph** (the current pipeline default). Two ways to generate them:

### 1. Embedded Stable Diffusion (standalone — recommended)
The SD model is loaded **directly inside the pipeline** (HuggingFace `diffusers`) — no
separate server needed. Everything runs in one command and produces the PDF.

1. Install torch with CUDA support (once):
   ```bat
   pip install torch torchvision --index-url https://download.pytorch.org/whl/cu128
   pip install diffusers transformers accelerate safetensors
   ```
2. Put any SD 1.5/SDXL `.safetensors` checkpoint somewhere and point
   `config.json → imagegen.diffusers.model_path` at it.
3. Run `story_writer.bat` (option 2 in the advanced menu) or
   `py -3 -m src.pipeline --backend diffusers ...`.

### 2. Image server (optional)
LM Studio serves text models only, so you can instead run a separate image server.
`config.json → imagegen.backend` can be `auto`, `diffusers`, `sdwebui`, `comfyui`,
`openai`, or `placeholder`. Auto-detection order: **diffusers → sdwebui → comfyui →
placeholder**.

| Backend | What it is | Requirement |
|---|---|---|
| `diffusers` | Embedded SD (standalone) | torch + diffusers installed, model file in `config.json` |
| `sdwebui` | Stable Diffusion WebUI (AUTOMATIC1111) | Run it locally, default port **7860** |
| `comfyui` | ComfyUI | Run it locally, port **8188**, plus an API-format workflow JSON path in `config.json` |
| `openai` | DALL-E / `gpt-image-1` | Put an API key in `config.json → imagegen.openai.api_key` |
| `placeholder` | gradient cards with captions | none — used for testing |

> **Note for RTX 50-series (Blackwell) GPUs**: you need torch ≥ 2.7, e.g.
> `pip install torch --index-url https://download.pytorch.org/whl/cu128`.
> Older AUTOMATIC1111 installs pin torch 2.1.2, which neither supports Python 3.14
> nor Blackwell GPUs.

## Configuration (`config.json`)

| Section | Key | Meaning |
|---|---|---|
| `lmstudio` | `base_url`, `model` | LM Studio endpoint; `model` = `google/gemma-4-31b-qat` (Gemma 31B) |
| `lmstudio` | `temperature_*` | Creativity for outline vs. story |
| `story` | `language`, `length` | Story language and default length (`short`/`medium`/`long`) |
| `pdf` | `divider` | Draw an abstract ornament between paragraphs (default `true`) |
| `imagegen` | `backend`, `style_prompt`, `negative_prompt` | Image backend + art style keywords |
| `imagegen` | `width`, `height`, `steps`, `cfg_scale`, `sampler` | SD settings |
| `imagegen.diffusers` | `model_path`, `hf_cache_dir` | SDXL checkpoint path + HF cache on `D:` |
| `tts` | `backend`, `voice_female`, `voice_male` | `orpheus`; female narrator (`jess`) + male narrator (`zac`) |
| `tts` | `narrator` | `auto` (from story) / `male` / `female` - which voice reads the body |
| `tts` | `model`, `hf_cache_dir` | 4-bit Orpheus repo id + HF cache dir |
| `pdf` | `divider` | Abstract ornament between paragraphs (default `true`) |

## Output

Each run creates `output/<title>-<timestamp>/` containing:

- `<title>.pdf` — the finished book (picture cover + abstract art per paragraph)
- `<title>-draft.pdf` — fast draft with placeholder cards
- `images/` — the generated cover + per-paragraph abstract art
- `audio/` — per-chapter WAVs + `audiobook.wav` (24 kHz, Orpheus dual voices)
- `story.json` — the full story (paragraphs, image prompts, emotions) for reuse

## Run all models on a headless Debian server (GTX 1060)

Instead of running the models on this PC, point the pipeline at a headless
Debian server on the LAN (`server/` folder in this repo):

| Service | Port | Runs on server | Config key |
|---|---|---|---|
| llama.cpp LLM (Qwen2.5-7B Q4) | 1234 | story writer | `lmstudio.base_url` |
| SD WebUI A1111 (Realistic Vision) | 7860 | cover + abstract art | `imagegen.sdwebui_url` + `backend=sdwebui` |
| Orpheus 3B TTS | 8000 | audiobook | `tts.server_url` + `backend=orpheus-http` |

`config.json` is pre-wired for `192.168.0.103`. See **`server/README.md`** for
the one-command install, the model choices (GTX 1060 = SD 1.5, not SDXL; Orpheus
in float16, not bfloat16), and how to switch back to fully-local.

## Project layout

```
story_writer.bat      Double-click launcher (finds Python, checks deps, runs the script)
write_story.py        THE single script - interactive, runs the full 3-stage pipeline
config.json           Settings (LM Studio, image backend, TTS voice, layout)
src/
  pipeline.py         End-to-end orchestration + CLI
  lmstudio.py         LM Studio (OpenAI-compatible) client
  storygen.py         Outline + chapter generation (strict JSON, retries)
  imagegen.py         Image backends (diffusers / SD WebUI / ComfyUI / OpenAI / placeholder)
  pdfbuilder.py       PDF layout replicating the sample book
  tts.py              Orpheus 3B audiobook (emotion tags, SNAC decode)
tools/                Analysis + test scripts for the layout
```

## Layout replication notes

The sample PDF was analyzed with PyMuPDF and reproduced in `pdfbuilder.py`:

- A5 portrait, ~31.2 pt margins, body Palatino 9.5 pt justified, leading 15
- Cover + back cover: full-bleed generated images
- Contents: bold 16 pt title, bold 10 pt sections, indented 9.5 pt chapters with
  right-aligned page numbers
- Chapter/Prologue/Epilogue first pages: italic 9 pt centered title, body starts at y≈68.6
- Continuation pages: italic 7 pt centered running header, body starts at y≈48.8
- Section pages: bold 20 pt centered title + italic chapter list
- Footer: italic 7 pt centered page number

## Troubleshooting

- **"Cannot reach LM Studio"** → start LM Studio, load a model, enable the server.
- **"Model did not return valid JSON"** → a small model occasionally writes prose
  instead of JSON. The pipeline retries automatically; if it still fails, pick a
  larger model in the advanced menu (or `--model <id>`).
- **No images / placeholder cards** → no local image backend was detected. Set
  `config.json → imagegen.diffusers.model_path` to the RealVisXL checkpoint
  (embedded diffusers, recommended) or start a server.
- **Orpheus model download fails** → the 4-bit model is fetched from HuggingFace
  (`unsloth/orpheus-3b-0.1-ft-unsloth-bnb-4bit`) into `D:\hf_cache`. If it fails,
  check the cache dir has space, or set `tts.model` in `config.json` to another
  public mirror.
- **Slow / CPU-only TTS** → the 4-bit model must load on CUDA (it reports
  `Orpheus on cuda:0`). VRAM used is ~2.4 GB at load and up to ~7 GB during
  generation on the RTX 5060 — close the SD stage before generating audio if tight.
