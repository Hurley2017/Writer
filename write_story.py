"""AI Story Writer - ONE script to create a complete illustrated audiobook.

Run it by double-clicking story_writer.bat (recommended), or directly with the
venv Python:
    D:\\stable-diffusion-webui\\venv\\Scripts\\python.exe write_story.py

It asks what kind of story you want, then runs the whole local pipeline:
  1. Story   - LM Studio (Gemma 31B) writes the story from your answers
  2. Images  - RealVisXL (SDXL) illustrates the cover + every paragraph
  3. Audio   - Orpheus 3B narrates the audiobook with emotion cues
Everything lands in  output/<book title>/  (story.json, images, PDF, audiobook)
"""
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

# ---- Environment: keep every cache on D: so the tiny C: drive never fills ----
os.environ.setdefault("PIP_CACHE_DIR", r"D:\pipcache")
os.environ.setdefault("TEMP", r"D:\piptemp")
os.environ.setdefault("TMP", r"D:\piptemp")
os.environ.setdefault("HF_HOME", r"D:\hf_cache")
os.environ.setdefault("HF_HUB_CACHE", r"D:\hf_cache\hub")
os.environ["HF_HUB_DISABLE_SYMLINKS"] = "1"
for _d in (r"D:\pipcache", r"D:\piptemp", r"D:\hf_cache"):
    os.makedirs(_d, exist_ok=True)

from src.config import load_config
from src import pipeline


def ask(prompt, default=""):
    v = input(prompt).strip()
    return v or default


def main():
    print("=" * 60)
    print("          AI STORY WRITER - local illustrated audiobooks")
    print("   story: Gemma 31B (LM Studio)   art: RealVisXL   voice: Orpheus (jess + zac)")
    print("=" * 60)

    cfg = load_config()

    print("\nMake sure LM Studio is running with a model loaded")
    print("(and the local server started) before continuing.\n")

    print("--- TELL ME WHAT KIND OF STORY YOU WANT ---\n")
    genre = ask("Genre (sci-fi, romance, fantasy, thriller, mystery, horror, drama...): ",
                "general fiction")
    topic = ask("Premise / elements you want (empty = I invent it): ")
    tone = ask("Tone (dark, light, humorous, epic, emotional...): ")
    print("\nLength:  [1] Short   [2] Medium   [3] Long")
    lc = ask("Choose (1-3, default 2): ", "2")
    length = {"1": "short", "3": "long"}.get(lc, "medium")
    title = ask("Book title (empty = I invent one): ")
    author = ask("Author name for the PDF (optional): ")
    language = ask("Language (English, Hindi, Spanish... empty = English): ", "English")

    print("\nNarrator (reads the story body) - chosen by the protagonist's gender:")
    print("   [1] Auto (decide from the story)   [2] Female (jess)   [3] Male (zac)")
    nc = ask("Choose (1-3, default 1): ", "1")
    narrator = {"2": "female", "3": "male"}.get(nc, "auto")

    print("\n[1] Defaults (auto-pick LM model + image backend)")
    print("[2] Advanced (choose LM model + image backend)")
    adv = ask("Choose (1-2, default 1): ", "1")

    args = ["--stage", "all", "--genre", genre, "--topic", topic, "--tone", tone,
            "--length", length, "--title", title, "--author", author,
            "--language", language]
    if narrator != "auto":
        cfg["tts"]["narrator"] = narrator
        with open(os.path.join(_HERE, "config.json"), "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
        args += ["--narrator", narrator]

    if adv == "2":
        # ---- choose LM model ----
        try:
            import requests
            models = requests.get(
                cfg["lmstudio"]["base_url"] + "/models", timeout=5).json().get("data", [])
            print("\nLM models currently loaded in LM Studio:")
            for i, m in enumerate(models, 1):
                print(f"   [{i}] {m['id']}")
            print("   [0] Auto (pick the largest that loads)")
            mc = ask("Choose LM model (0-Auto, or type an id): ", "0")
            if mc and mc != "0":
                try:
                    args += ["--model", models[int(mc) - 1]["id"]]
                except (ValueError, IndexError):
                    args += ["--model", mc]
        except Exception:
            print("   (could not reach LM Studio to list models - using Auto)")

        # ---- choose image backend ----
        print("\nImage backend:")
        print("   [1] Auto    [2] Embedded SDXL (recommended)   [3] SD WebUI")
        print("   [4] ComfyUI  [5] OpenAI    [6] Placeholder images")
        bc = ask("Choose (1-6, default 1): ", "1")
        backend = {"2": "diffusers", "3": "sdwebui", "4": "comfyui",
                   "5": "openai", "6": "placeholder"}.get(bc)
        if backend:
            args += ["--backend", backend]

    print("\n" + "=" * 60)
    print("   Writing, illustrating and narrating your story...")
    print("   (this can take several minutes)")
    print("=" * 60 + "\n")
    return pipeline.main(args)


if __name__ == "__main__":
    try:
        rc = main()
    except Exception as e:  # friendly error instead of a raw traceback
        print(f"\n[ERROR] {e}")
        rc = 1
    input("\nPress Enter to close this window...")
    sys.exit(rc or 0)
