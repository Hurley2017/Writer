"""Track 1 — public-domain classics: Gutendex text -> A5 PDF + cover ->
LibriVox audiobook match -> publish to writers-palette.com."""
import datetime
import json
import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_PROJ = os.path.dirname(_HERE)
if _PROJ not in sys.path:
    sys.path.insert(0, _PROJ)

from bulk import gutendex, gutenberg_text, librivox, cover as covergen
from bulk.classics_pdf import build_classic_pdf
from bulk.publisher import (SupabasePublisher, PublishError,
                            title_published, normalize_title)
from bulk.state import BulkState, slugify


def _stamp():
    return datetime.datetime.now().strftime("%Y%m%d-%H%M%S")


def _title_clean(meta_title):
    return gutendex.clean_title(meta_title)


def _description(meta, lv_url=""):
    lines = []
    subs = [s for s in (meta.get("subjects") or []) if s][:4]
    if subs:
        lines.append(" · ".join(subs) + ".")
    if meta.get("download_count"):
        lines.append(f"Public-domain text from Project Gutenberg (ebook {meta['gutenberg_id']}).")
    if lv_url:
        lines.append(f"Free audiobook recording by LibriVox volunteers: {lv_url}")
    return " ".join(lines)


def list_candidates(cfg, n=25):
    """Print the top-n Gutendex candidates so the user can pick curated ids."""
    b = cfg["bulk"]
    books = gutendex.top_books(n, lang=b.get("language", "en"),
                               min_downloads=b.get("min_downloads", 0))
    print(f"{'id':>6}  {'downloads':>9}  {'title':<52} author")
    print("-" * 90)
    for bk in books:
        print(f"{bk['id']:>6}  {bk.get('download_count', 0):>9}  "
              f"{_title_clean(bk.get('title',''))[:52]:<52} {gutendex.author_name(bk)}")
    return books


def _candidate_books(cfg, count, curated, state, published_norm=None):
    """Pick the next `count` books not already produced OR already live on the
    website (published_norm = normalized set of published_books titles)."""
    b = cfg["bulk"]
    books = []
    if curated:
        for gid in curated:
            bk = gutendex.get_book(gid, cache_dir=b.get("cache_dir", ""))
            if bk and bk.get("id"):
                books.append(bk)
            else:
                print(f"[!] Could not fetch Gutenberg #{gid} (network or cache).")
    if len(books) < count:
        tops = gutendex.top_books(200, lang=b.get("language", "en"),
                                  min_downloads=b.get("min_downloads", 0))
        for bk in tops:
            if len(books) >= count:
                break
            gid = bk["id"]
            if any(x.get("gutenberg_id") == gid for x in books):
                continue
            if state.is_known(gutenberg_id=gid):
                continue
            books.append(bk)
    # never produce a book whose title is already live on the website
    if published_norm:
        kept = []
        for bk in books:
            if title_published(published_norm, _title_clean(bk.get("title", ""))):
                print(f"[i] skipping {_title_clean(bk.get('title',''))[:50]} — already on the website")
            else:
                kept.append(bk)
        books = kept
    return books[:count]


