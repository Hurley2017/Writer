"""End-to-end story pipeline - three stages:

  Stage 1 (draft)  : LM Studio (Gemma 31B) writes the story, then builds a
                     draft PDF with placeholder images (fast).
  Stage 2 (images) : RealVisXL fills every placeholder with a real illustration
                     for the current chapter/paragraph and rebuilds the final PDF.
  Stage 3 (audio)  : Orpheus 3B TTS narrates the story into an audiobook
                     (emotion tags per paragraph).

Run everything:        py -3 -m src.pipeline --genre ... 
Run one stage only:    py -3 -m src.pipeline --stage images --story output/<book>/story.json
"""
import argparse
import datetime
import json
import os
import re
import sys

try:
    from .config import load_config
    from .lmstudio import LMStudio, LMStudioError
    from .storygen import StoryGenerator
    from . import imagegen
    from . import pdfbuilder
    from . import tts
except ImportError:  # allows `python src/pipeline.py` as well as `python -m src.pipeline`
    _here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _here not in sys.path:
        sys.path.insert(0, _here)
    from src.config import load_config
    from src.lmstudio import LMStudio, LMStudioError
    from src.storygen import StoryGenerator
    from src import imagegen
    from src import pdfbuilder
    from src import tts

DEFAULT_MODEL = "google/gemma-4-31b-qat"


def slugify(text, maxlen=60):
    s = re.sub(r"[^A-Za-z0-9]+", "-", text).strip("-").lower()
    return s[:maxlen] or "story"


# emotion label -> abstract art prompt used for the per-paragraph ornament
# (the cover keeps its real picture; paragraphs get emotion-themed abstract art)
ABSTRACT_ART = {
    "calm": "abstract art, soft pastel gradients, smooth flowing shapes, serene minimalist composition, gentle light, high quality digital art, no text, no letters",
    "neutral": "abstract art, balanced geometric forms, neutral grey and beige palette, clean modern composition, high quality digital art, no text, no letters",
    "warm": "abstract art, warm amber and honey tones, soft glowing orbs, cozy gentle forms, high quality digital art, no text, no letters",
    "somber": "abstract art, dark muted indigo and charcoal washes, heavy slow shapes, quiet grief, soft edges, high quality digital art, no text, no letters",
    "mysterious": "abstract art, deep violet fog, hidden geometric shapes, moonlit haze, enigmatic composition, high quality digital art, no text, no letters",
    "tense": "abstract art, sharp jagged black and crimson shapes, high contrast, dynamic diagonal lines, high quality digital art, no text, no letters",
    "sad": "abstract art, muted blue and grey washes, blurred drifting forms, melancholic haze, soft focus, high quality digital art, no text, no letters",
    "dramatic": "abstract art, bold chiaroscuro, deep reds and golds, sweeping dramatic brushstrokes, cinematic light, high quality digital art, no text, no letters",
    "fearful": "abstract art, dark swirling shadows, cold blue highlights, chaotic angular forms, ominous mood, high quality digital art, no text, no letters",
    "excited": "abstract art, vibrant electric colors, explosive radiating shapes, dynamic motion, high energy, high quality digital art, no text, no letters",
    "joyful": "abstract art, bright warm yellows and pinks, playful curves, radiant light, cheerful energy, high quality digital art, no text, no letters",
    "angry": "abstract art, violent red and black slashes, aggressive angular shards, raw texture, high quality digital art, no text, no letters",
    "": "abstract art, elegant flowing shapes, harmonious palette, high quality digital art, no text, no letters",
}


def _model_ok(lm, model):
    """Tiny probe to confirm a model actually loads and responds in LM Studio."""
    try:
        text = lm.chat(
            [{"role": "user", "content": "Reply with exactly the single word: ok"}],
            model=model, temperature=0, max_tokens=5, timeout=120,
        )
        return bool(text and "ok" in text.lower())
    except LMStudioError:
        return False


def pick_model(lm, requested):
    """Choose a model that actually works. Auto mode prefers the largest loaded
    model, but skips any that fail to load/respond (e.g. out-of-memory crashes)."""
    models = lm.list_models()
    if not models:
        raise LMStudioError("LM Studio is running but returned no models. Load a model in LM Studio first.")
    preferred = [m for m in models if "embed" not in m.lower()]
    if not preferred:
        preferred = models

    if requested and requested in models:
        candidates = [requested] + [m for m in preferred if m != requested]
    else:
        def size_rank(name):
            m = re.search(r"(\d+(?:\.\d+)?)b", name.lower())
            return float(m.group(1)) if m else 0.0
        candidates = sorted(preferred, key=size_rank, reverse=True)

    failed = []
    for m in candidates:
        if _model_ok(lm, m):
            if failed:
                print(f"[!] Skipped model(s) that failed to load: {failed}")
            return m
        failed.append(m)
    raise LMStudioError(
        "None of the loaded models responded. Tried: "
        + ", ".join(failed)
        + ". Check in LM Studio that a model can actually load and run."
    )


