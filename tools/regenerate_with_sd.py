"""Regenerate the COVER for an existing story.json using the EMBEDDED Stable
Diffusion model (diffusers, in-process - no server needed), then rebuild the PDF
with abstract paragraph dividers. Usage:
    py -3 -m tools.regenerate_with_sd <path-to-story.json>
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import imagegen, pdfbuilder
from src.config import load_config


def main():
    if len(sys.argv) < 2:
        print("Usage: py -3 -m tools.regenerate_with_sd <story.json>")
        return 1
    story_path = os.path.abspath(sys.argv[1])
    with open(story_path, "r", encoding="utf-8") as f:
        story = json.load(f)

    cfg = load_config()
    title = story.get("title", "story")
    slug = re.sub(r"[^A-Za-z0-9]+", "-", title).strip("-").lower()[:60] or "story"
    import datetime
    out_dir = os.path.join(cfg["output"]["dir"],
                           f"{slug}-sd-{datetime.datetime.now():%Y%m%d-%H%M%S}")
    images_dir = os.path.join(out_dir, "images")
    os.makedirs(images_dir, exist_ok=True)

    # prefer the embedded diffusers backend (standalone); fall back to auto
    try:
        backend, backend_id = imagegen.create_backend(cfg, force="diffusers")
    except RuntimeError:
        backend, backend_id = imagegen.create_backend(cfg, force="auto")
    print(f"Image backend: {backend_id}")
    if backend_id not in ("diffusers", "sdwebui", "comfyui", "openai"):
        print("No real image backend available. Install torch + diffusers "
              "(see requirements.txt) and set imagegen.diffusers.model_path in config.json.")
        return 1

    images = {}
    cw, chh = cfg["imagegen"]["cover_size"]
    print(" - cover ...")
    images["cover"] = imagegen.generate_and_save(
        backend, story.get("cover_prompt", f"an atmospheric cover for '{title}'"),
        cw, chh, os.path.join(images_dir, "cover.png"), caption=title)
    images["back"] = images["cover"]

    pdf_path = os.path.join(out_dir, f"{slug}.pdf")
    pdfbuilder.build_pdf(story, images, pdf_path, opts={
        "divider": cfg["pdf"].get("divider", True),
    })
    print(f"\nDone! Cover regenerated with SD.")
    print(f"PDF: {os.path.abspath(pdf_path)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
