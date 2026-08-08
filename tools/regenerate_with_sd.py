"""Regenerate all images for an existing story.json using the EMBEDDED Stable
Diffusion model (diffusers, in-process - no server needed), then rebuild the PDF.
Usage:
    py -3 -m tools.regenerate_with_sd <path-to-story.json>
"""
import json
import os
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
    out_dir = os.path.join(cfg["output"]["dir"], f"{os.path.basename(story_path)}-sd-images")
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
    title = story.get("title", "Story")
    cw, chh = cfg["imagegen"]["cover_size"]
    print(f" - cover ...")
    images["cover"] = imagegen.generate_and_save(
        backend, story.get("cover_prompt", f"an atmospheric cover for '{title}'"),
        cw, chh, os.path.join(images_dir, "cover.png"), caption=title)
    images["back"] = images["cover"]

    total = 0
    def paras(prefix, chapter):
        nonlocal total
        prompts = chapter.get("image_prompts", []) or []
        for i, p in enumerate(chapter.get("paragraphs", [])):
            prompt = prompts[i] if i < len(prompts) and prompts[i] else p
            total += 1
            w, h = cfg["imagegen"]["width"], cfg["imagegen"]["height"]
            print(f" - {prefix} p{i}: {prompt[:60]}...")
            images[f"{prefix}_p{i}"] = imagegen.generate_and_save(
                backend, prompt, w, h, os.path.join(images_dir, f"{prefix}_p{i}.png"),
                caption=prompt)

    if story.get("prologue"):
        paras("prologue", story["prologue"])
    for si, sec in enumerate(story.get("sections", [])):
        for ci, ch in enumerate(sec.get("chapters", []), start=1):
            paras(f"s{si}_c{ci}", ch)
    if story.get("epilogue"):
        paras("epilogue", story["epilogue"])

    pdf_path = os.path.join(out_dir, f"{os.path.splitext(os.path.basename(story_path))[0]}.pdf")
    pdfbuilder.build_pdf(story, images, pdf_path, opts={
        "image_interval": 1,
        "images_after_last": False,
        "image_max_width": cfg["pdf"].get("image_max_width", 300),
        "image_max_height": cfg["pdf"].get("image_max_height", 340),
    })
    print(f"\nDone! {total} images regenerated with SD.")
    print(f"PDF: {os.path.abspath(pdf_path)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
