# Bulk Publisher — writers-palette.com

A standalone bulk book factory for [writers-palette.com](https://writers-palette.com).
It produces finished books **locally** (PDF + cover + audiobook) and publishes them
to the site through the existing `publish-book` edge function (Google Drive + DB).

Two production tracks:

| Track | Pipeline |
|---|---|
| **1 · Classics** | Gutendex public-domain text → A5 Palatino PDF (Second Light of March layout) → typographic cover → LibriVox audiobook match → publish |
| **2 · Generated** | on-device: LM Studio story → RealVisXL/SD cover → Orpheus TTS audiobook → PDF → publish |

---

## Quick start

```bat
:: one-click launcher (asks questions, defaults to safe mode)
bulk_publisher.bat

:: CLI
py -3 -m bulk.run_bulk --help
py -3 -m bulk.run_bulk --classics 5                :: 5 public-domain classics
py -3 -m bulk.run_bulk --classics 3 --curated 1342,84,11
py -3 -m bulk.run_bulk --generated 2               :: 2 on-device AI books
py -3 -m bulk.run_bulk --classics 2 --generated 1  :: mixed run
py -3 -m bulk.run_bulk --list-top 25               :: preview Gutendex candidates
```

### First-time setup

1. **Publish credentials** — copy `bulk/secrets.json.example` to `bulk/secrets.json`
   and fill in your Supabase URL + an admin account (email must end with an allowed
   admin domain, e.g. `@writers-palette.com`):
   ```json
   {
     "supabase_url": "https://YOURPROJECT.supabase.co",
     "admin_email": "you@writers-palette.com",
     "admin_password": "your-admin-password"
   }
   ```
   Without this file the runs default to `--no-publish` (books are still produced).
2. **Python deps** — the existing `requirements.txt` covers everything (requests,
   Pillow, reportlab). The generated track additionally needs LM Studio / SD / TTS
   configured exactly as the existing writer pipeline (`config.json`).
3. **ffmpeg** (optional) — used to convert TTS WAVs to MP3 before publishing.
   `winget install Gyan.FFmpeg`, or set `bulk.ffmpeg_path`.

---

## Track 1 — Classics (Gutendex → PDF → LibriVox)

```
Gutendex (public-domain English books, most-downloaded first)
  → download plain text (utf-8)            bulk/gutendex.py
  → parse into chapters (robust TOC/header/footer stripping)
                                           bulk/gutenberg_text.py
  → typeset A5 PDF (Palatino 9.5/15, contents, running headers, footers)
                                           bulk/classics_pdf.py
  → cover (elegant typographic; --sd-covers for painterly SD art)
                                           bulk/cover.py
  → LibriVox audiobook lookup              bulk/librivox.py
  → publish (cover + pdf [+ audiobook])    bulk/publisher.py
```

**LibriVox handling** (`--librivox`, default `link`):

* `link` — record the LibriVox page URL in `state.json` and in the book
  description (visible on the site). Safe default, no huge uploads.
* `upload` — download the LibriVox chapter MP3s and publish them as the book's
  audiobook (the site player shows the chapter list). Downloading is sequential
  (archive.org throttles parallel) and resumable (skips existing files). Very long
  books may exceed edge-function request limits — use for short/mid-length books.
* `skip` — don't touch LibriVox at all.

**Curating which classics**: `--list-top 50` shows the most-downloaded candidates
with their Gutenberg ids, then `--curated 1342,84,11` pins exact titles (in order).

---

## Track 2 — Generated (on-device AI books)

Reuses the existing writer pipeline (`src/pipeline.py`): LM Studio writes the
story, RealVisXL (or your configured image backend) makes the cover + art,
Orpheus TTS narrates the audiobook, and the A5 PDF is built — then everything is
published in one shot. Themes rotate through a built-in list for variety.

```bat
py -3 -m bulk.run_bulk --generated 3 --author "Your Pen Name" --length medium
```

---

## State, dedupe, resume

* `bulk/state.json` is the ledger. Every produced book gets an entry
  (`planned → ready/published/failed`). A book is never produced twice
  (dedupe by title and Gutenberg id). If the file is corrupted it is rebuilt empty
  and each `output/<slug>-<ts>/` folder remains the source of truth.
* Runs are resumable: interrupted audio downloads continue where they stopped;
  already-done books are skipped.
* Raw downloaded texts/covers are cached in `bulk/cache/` (keyed by Gutenberg id),
  so re-runs are fast.

## Layout of a produced book (`output/<slug>-<ts>/`)

```
book.json        parsed chapters (struct)
cover.png        cover art
<slug>.pdf       the A5 typeset book
audio/           chapter MP3s (classics: LibriVox; generated: TTS)
story.json       (generated track) the LLM's story
```

## Publish contract

`bulk/publisher.py` mirrors the website's own `publishBook`:

```
POST {supabase}/functions/v1/publish-book
  Authorization: Bearer <admin JWT>
  multipart: title, subtitle, description, category, cover, pdf, audio[]…
```

Re-publishing the same title replaces the old book (no duplicates). Files go to
`Writer's Palette/Books/<Title>/` on Google Drive; the DB row + `book_audio` row
are written by the edge function.

## Notes / gotchas baked in

* Public-domain only: Gutendex already filters `copyright=false`; LibriVox audio is
  CC0 — no licensing issues. Do NOT republish modern copyrighted works.
* The classics parser is conservative — it never deletes text, it only fails to
  *split* chapters (fallback: whole book as one chapter). Spot-check the PDF
  before publishing (the pipeline prints word/chapter counts).
* `--dry-run` shows the plan without downloads/publish; `--no-publish` does the
  full production but skips the upload step (great for reviewing a batch).
* Set `PYTHONIOENCODING=utf-8` if titles contain non-ASCII (the .bat does this).