def run_classics(cfg, count=3, curated=None, opts=None, stop_event=None):
    """Bulk-produce `count` classic books. Returns list of result dicts.

    stop_event: optional threading.Event — checked between books so a UI can
    stop a batch cleanly (current book finishes, then it aborts).
    """
    opts = opts or {}
    b = cfg["bulk"]
    state = BulkState(b["state_file"])
    out_root = b["output_dir"]
    dry_run = opts.get("dry_run", False)
    no_publish = opts.get("no_publish", False)
    lv_mode = opts.get("librivox", b.get("librivox", "link"))
    max_pdf_chapters = opts.get("max_pdf_chapters", b.get("max_chapters_pdf", 200))
    sd_covers = opts.get("sd_covers", False)
    category = opts.get("category", b.get("category", "classics"))
    if stop_event is None:
        class _Never:
            def is_set(self):
                return False
        stop_event = _Never()

    pub = None
    published_norm = None
    if not no_publish and not dry_run:
        from bulk.bulk_config import resolve_publish
        creds = resolve_publish(cfg)
        if not (creds.get("supabase_url") and creds.get("admin_email")
                and creds.get("admin_password")):
            print("[!] Publish credentials incomplete in bulk/secrets.json "
                  "(need supabase_url + admin_email + admin_password) — running "
                  "in no-publish mode. Add the admin password to publish.")
            no_publish = True
        else:
            pub = SupabasePublisher(creds["supabase_url"], creds["admin_email"],
                                    creds["admin_password"],
                                    anon_key=creds.get("anon_key", ""))
            # dedupe guard: don't re-publish titles already live on the website
            published_norm = pub.published_titles_norm()
            if published_norm:
                print(f"[i] {len(published_norm)} title(s) already on the "
                      f"website — those will not be re-published")

    books = _candidate_books(cfg, count, curated, state, published_norm)
    if not books:
        print("No new candidate books left to produce.")
        return []

    results = []
    for idx, bk in enumerate(books, 1):
        if stop_event.is_set():
            print("\n[stopped] batch aborted by user.")
            break
        meta = gutendex.book_to_meta(bk)
        title = _title_clean(meta["title"])
        author = meta["author"]
        slug = slugify(title)
        stamp = _stamp()
        out_dir = os.path.join(out_root, f"{slug}-{stamp}")
        print(f"\n=== [{idx}/{len(books)}] {title} — by {author} "
              f"(Gutenberg #{meta['gutenberg_id']}) ===")

        entry = state.new("classics", title, author, gutenberg_id=meta["gutenberg_id"],
                          category=category, output_dir=out_dir,
                          description="", meta=meta)
        try:
            os.makedirs(out_dir, exist_ok=True)

            # ---- text + parse ----
            print("  [1/6] Downloading text ...")
            txt = gutendex.download_text(bk, b["cache_dir"])
            book = gutenberg_text.parse_book(txt, title, author)
            wc = book["word_count"]
            if wc < b.get("min_words", 1200):
                raise RuntimeError(f"Book too short ({wc} words) — skipped")
            print(f"        {wc} words, {len(book['chapters'])} chapters")
            with open(os.path.join(out_dir, "book.json"), "w", encoding="utf-8") as f:
                json.dump(book, f, ensure_ascii=False, indent=2)

            # ---- cover ----
            print("  [2/6] Cover ...")
            cover_path = os.path.join(out_dir, "cover.png")
            if sd_covers:
                covergen.sd_cover({"title": title, "author": author}, cfg, cover_path)
            else:
                covergen.classic_cover(title, author, cover_path,
                                       size=tuple(b.get("cover_size", [896, 1152])))
            entry["cover"] = cover_path

            # ---- PDF ----
            print("  [3/6] Typesetting A5 PDF ...")
            pdf_path = os.path.join(out_dir, f"{slug}.pdf")
            build_classic_pdf(book, cover_path, pdf_path,
                              max_chapters=max_pdf_chapters)
            entry["pdf"] = pdf_path
            print(f"        {os.path.getsize(pdf_path)//1024} KB -> {pdf_path}")

            # ---- LibriVox audiobook ----
            print("  [4/6] LibriVox lookup ...")
            lv = None
            if not librivox.api_reachable(timeout=6):
                print("        LibriVox API unreachable — skipping lookup.")
            else:
                lv = librivox.match_book(meta["gutenberg_id"], title, author)
            lv_info = None
            if lv:
                lv_info = {"url": lv.get("url_librivox", ""), "title": lv.get("title", ""),
                           "total": librivox.human_time(lv.get("totaltimesecs")),
                           "num_sections": lv.get("num_sections")}
                print(f"        MATCH: {lv_info['title']} ({lv_info['total']}) "
                      f"-> {lv_info['url']}")
            else:
                print("        no LibriVox match (or not in English)")
            entry["librivox"] = lv_info

            # ---- audio download (optional) ----
            audio_paths = []
            if lv_info and lv_mode == "upload":
                print("  [5/6] Downloading LibriVox chapters ...")
                audio_dir = os.path.join(out_dir, "audio")
                max_ch = b.get("librivox_max_chapters", 80)
                try:
                    audio_paths = librivox.download_all_chapters(
                        lv["id"], audio_dir, max_chapters=max_ch)
                    print(f"        {len(audio_paths)} mp3 files -> {audio_dir}")
                except librivox.LibriVoxError as e:
                    print(f"        [!] chapter download failed: {e}")
                    audio_paths = []
                entry["audio"] = audio_paths

            # ---- description + publish ----
            desc = _description(meta, lv_info["url"] if lv_info else "")
            entry["description"] = desc
            print("  [6/6] Publishing ...")
            if pub and not no_publish:
                if title_published(published_norm or set(), title):
                    # already live on the website — never replace it
                    state.set_status(slug, "skipped",
                                     error="already published on the website")
                    print("        SKIPPED — already published on the website "
                          "(re-publishing would REPLACE the live book)")
                    results.append({"slug": slug, "title": title, "status": "skipped",
                                    "reason": "already on website"})
                    continue
                res = pub.publish(title, cover_path, pdf_path,
                                  subtitle=author, description=desc,
                                  category=category, audio_paths=audio_paths,
                                  dry_run=dry_run)
                state.set_status(slug, "published", published_at=_stamp(),
                                 publish_result=res)
                print(f"        PUBLISHED (id={res.get('id')})")
            else:
                state.set_status(slug, "ready", published_at=None)
                print("        ready (not published: no-publish/dry-run)")

            results.append({"slug": slug, "title": title, "status": "published" if pub else "ready",
                            "pdf": pdf_path, "audio": len(audio_paths),
                            "librivox": bool(lv_info)})
        except Exception as e:
            import traceback
            traceback.print_exc()
            state.set_status(slug, "failed", error=str(e))
            results.append({"slug": slug, "title": title, "status": "failed", "error": str(e)})

    return results


