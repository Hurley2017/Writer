"""Track 2 — on-device generated books: LLM story + SD cover + TTS audio + PDF,
then publish. Wraps the existing src.pipeline (LM Studio / RealVisXL / Orpheus)."""
import argparse
import datetime
import os
import subprocess
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_PROJ = os.path.dirname(_HERE)
if _PROJ not in sys.path:
    sys.path.insert(0, _PROJ)

from bulk.bulk_config import find_ffmpeg
from bulk.publisher import SupabasePublisher, title_published
from bulk.state import BulkState, slugify

THEMES = [
    ("fantasy", "a young mapmaker discovers a hidden realm beneath her city", "epic"),
    ("sci-fi", "the last lighthouse keeper on a dying space station", "melancholic"),
    ("mystery", "a locked-room puzzle at a remote island hotel", "suspenseful"),
    ("romance", "two rival booksellers fall in love across a crowded market", "warm"),
    ("horror", "a village where the fog remembers the dead", "creepy"),
    ("adventure", "a treasure hunt across the lost canals of Venice", "swashbuckling"),
    ("drama", "a retiring theater director stages one final play", "emotional"),
    ("thriller", "a whistleblower trapped in a city that never sleeps", "tense"),
    ("fantasy", "an apprentice alchemist accidentally summons a friendly dragon", "whimsical"),
    ("sci-fi", "archaeologists unearth a machine that replays memories", "wonder-filled"),
]


def _make_args(theme, idx, length, language, author, narrator, model):
    ns = argparse.Namespace()
    ns.genre = theme[0]
    ns.topic = theme[1]
    ns.tone = theme[2]
    ns.length = length
    ns.title = None          # let the model invent titles for variety
    ns.language = language
    ns.author = author or ""
    ns.narrator = narrator
    ns.model = model
    return ns


def _convert_to_mp3(wav, ffmpeg):
    """WAV -> MP3 via ffmpeg (delete the WAV after). Returns mp3 path or wav."""
    if not ffmpeg:
        return wav
    mp3 = os.path.splitext(wav)[0] + ".mp3"
    try:
        subprocess.run([ffmpeg, "-y", "-loglevel", "error", "-i", wav,
                        "-codec:a", "libmp3lame", "-b:a", "128k", mp3],
                       check=True, timeout=1800)
        if os.path.exists(mp3) and os.path.getsize(mp3) > 10000:
            try:
                os.remove(wav)
            except OSError:
                pass
            return mp3
    except Exception as e:
        print(f"        [!] mp3 conversion failed for {wav}: {e}")
    return wav


