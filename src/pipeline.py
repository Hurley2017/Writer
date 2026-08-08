"""End-to-end story pipeline:
  1. Ask the local LLM (LM Studio) for a book outline
  2. Ask it for each chapter's paragraphs + image prompts
  3. Generate illustrations with the configured image backend
  4. Render everything into a PDF that replicates the sample book layout
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
except ImportError:  # allows `python src/pipeline.py` as well as `python -m src.pipeline`
    _here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _here not in sys.path:
        sys.path.insert(0, _here)
    from src.config import load_config
    from src.lmstudio import LMStudio, LMStudioError
    from src.storygen import StoryGenerator
    from src import imagegen
    from src import pdfbuilder

DEFAULT_MODEL = "llama-3.2-3b-instruct"


def slugify(text, maxlen=60):
    s = re.sub(r"[^A-Za-z0-9]+", "-", text).strip("-").lower()
    return s[:maxlen] or "story"


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
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description="AI Story Writer pipeline")
    ap.add_argument("--check", action="store_true", help="check the environment and exit")
    ap.add_argument("--genre", default=None, help="story genre (sci-fi, romance, fantasy, ...)")
    ap.add_argument("--topic", default=None, help="premise / topic / elements you want")
    ap.add_argument("--tone", default=None, help="tone (dark, light, humorous, epic, ...)")
    ap.add_argument("--length", default=None, choices=["short", "medium", "long"],
                    help="story length")
    ap.add_argument("--title", default=None, help="book title (or let the model invent one)")
    ap.add_argument("--author", default=None, help="author name for the PDF")
    ap.add_argument("--language", default=None, help="story language")
    ap.add_argument("--model", default=None, help="LM Studio model id")
    ap.add_argument("--backend", default=None,
                    help="image backend: auto|sdwebui|comfyui|openai|placeholder")
    ap.add_argument("--no-open", action="store_true", help="do not open the PDF at the end")
    args = ap.parse_args(argv)

    cfg = load_config()

    if args.check:
        return check_environment(cfg, args)

    if args.length:
        cfg["story"]["length"] = args.length
    if args.language:
        cfg["story"]["language"] = args.language
    if args.backend:
        cfg["imagegen"]["backend"] = args.backend

    lm = LMStudio(cfg["lmstudio"]["base_url"])
    if not lm.is_available():
        raise LMStudioError(
            "LM Studio is not running. Start LM Studio, load a model, and start the "
            "local server, then run the batch file again."
        )
    model = pick_model(lm, args.model or cfg["lmstudio"].get("model"))
    print(f"Using LM Studio model: {model}")

    params = collect_story_params(args)
    gen = StoryGenerator(lm, model, cfg)

    # ---------------- 1. outline ----------------
    print("\n[1/4] Planning the book outline ...")
    outline = gen.generate_outline(params)
    title = outline.get("title") or params.get("title") or "Untitled"
    author = params.get("author") or ""
    print(f"      Title: {title}")
    for i, sec in enumerate(outline.get("sections", [])):
        print(f"      Section {i+1}: {sec.get('title')} -> {len(sec.get('chapters', []))} chapters")
    if outline.get("prologue"):
        print("      (includes a prologue)")
    if outline.get("epilogue"):
        print("      (includes an epilogue)")

    # ---------------- 2. content ----------------
    story = {
        "title": title,
        "author": author,
        "prologue": None,
        "sections": [],
        "epilogue": None,
    }
    print("\n[2/4] Writing the story (this can take a while) ...")
    if outline.get("prologue"):
        print("      - Prologue")
        data = gen.generate_chapter(outline, "Prologue", "Prologue", 0, params)
        story["prologue"] = {"title": "The Opening", "paragraphs": data["paragraphs"],
                             "image_prompts": data.get("image_prompts", [])}
    ch = 0
    for si, sec in enumerate(outline.get("sections", [])):
        chapters = []
        for c in sec.get("chapters", []):
            ch += 1
            print(f"      - Chapter {ch}: {c}")
            data = gen.generate_chapter(outline, sec.get("title", ""), c, ch, params)
            chapters.append({"title": c, "paragraphs": data["paragraphs"],
                             "image_prompts": data.get("image_prompts", [])})
        story["sections"].append({"title": sec.get("title", ""), "chapters": chapters})
    if outline.get("epilogue"):
        print("      - Epilogue")
        data = gen.generate_chapter(outline, "Epilogue", "Epilogue", 0, params)
        story["epilogue"] = {"title": "The Closing", "paragraphs": data["paragraphs"],
                             "image_prompts": data.get("image_prompts", [])}

    # ---------------- 3. images (cover only) ----------------
    backend, backend_id = imagegen.create_backend(cfg)
    print(f"\n[3/4] Generating the cover illustration ({backend_id} backend) ...")

    out_dir = os.path.join(cfg["output"]["dir"], f"{slugify(title)}-{datetime.datetime.now():%Y%m%d-%H%M%S}")
    images_dir = os.path.join(out_dir, "images")
    os.makedirs(images_dir, exist_ok=True)

    images = {}
    cover_prompt = gen.generate_cover_prompt_from_title(outline)
    cw, chh = cfg["imagegen"]["cover_size"]
    print("      - Cover image ...")
    images["cover"] = imagegen.generate_and_save(
        backend, cover_prompt, cw, chh, os.path.join(images_dir, "cover.png"),
        caption=title)
    if cfg["imagegen"].get("back_cover") == "reuse":
        images["back"] = images["cover"]
    elif cfg["imagegen"].get("back_cover") == "generate":
        print("      - Back cover image ...")
        images["back"] = imagegen.generate_and_save(
            backend, f"{cover_prompt}, quiet and atmospheric end-of-book mood", cw, chh,
            os.path.join(images_dir, "back.png"), caption=title)

    # ---------------- 4. PDF ----------------
    print("\n[4/4] Building the PDF ...")
    pdf_name = f"{slugify(title)}.pdf"
    pdf_path = os.path.join(out_dir, pdf_name)
    pdfbuilder.build_pdf(story, images, pdf_path, opts={
        "divider": cfg["pdf"].get("divider", True),
    })

    # save the story for reproducibility
    with open(os.path.join(out_dir, "story.json"), "w", encoding="utf-8") as f:
        json.dump(story, f, ensure_ascii=False, indent=2)

    print("\n" + "=" * 60)
    print("Done!")
    print(f"  Story : {title}")
    print(f"  Pages : {pdfbuilder_summary(pdf_path)}")
    print(f"  Cover : {os.path.basename(images.get('cover', ''))}")
    print(f"  PDF   : {os.path.abspath(pdf_path)}")
    print("=" * 60)

    if cfg["output"].get("open_pdf") and not args.no_open:
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
    except (LMStudioError, RuntimeError, ValueError) as e:
        print(f"\nERROR: {e}", file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    entry()
