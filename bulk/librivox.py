"""LibriVox API client — find the audiobook for a Gutendex book, list its
chapter MP3s (via the RSS feed), and download them.

Verified API contracts (2026-08):
  * search  : https://librivox.org/api/feed/audiobooks?title=<q>&format=json
              returns {"books":[{id, title, url_librivox, url_zip_file,
              url_rss, url_text_source (Gutenberg link), language, num_sections,
              totaltime, totaltimesecs, authors:[{first_name,last_name}], ...}]}
              (the `q=` parameter is ignored by the API — use `title=`.)
  * chapters: https://librivox.org/rss/<id>  -> RSS with one <item> per chapter,
              each with <title> and <enclosure url=...> (mp3).
  * audio   : zip via url_zip_file (archive.org); individual mp3s via the RSS
              enclosure URLs (preferred — no giant zip).
"""
import os
import re
import time
import urllib.parse
import xml.etree.ElementTree as ET

import requests

API = "https://librivox.org/api/feed/audiobooks"
RSS = "https://librivox.org/rss"
UA = {"User-Agent": "writers-palette-bulk-publisher/1.0 (+local script)"}


class LibriVoxError(RuntimeError):
    pass


def api_reachable(timeout=6):
    """Fast preflight: is librivox.org responding at all? (The API is flaky;
    when it is down we should skip the whole lookup instead of blocking a
    batch for minutes on retries.)"""
    try:
        r = requests.get(API, params={"title": "test", "format": "json"},
                         headers=UA, timeout=timeout)
        return r.status_code < 500
    except requests.RequestException:
        return False


def _get(url, params=None, timeout=15, retries=2):
    last = None
    for i in range(retries):
        try:
            r = requests.get(url, params=params, headers=UA, timeout=timeout)
            if r.status_code == 429:
                time.sleep(2 * (i + 1))
                continue
            r.raise_for_status()
            return r
        except requests.RequestException as e:
            last = e
            time.sleep(1.5 * (i + 1))
    raise LibriVoxError(f"LibriVox request failed: {last}")


def _norm(s):
    return re.sub(r"[^a-z0-9]+", "", (s or "").lower())


def search_by_title(title):
    """Title search; returns a list of book dicts (English filter applied).
    The LibriVox API 404s on some titles (commas, edition suffixes) — retry
    with a simplified title when that happens."""
    variants = _title_variants(title)
    seen = set()
    for v in variants:
        try:
            r = _get(API, params={"title": v, "format": "json"})
        except LibriVoxError:
            continue
        data = r.json()
        for b in data.get("books") or []:
            if (b.get("language") or "").lower() == "english" and b.get("id") not in seen:
                seen.add(b.get("id"))
                yield b
    return


def _title_variants(title):
    """Progressively simpler versions of a title to try against the API."""
    t = (title or "").strip()
    out = [t]
    # strip edition suffixes: ", Complete", "Vol. 1", ", v. 2", etc.
    t2 = re.sub(r"\s*[,;:]?\s*(Complete|Unabridged|Vol\.?\s*[IVXLC0-9]+|Volume\s*[IVXLC0-9]+|\(.*?\)|\[.*?\])\s*$", "", t, flags=re.I).strip()
    if t2 and t2 != t:
        out.append(t2)
    # drop a leading "The " (LibriVox often omits it)
    t3 = re.sub(r"^The\s+", "", t2 or t, flags=re.I).strip()
    if t3 and t3 not in out:
        out.append(t3)
    return out


def _gutenberg_id(book):
    """Pull the Gutenberg ebook id out of url_text_source, or None."""
    src = book.get("url_text_source") or ""
    m = re.search(r"/e(?:text|books)/(\d+)", src)
    return int(m.group(1)) if m else None