def publish_ready(cfg, opts=None, stop_event=None, limit=0):
    """Publish books that are produced locally (state status 'ready') but not
    yet on the website — lets you produce a batch, review it, then publish.

    Respects the no-duplicate guard: titles already live are marked 'skipped'
    and never re-published. Works for both the classics and generated tracks.
    """
    opts = opts or {}
    b = cfg["bulk"]
    state = BulkState(b["state_file"])
    dry_run = opts.get("dry_run", False)
    no_publish = opts.get("no_publish", False)
    if stop_event is None:
        class _Never:
            def is_set(self):
                return False
        stop_event = _Never()

    from bulk.bulk_config import resolve_publish
    creds = resolve_publish(cfg)
    if no_publish or not (creds.get("supabase_url") and creds.get("admin_email")
                          and creds.get("admin_password")):
        print("[!] Publish credentials incomplete in bulk/secrets.json (need "
              "supabase_url + admin_email + admin_password) — nothing published.")
        return []
    pub = SupabasePublisher(creds["supabase_url"], creds["admin_email"],
                            creds["admin_password"],
                            anon_key=creds.get("anon_key", ""))
    published_norm = pub.published_titles_norm()

    candidates = [bk for bk in state.all()
                  if bk.get("status") == "ready"
                  and bk.get("cover") and os.path.exists(bk["cover"])
                  and bk.get("pdf") and os.path.exists(bk["pdf"])]
    if limit and len(candidates) > limit:
        candidates = candidates[:limit]
    if not candidates:
        print("No 'ready' books to publish (produce some first).")
        return []

    print(f"Publishing {len(candidates)} ready book(s) ...")
    results = []
    for idx, entry in enumerate(candidates, 1):
        if stop_event.is_set():
            print("\n[stopped] publish aborted by user.")
            break
        slug = entry["slug"]
        title = entry.get("title") or slug
        author = entry.get("author") or ""
        print(f"\n=== [{idx}/{len(candidates)}] {title} — {author} ===")
        try:
            if title_published(published_norm, title):
                state.set_status(slug, "skipped",
                                 error="already published on the website")
                print("        SKIPPED — already published on the website "
                      "(re-publishing would REPLACE the live book)")
                results.append({"slug": slug, "title": title, "status": "skipped"})
                continue
            res = pub.publish(title, entry["cover"], entry["pdf"],
                              subtitle=author,
                              description=entry.get("description", ""),
                              category=entry.get("category", b.get("category", "classics")),
                              audio_paths=entry.get("audio") or [],
                              dry_run=dry_run)
            state.set_status(slug, "published", published_at=_stamp(),
                             publish_result=res)
            print(f"        PUBLISHED (id={res.get('id')})")
            results.append({"slug": slug, "title": title, "status": "published",
                            "id": res.get("id")})
        except Exception as e:
            import traceback
            traceback.print_exc()
            entry["error"] = str(e)
            state.save()
            results.append({"slug": slug, "title": title, "status": "failed", "error": str(e)})
    return results


