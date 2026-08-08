# Writer — Local AI Story Writer

An AI agent that writes illustrated stories and renders them into a **PDF book** that
matches the exact layout of your sample book (`Second Light of March.pdf`): A5 pages,
Palatino Linotype typography, a cover, a contents page, section title pages, chapters
with running headers, and illustrations placed **between paragraphs**.

## How it works

```
story_writer.bat
      │  asks you: genre, premise, tone, length, title, author
      ▼
┌─────────────────┐      ┌──────────────────┐      ┌─────────────────┐
│  Local LLM      │      │  Image model     │      │  PDF builder    │
│  (LM Studio)    │ ───► │  (auto-detect)   │ ───► │  (reportlab)    │
│  1. outline     │      │  per-paragraph   │      │  replicates the │
│  2. chapters +  │      │  illustrations + │      │  sample layout  │
│     image ideas │      │  cover           │      │                 │
└─────────────────┘      └──────────────────┘      └─────────────────┘
```

1. **LM Studio (local LLM)** writes the story:
   - An outline (title, prologue, sections → chapters, epilogue, cover idea).
   - Each chapter as a set of scene-paragraphs, plus a one-line **image prompt** per
     paragraph (so the illustrations match the text).
2. **Image generation** creates one illustration per paragraph and a full-bleed cover.
3. **PDF builder** lays everything out in the sample book's format and saves it to
   `output/`.

## Quick start

1. Make sure **LM Studio** is running with the local server enabled
   (Developer tab → Start Server, default `http://localhost:1234/v1`) and at least one
   model loaded.
2. Double-click **`story_writer.bat`**.
3. Answer the questions (genre, premise, tone, length, title, author).
4. Wait — the PDF is built and opened automatically.

You can also run the pipeline directly:

```bat
py -3 -m src.pipeline --genre "fantasy" --topic "a young cartographer maps an
    uncharted sea" --tone "epic" --length medium
```

## Choosing the image model

LM Studio serves text models only, so illustrations need a separate backend.
`config.json → imagegen.backend` can be `auto` (default), `sdwebui`, `comfyui`,
`openai`, or `placeholder`. Auto-detection order:

| Backend | What it is | Requirement |
|---|---|---|
| `sdwebui` | Stable Diffusion WebUI (AUTOMATIC1111) | Run it locally, default port **7860** |
| `comfyui` | ComfyUI | Run it locally, port **8188**, plus an API-format workflow JSON path in `config.json` |
| `openai` | DALL-E / `gpt-image-1` | Put an API key in `config.json → imagegen.openai.api_key` |
| `placeholder` | gradient cards with captions | none — used for testing |

The pipeline picks the first available backend automatically. To get real artwork,
install and start **Stable Diffusion WebUI**:

```bat
git clone https://github.com/AUTOMATIC1111/stable-diffusion-webui
cd stable-diffusion-webui
webui.bat --api        :: keep it running, then start story_writer.bat
```

## Configuration (`config.json`)

| Section | Key | Meaning |
|---|---|---|
| `lmstudio` | `base_url`, `model` | LM Studio endpoint; `model` empty = auto-pick the largest loaded model |
| `lmstudio` | `temperature_*` | Creativity for outline vs. story |
| `story` | `language`, `length` | Story language and default length (`short`/`medium`/`long`) |
| `story` | `image_interval` | Put an image after every N-th paragraph (1 = after every paragraph) |
| `story` | `images_after_last_paragraph` | Also illustrate after the last paragraph of a chapter |
| `story` | `max_total_images` | Safety cap on the number of images generated |
| `imagegen` | `backend`, `style_prompt`, `negative_prompt` | Image backend + art style keywords |
| `imagegen` | `width`, `height`, `steps`, `cfg_scale`, `sampler` | SD WebUI settings |
| `pdf` | `image_max_width/height` | Max displayed size of in-text illustrations |

## Output

Each run creates `output/<title>-<timestamp>/` containing:

- `<title>.pdf` — the finished book
- `images/` — all generated illustrations (named `s<sec>_c<ch>_p<para>.png`)
- `story.json` — the full story (paragraphs + image prompts) for reuse

## Project layout

```
story_writer.bat      Interactive launcher (asks for genre, etc.)
config.json           Settings (LM Studio, image backend, layout)
src/
  pipeline.py         End-to-end orchestration + CLI
  lmstudio.py         LM Studio (OpenAI-compatible) client
  storygen.py         Outline + chapter generation (strict JSON, retries)
  imagegen.py         Image backends (SD WebUI / ComfyUI / OpenAI / placeholder)
  pdfbuilder.py       PDF layout replicating the sample book
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
- **No images / placeholder cards** → no local image server was detected. Start
  Stable Diffusion WebUI or set an OpenAI key.