def match_book(gutenberg_id, title, author):
    """Best LibriVox match for a Gutendex book.

    Priority:
      1. url_text_source points at the same Gutenberg id (exact match)
      2. normalized title equality (or containment) + author last name match
    Returns a book dict or None.
    """
    author_last = (author or "").strip().split()[-1].lower() if (author or "").strip() else ""
    candidates = list(search_by_title(title))
    if not candidates:
        return None

    # exact by gutenberg id
    for b in candidates:
        if _gutenberg_id(b) == gutenberg_id:
            return b

    t_norm = _norm(title)
    best = None
    for b in candidates:
        b_norm = _norm(b.get("title", ""))
        if b_norm == t_norm or t_norm in b_norm or b_norm in t_norm:
            if author_last:
                names = " ".join(a.get("last_name", "") for a in (b.get("authors") or []))
                if author_last not in _norm(names) and author_last not in _norm(b.get("title", "")):
                    continue
            if best is None or (b.get("totaltimesecs") or 0) > (best.get("totaltimesecs") or 0):
                best = b
    return best


def chapter_meta(book_id):
    """Parse the RSS feed -> list of {title, url, dur_sec} chapter entries."""
    r = _get(f"{RSS}/{book_id}")
    try:
        root = ET.fromstring(r.content)
    except ET.ParseError as e:
        raise LibriVoxError(f"LibriVox RSS parse failed for {book_id}: {e}")
    out = []
    ns = {"itunes": "http://www.itunes.com/dtds/podcast-1.0.dtd"}
    for item in root.iter("item"):
        title = item.findtext("title") or ""
        enc = item.find("enclosure")
        url = enc.get("url") if enc is not None else ""
        if not url:
            continue
        dur_el = item.find("itunes:duration", ns)
        dur_sec = _parse_duration(dur_el.text if dur_el is not None else None)
        out.append({"title": title, "url": url, "dur_sec": dur_sec})
    return out


def _parse_duration(s):
    if not s:
        return 0
    raw = re.sub(r"\s+", "", str(s))  # CDATA may include newlines/whitespace
    parts = [int(p) for p in raw.split(":") if p.isdigit()]
    if not parts:
        return 0
    secs = 0
    for p in parts:
        secs = secs * 60 + p
    return secs


def human_time(secs):
    h, rem = divmod(int(secs or 0), 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}h {m:02d}m"
    return f"{m}m {s:02d}s"


def download_chapter(chapter, dest_dir, prefix="", timeout=120):
    """Download one chapter MP3 (resumable: skips existing files). Returns path."""
    os.makedirs(dest_dir, exist_ok=True)
    url = chapter["url"]
    # name: NN_slug.mp3 (fall back to a hash of the url if title is empty)
    slug = re.sub(r"[^a-z0-9]+", "_", (chapter.get("title") or "").lower()).strip("_")
    if not slug:
        slug = "ch" + re.sub(r"\D", "", url[-12:])
    fname = f"{prefix}{slug}.mp3" if prefix else f"{slug}.mp3"
    path = os.path.join(dest_dir, fname)
    if os.path.exists(path) and os.path.getsize(path) > 10000:
        return path
    r = _get(url, timeout=timeout)
    with open(path, "wb") as f:
        f.write(r.content)
    return path


def download_all_chapters(book_id, dest_dir, max_chapters=0, prefix=""):
    """Download every chapter of a LibriVox book, sequentially (archive.org
    throttles parallel downloads and can hard-crash Python). Returns [paths]."""
    chapters = chapter_meta(book_id)
    if max_chapters and len(chapters) > max_chapters:
        chapters = chapters[:max_chapters]
    paths = []
    for i, ch in enumerate(chapters, 1):
        paths.append(download_chapter(ch, dest_dir, prefix=f"{i:02d}_" if not prefix else prefix))
    return paths


if __name__ == "__main__":
    # self-test: match Pride and Prejudice (Gutenberg #1342) and list chapters
    m = match_book(1342, "Pride and Prejudice", "Jane Austen")
    if m:
        print("match:", m["title"], "|", m["url_librivox"], "|", human_time(m.get("totaltimesecs")))
        chs = chapter_meta(m["id"])
        print(f"chapters: {len(chs)}")
        for c in chs[:5]:
            print("   -", c["title"], "|", c["url"][:80], "|", human_time(c["dur_sec"]))
    else:
        print("NO MATCH")