def check_environment(cfg, args):
    print("=" * 60)
    print("Environment check")
    print("=" * 60)
    lm = LMStudio(cfg["lmstudio"]["base_url"])
    if lm.is_available():
        models = lm.list_models()
        print(f"[OK] LM Studio reachable at {cfg['lmstudio']['base_url']}")
        for m in models:
            print(f"     - {m}")
        if not models:
            print("[!] No models loaded - load one in LM Studio.")
    else:
        print(f"[X] LM Studio NOT reachable at {cfg['lmstudio']['base_url']}")

    backend = imagegen.detect_backend(cfg, force=args.backend)
    names = {"diffusers": "EMBEDDED Stable Diffusion (diffusers, standalone)",
             "sdwebui": "Stable Diffusion WebUI (local)",
             "comfyui": "ComfyUI (local)",
             "openai": "OpenAI Images API",
             "placeholder": "placeholder images (no server)"}
    print(f"[OK] Image backend selected: {names.get(backend, backend)}")
    if backend == "diffusers":
        mp = cfg["imagegen"].get("diffusers", {}).get("model_path", "")
        print(f"     Model: {mp}")
    elif backend == "placeholder":
        print("     No SD model configured and no image server detected.")
        print("     Set config.json -> imagegen.diffusers.model_path to a .safetensors checkpoint")
        print("     (and install torch + diffusers) for real art, or use an OpenAI key.")
    for mod in ("requests", "PIL", "reportlab", "pymupdf", "diffusers", "torch"):
        try:
            __import__(mod)
            print(f"[OK] Python package: {mod}")
        except ImportError:
            print(f"[X] Missing Python package: {mod} (run: pip install -r requirements.txt)")
    return 0


def collect_story_params(args):
    return {
        "genre": args.genre,
        "topic": args.topic,
        "tone": args.tone,
        "length": args.length,
        "title": args.title,
        "language": args.language,
        "author": args.author,
        "narrator": args.narrator,
    }


def write_story(cfg, args):
    """Stage 0: use LM Studio to write the story (outline + chapters)."""
    lm = LMStudio(cfg["lmstudio"]["base_url"])
    if not lm.is_available():
        raise LMStudioError(
            "LM Studio is not running. Start LM Studio, load a model, and start the "
            "local server, then run the batch file again."
        )
    model = pick_model(lm, args.model or cfg["lmstudio"].get("model"))
    print(f"Using LM Studio model: {model}")
    gen = StoryGenerator(lm, model, cfg)
    params = collect_story_params(args)

    print("\n[1/3] Planning the book outline ...")
    outline = gen.generate_outline(params)
    title = outline.get("title") or params.get("title") or "Untitled"
    print(f"      Title: {title}")
    for i, sec in enumerate(outline.get("sections", [])):
        print(f"      Section {i+1}: {sec.get('title')} -> {len(sec.get('chapters', []))} chapters")

    story = {
        "title": title,
        "author": params.get("author") or "",
        "cover_prompt": outline.get("cover_prompt", ""),
        "narrator": params.get("narrator") or outline.get("protagonist_gender", "auto"),
        "prologue": None,
        "sections": [],
        "epilogue": None,
    }
    print("\n[1/3] Writing the story (this can take a while) ...")
    if outline.get("prologue"):
        print("      - Prologue")
        data = gen.generate_chapter(outline, "Prologue", "Prologue", 0, params)
        story["prologue"] = {"title": "The Opening", "paragraphs": data["paragraphs"],
                             "image_prompts": data.get("image_prompts", []),
                             "emotions": data.get("emotions", [])}
    ch = 0
    for si, sec in enumerate(outline.get("sections", [])):
        chapters = []
        for c in sec.get("chapters", []):
            ch += 1
            print(f"      - Chapter {ch}: {c}")
            data = gen.generate_chapter(outline, sec.get("title", ""), c, ch, params)
            chapters.append({"title": c, "paragraphs": data["paragraphs"],
                             "image_prompts": data.get("image_prompts", []),
                             "emotions": data.get("emotions", [])})
        story["sections"].append({"title": sec.get("title", ""), "chapters": chapters})
    if outline.get("epilogue"):
        print("      - Epilogue")
        data = gen.generate_chapter(outline, "Epilogue", "Epilogue", 0, params)
        story["epilogue"] = {"title": "The Closing", "paragraphs": data["paragraphs"],
                             "image_prompts": data.get("image_prompts", []),
                             "emotions": data.get("emotions", [])}
    # best-effort: unload the LLM from LM Studio so SD/TTS have free VRAM
    try:
        import requests as _req
        _req.post(cfg["lmstudio"]["base_url"] + "/models/unload",
                  json={"model": model}, timeout=10)
    except Exception:
        pass
    return story