def backfill_covers(cfg, opts=None, stop_event=None, limit=0):
    """Regenerate covers of already-produced classics with AI (Stable Diffusion).

    Scans bulk/state.json for classic books that have a cover + pdf (status
    ready or published), regenerates each cover as painterly AI art (replacing
    the typographic one on disk), and — when publishing is enabled — re-publishes
    the book so the new cover goes live on writers-palette.com (re-publishing a
    title REPLACES the old book there, so the PDF/audiobook stay the same).

    Returns a list of result dicts.
    """
    opts = opts or {}
    b = cfg["bulk"]
    state = BulkState(b["state_file"])
    dry_run = opts.get("dry_run", False)
    no_publish = opts.get("no_publish", False)
    if stop_event is None:
        class _Never:
            def is_set(self):
                return False
        stop_event = _Never()

    # is a real SD backend available? (placeholder = no diffusers/model)
    from src import imagegen
    wcfg = cfg.get("writer") or cfg
    try:
        backend_id = imagegen.detect_backend(wcfg)
    except Exception:
        backend_id = "?"
    if backend_id in ("placeholder", "?", ""):
        print("[!] No Stable Diffusion backend available (install torch+diffusers "
              "and set imagegen.diffusers.model_path) — cannot backfill covers.")
        return []

    candidates = [bk for bk in state.all()
                  if bk.get("source") == "classics"
                  and bk.get("status") in ("ready", "published")
                  and bk.get("cover") and os.path.exists(bk["cover"])
                  and bk.get("pdf") and os.path.exists(bk["pdf"])]
    if limit and len(candidates) > limit:
        candidates = candidates[:limit]
    if not candidates:
        print("No produced classics with existing covers to backfill (check bulk/state.json).")
        return []

    pub = None
    published_norm = None
    if not no_publish and not dry_run:
        from bulk.bulk_config import resolve_publish
        creds = resolve_publish(cfg)
        if not (creds.get("supabase_url") and creds.get("admin_email")
                and creds.get("admin_password")):
            print("[!] Publish credentials incomplete in bulk/secrets.json "
                  "(need supabase_url + admin_email + admin_password) — covers "
                  "updated locally only (no re-publish).")
            no_publish = True
        else:
            pub = SupabasePublisher(creds["supabase_url"], creds["admin_email"],
                                    creds["admin_password"],
                                    anon_key=creds.get("anon_key", ""))
            # only re-publish books that are ALREADY live (never publish new
            # ones during a backfill)
            published_norm = pub.published_titles_norm()

    print(f"Backfilling AI covers for {len(candidates)} classic book(s) "
          f"({'+ re-publish' if pub else 'local only'}) ...")
    results = []
    for idx, entry in enumerate(candidates, 1):
        if stop_event.is_set():
            print("\n[stopped] backfill aborted by user.")
            break
        slug = entry["slug"]
        title = entry.get("title") or slug
        author = entry.get("author") or ""
        cover_path = entry["cover"]
        print(f"\n=== [{idx}/{len(candidates)}] {title} — {author} ===")
        try:
            print("  Generating AI cover (Stable Diffusion) ...")
            covergen.sd_cover({"title": title, "author": author}, cfg, cover_path)
            print(f"        -> {cover_path} ({os.path.getsize(cover_path)//1024} KB)")
            entry["cover_kind"] = "sd"
            entry["cover_backfilled_at"] = _stamp()
            if entry.get("error"):
                entry.pop("error", None)
            state.save()

            was_live = (entry.get("status") == "published"
                        or title_published(published_norm or set(), title))
            if pub and not no_publish and was_live:
                print("  Re-publishing (replaces the old book, new cover goes live) ...")
                res = pub.publish(title, cover_path, entry["pdf"],
                                  subtitle=author,
                                  description=entry.get("description", ""),
                                  category=entry.get("category", b.get("category", "classics")),
                                  audio_paths=entry.get("audio") or [],
                                  dry_run=dry_run)
                state.set_status(slug, "published", published_at=_stamp(),
                                 publish_result=res)
                print(f"        PUBLISHED (id={res.get('id')})")
            elif pub and not no_publish:
                print("        cover saved locally — book was NOT previously "
                      "published (backfill never publishes new books)")
                state.set_status(slug, "ready")
            else:
                print("        cover saved locally (no re-publish)")

            results.append({"slug": slug, "title": title, "status": "published" if pub else "ready",
                            "cover_kind": "sd"})
        except Exception as e:
            import traceback
            traceback.print_exc()
            entry["error"] = str(e)
            state.save()
            results.append({"slug": slug, "title": title, "status": "failed", "error": str(e)})
    return results