def run_generated(cfg, count=1, opts=None, stop_event=None):
    """Bulk-produce `count` on-device books (story + cover + audio + pdf).

    stop_event: optional threading.Event — checked between books so a UI can
    stop a batch cleanly.
    """
    opts = opts or {}
    import src.pipeline as pipeline

    # src.pipeline expects the FLAT writer config (cfg["lmstudio"], cfg["imagegen"],
    # cfg["tts"]...) — the bulk config nests config.json under cfg["writer"].
    wcfg = cfg.get("writer") or cfg
    b = cfg["bulk"]
    state = BulkState(b["state_file"])
    out_root = b["output_dir"]
    dry_run = opts.get("dry_run", False)
    no_publish = opts.get("no_publish", False)
    length = opts.get("length", cfg.get("writer", {}).get("story", {}).get("length", "medium"))
    language = opts.get("language", cfg.get("writer", {}).get("story", {}).get("language", "English"))
    author = opts.get("author", cfg.get("writer", {}).get("story", {}).get("author", ""))
    narrator = opts.get("narrator", "auto")
    model = opts.get("model", cfg.get("writer", {}).get("lmstudio", {}).get("model", ""))
    category = opts.get("category", b.get("generated_category", "specials"))
    start_theme = opts.get("start_theme", 0)
    ffmpeg = find_ffmpeg(cfg)

    pub = None
    published_norm = None
    if not no_publish and not dry_run:
        from bulk.bulk_config import resolve_publish
        creds = resolve_publish(cfg)
        if not (creds.get("supabase_url") and creds.get("admin_email")
                and creds.get("admin_password")):
            print("[!] Publish credentials incomplete in bulk/secrets.json "
                  "(need supabase_url + admin_email + admin_password) — "
                  "no-publish mode. Add the admin password to publish.")
            no_publish = True
        else:
            pub = SupabasePublisher(creds["supabase_url"], creds["admin_email"],
                                    creds["admin_password"],
                                    anon_key=creds.get("anon_key", ""))
            published_norm = pub.published_titles_norm()  # dedupe guard
            if published_norm:
                print(f"[i] {len(published_norm)} title(s) already on the "
                      f"website — those will not be re-published")

    if stop_event is None:
        class _Never:
            def is_set(self):
                return False
        stop_event = _Never()

    results = []
    for i in range(count):
        if stop_event.is_set():
            print("\n[stopped] batch aborted by user.")
            break
        theme = THEMES[(start_theme + i) % len(THEMES)]
        print(f"\n=== [{i+1}/{count}] generating: {theme[0]} — {theme[1]} ({theme[2]}) ===")
        try:
            args = _make_args(theme, i, length, language, author, narrator, model)
            story = pipeline.write_story(wcfg, args)
            title = story.get("title") or "Untitled"
            slug = slugify(title)
            out_dir = os.path.join(out_root, f"{slug}-{datetime.datetime.now():%Y%m%d-%H%M%S}")
            os.makedirs(out_dir, exist_ok=True)

            import json
            with open(os.path.join(out_dir, "story.json"), "w", encoding="utf-8") as f:
                json.dump(story, f, ensure_ascii=False, indent=2)

            # cover + illustrations + final PDF
            pdf_path = pipeline.stage_images(wcfg, story, out_dir)
            if not pdf_path or not os.path.exists(pdf_path):
                raise RuntimeError("stage_images produced no PDF")
            pipeline._free_gpu()

            # audiobook (per-chapter wav -> mp3)
            files = pipeline.stage_audio(wcfg, story, out_dir)
            audio_paths = [_convert_to_mp3(f, ffmpeg) for f in (files or [])]

            cover_path = os.path.join(out_dir, "images", "cover.png")
            if not os.path.exists(cover_path):
                cover_path = ""
            desc = (f"An original {theme[0]} story by the Writer's Palette "
                    f"AI studio: {story.get('author') or 'anon'}.")
            entry = state.new("generated", title, story.get("author") or author,
                              output_dir=out_dir, category=category, description=desc,
                              pdf=pdf_path, cover=cover_path, audio=audio_paths,
                              theme=theme[0], topic=theme[1])

            if pub and not no_publish and cover_path:
                if title_published(published_norm or set(), title):
                    state.set_status(slug, "skipped",
                                     error="already published on the website")
                    print("        SKIPPED — already published on the website "
                          "(re-publishing would REPLACE the live book)")
                    results.append({"slug": slug, "title": title, "status": "skipped",
                                    "reason": "already on website"})
                    continue
                res = pub.publish(title, cover_path, pdf_path, subtitle=story.get("author") or author,
                                  description=desc, category=category,
                                  audio_paths=audio_paths, dry_run=dry_run)
                state.set_status(slug, "published", published_at=datetime.datetime.now().isoformat(timespec="seconds"),
                                 publish_result=res)
                print(f"        PUBLISHED (id={res.get('id')})")
            else:
                state.set_status(slug, "ready")
                print("        ready (not published)")

            results.append({"slug": slug, "title": title, "status": "published" if pub else "ready",
                            "pdf": pdf_path, "audio": len(audio_paths)})
        except Exception as e:
            import traceback
            traceback.print_exc()
            slug = slugify(story.get("title") if 'story' in dir() else f"gen-{i}")
            state.set_status(slug, "failed", error=str(e))
            results.append({"slug": slug, "title": "?", "status": "failed", "error": str(e)})

    return results