def generate_all_images(cfg, backend, story, out_dir):
    """Generate only the book cover and reuse it as the back cover."""
    images = {}
    images_dir = os.path.join(out_dir, "images")
    os.makedirs(images_dir, exist_ok=True)
    title = story.get("title", "Story")
    cw, chh = cfg["imagegen"]["cover_size"]

    if cfg["imagegen"].get("generate_cover_only", True):
        print("      - Cover image only (no inline page illustrations) ...")
        images["cover"] = imagegen.generate_and_save(
            backend, story.get("cover_prompt") or f"an atmospheric cover for '{title}'",
            cw, chh, os.path.join(images_dir, "cover.png"), caption=title)
        images["back"] = images["cover"]
        return images

    print("      - Cover image ...")
    images["cover"] = imagegen.generate_and_save(
        backend, story.get("cover_prompt") or f"an atmospheric cover for '{title}'",
        cw, chh, os.path.join(images_dir, "cover.png"), caption=title)
    images["back"] = images["cover"]
    return images


def _pdf_opts(cfg):
    return {
        "divider": cfg["pdf"].get("divider", True),
        "image_max_width": cfg["pdf"].get("image_max_width", 300),
        "image_max_height": cfg["pdf"].get("image_max_height", 340),
    }


def stage_draft(cfg, story, out_dir):
    """Stage 1: placeholder images + draft PDF (fast)."""
    print("\n[2/3] Building draft PDF with placeholder images ...")
    backend = imagegen.Placeholder(cfg)
    images = generate_all_images(cfg, backend, story, out_dir)
    pdf_path = os.path.join(out_dir, f"{slugify(story['title'])}-draft.pdf")
    pdfbuilder.build_pdf(story, images, pdf_path, opts=_pdf_opts(cfg))
    print(f"      Draft PDF: {pdf_path} ({pdfbuilder_summary(pdf_path)} pages)")
    return pdf_path


def stage_images(cfg, story, out_dir):
    """Stage 2: RealVisXL fills every placeholder with a real illustration."""
    print("\n[2/3] Generating real illustrations ...")
    backend, backend_id = imagegen.create_backend(cfg)
    print(f"      Image backend: {backend_id}")
    if backend_id == "placeholder":
        print("      No real image backend available (install torch+diffusers and set "
              "imagegen.diffusers.model_path).")
        return None
    images = generate_all_images(cfg, backend, story, out_dir)
    pdf_path = os.path.join(out_dir, f"{slugify(story['title'])}.pdf")
    pdfbuilder.build_pdf(story, images, pdf_path, opts=_pdf_opts(cfg))
    print(f"      Final PDF: {pdf_path} ({pdfbuilder_summary(pdf_path)} pages)")
    if hasattr(backend, "free"):
        backend.free()
    return pdf_path


def _free_gpu():
    """Release GPU memory between stages so the next model can load."""
    import gc
    try:
        import torch
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except Exception:
        pass


def stage_audio(cfg, story, out_dir):
    """Stage 3: Orpheus TTS narrates the story (emotion tags per paragraph)."""
    print("\n[3/3] Generating the audiobook ...")
    gen = tts.AudiobookGenerator(cfg)
    audio_dir = os.path.join(out_dir, "audio")
    files = gen.generate_book(story, audio_dir)
    print(f"      {len(files)} chapter audio files -> {audio_dir}")
    return files


def main(argv=None):
    ap = argparse.ArgumentParser(description="AI Story Writer pipeline (3 stages)")
    ap.add_argument("--check", action="store_true", help="check the environment and exit")
    ap.add_argument("--stage", default="all",
                    choices=["draft", "images", "audio", "all"],
                    help="which stage(s) to run (default: all)")
    ap.add_argument("--story", default=None,
                    help="path to an existing story.json (skips story writing)")
    ap.add_argument("--out", default=None, help="output directory (default: output/<title>-<ts>)")
    ap.add_argument("--genre", default=None, help="story genre (sci-fi, romance, fantasy, ...)")
    ap.add_argument("--topic", default=None, help="premise / topic / elements you want")
    ap.add_argument("--tone", default=None, help="tone (dark, light, humorous, epic, ...)")
    ap.add_argument("--length", default=None, choices=["short", "medium", "long"],
                    help="story length")
    ap.add_argument("--title", default=None, help="book title (or let the model invent one)")
    ap.add_argument("--author", default=None, help="author name for the PDF")
    ap.add_argument("--language", default=None, help="story language")
    ap.add_argument("--narrator", default=None, choices=["auto", "male", "female"],
                    help="narrator gender (auto = decide from the story; default: auto)")
    ap.add_argument("--model", default=None, help="LM Studio model id")
    ap.add_argument("--backend", default=None,
                    help="image backend: auto|diffusers|sdwebui|comfyui|openai|placeholder")
    ap.add_argument("--no-open", action="store_true", help="do not open the PDF at the end")
    args = ap.parse_args(argv)

    # ---- silence known-harmless third-party warnings (deprecations, fallbacks) ----
    import warnings
    warnings.filterwarnings("ignore", message=".*torchvision.*")
    warnings.filterwarnings("ignore", message=".*Siglip.*")
    warnings.filterwarnings("ignore", message=".*deprecated.*")
    warnings.filterwarnings("ignore", message=".*kept in float32.*")
    warnings.filterwarnings("ignore", message=".*triton not found.*")
    warnings.filterwarnings("ignore", message=".*unauthenticated requests.*")
    warnings.filterwarnings("ignore", message=".*Both `max_new_tokens`.*")

    cfg = load_config()

    if args.check:
        return check_environment(cfg, args)

    if args.length:
        cfg["story"]["length"] = args.length
    if args.language:
        cfg["story"]["language"] = args.language
    if args.backend:
        cfg["imagegen"]["backend"] = args.backend

    # ----- redirect HuggingFace cache to a big drive & avoid Windows symlink errors -----
    hf_cache = cfg["imagegen"].get("diffusers", {}).get("hf_cache_dir", "")
    if hf_cache:
        os.environ["HF_HOME"] = hf_cache
        os.environ["HF_HUB_CACHE"] = os.path.join(hf_cache, "hub")
    os.environ["HF_HUB_DISABLE_SYMLINKS"] = "1"
    os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
    os.makedirs(os.environ.get("HF_HUB_CACHE", ""), exist_ok=True)

    # ----- load or write the story -----
    if args.story:
        with open(args.story, "r", encoding="utf-8") as f:
            story = json.load(f)
        out_dir = args.out or os.path.dirname(os.path.abspath(args.story))
        print(f"Loaded story: {story.get('title', '?')} ({len(story.get('sections', []))} sections)")
    else:
        story = write_story(cfg, args)
        out_dir = args.out or os.path.join(
            cfg["output"]["dir"],
            f"{slugify(story['title'])}-{datetime.datetime.now():%Y%m%d-%H%M%S}")
        os.makedirs(out_dir, exist_ok=True)
        with open(os.path.join(out_dir, "story.json"), "w", encoding="utf-8") as f:
            json.dump(story, f, ensure_ascii=False, indent=2)
        print(f"Story saved: {os.path.join(out_dir, 'story.json')}")

    # ----- run the requested stage(s) -----
    pdf_path = None
    if args.stage in ("draft", "all"):
        pdf_path = stage_draft(cfg, story, out_dir)
    if args.stage in ("images", "all"):
        pdf_path = stage_images(cfg, story, out_dir) or pdf_path
        _free_gpu()  # release the SDXL model before the TTS model loads
    if args.stage in ("audio", "all"):
        stage_audio(cfg, story, out_dir)

    print("\n" + "=" * 60)
    print("Done!")
    print(f"  Story : {story.get('title')}")
    if pdf_path and os.path.exists(pdf_path):
        print(f"  PDF   : {os.path.abspath(pdf_path)}")
    print(f"  Output: {os.path.abspath(out_dir)}")
    print("=" * 60)

    if pdf_path and cfg["output"].get("open_pdf") and not args.no_open:
        try:
            os.startfile(os.path.abspath(pdf_path))  # Windows
        except Exception:
            pass
    return 0


def pdfbuilder_summary(pdf_path):
    try:
        import pymupdf
        d = pymupdf.open(pdf_path)
        n = d.page_count
        d.close()
        return n
    except Exception:
        return "?"


def entry():
    try:
        raise SystemExit(main())
    except (LMStudioError, tts.AudiobookError, RuntimeError, ValueError) as e:
        print(f"\nERROR: {e}", file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    entry()
