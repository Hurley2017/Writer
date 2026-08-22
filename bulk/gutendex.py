"""Gutendex (Project Gutenberg API) client — search, fetch, download, cache.

API: https://gutendex.com/books/
Example record (abridged):
  {id, title, authors:[{name:"Melville, Herman", birth_year, death_year}],
   translators:[...], subjects:[...], bookshelves:[...], languages:["en"],
   copyright:false, media_type:"Text",
   formats:{"text/plain; charset=utf-8": "https://www.gutenberg.org/ebooks/2701.txt.utf-8",
            "image/jpeg": "https://www.gutenberg.org/cache/epub/2701/pg2701.cover.medium.jpg",
            ...},
   download_count: 188210}
"""
import json
import os
import re
import time
import urllib.parse

import requests

BASE = "https://gutendex.com/books"
UA = {"User-Agent": "writers-palette-bulk-publisher/1.0 (+local script)"}
TEXT_KEYS = ("text/plain; charset=utf-8", "text/plain; charset=us-ascii", "text/plain; charset=iso-8859-1")


class GutendexError(RuntimeError):
    pass


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
    raise GutendexError(f"Gutendex request failed: {last}")


def author_name(book):
    """'Melville, Herman' -> 'Herman Melville'."""
    a = (book.get("authors") or [{}])[0]
    name = a.get("name", "")
    parts = [p.strip() for p in name.split(",")]
    if len(parts) >= 2 and parts[0]:
        return (parts[1] + " " + parts[0]).strip()
    return name.strip() or "Unknown"


def clean_title(title):
    """Strip volume/edition suffixes that would create near-duplicate titles."""
    t = re.sub(r"\s*[,;]?\s*(Vol(ume)?\.?|vol\.|V\.?|Volume)\s+[IVXLC0-9]+\s*$", "", title, flags=re.I)
    return t.strip()


def iter_books(params, max_pages=200):
    """Yield Gutendex records across pages for the given query params."""
    url = BASE
    while url and max_pages > 0:
        data = _get(url, params=params).json()
        for b in data.get("results", []):
            yield b
        url = data.get("next")
        params = None
        max_pages -= 1


def top_books(n=50, lang="en", min_downloads=0, max_pages=4):
    """Most-downloaded books in a language among a bounded catalog sample.

    Gutendex does not sort by popularity, so the true top-N needs the whole
    catalog (~2000 pages) — too slow for a CLI preview. max_pages (default 4,
    ~128 books) is plenty to surface the popular public-domain classics.
    """
    books = list(iter_books({"languages": lang, "copyright": "false"},
                            max_pages=max_pages))
    usable = []
    for b in books:
        if b.get("media_type") != "Text":
            continue
        dc = b.get("download_count") or 0
        if dc < min_downloads:
            continue
        if not text_url(b):
            continue
        usable.append(b)
    usable.sort(key=lambda b: -(b.get("download_count") or 0))
    return usable[:n]


def search(query, n=25, lang="en"):
    books = list(iter_books({"search": query, "languages": lang}))
    books.sort(key=lambda b: -(b.get("download_count") or 0))
    return books[:n]


def get_book(gid, cache_dir=None):
    """Fetch a book by id. Cache-first: if a plain-text cache exists for this
    id we use it directly (no network) — this keeps production working when
    Gutendex is slow/down. Otherwise fetch from Gutendex, falling back to the
    cache on failure."""
    if cache_dir:
        cached = _cached_book(gid, cache_dir)
        if cached:
            print(f"[i] using cached text for #{gid} (offline metadata)")
            return cached
    try:
        return _get(f"{BASE}/{gid}").json()
    except GutendexError:
        return _cached_book(gid, cache_dir) or {}


def _cached_book(gid, cache_dir=None):
    """Minimal book dict built from a cached plain-text file (offline fallback)."""
    import glob
    for d in ([cache_dir] if cache_dir else []):
        if not d:
            continue
        matches = glob.glob(os.path.join(d, f"{gid}.txt.txt"))
        if not matches:
            continue
        try:
            with open(matches[0], "r", encoding="utf-8", errors="replace") as f:
                head = f.read(4000)
            title = re.search(r"(?m)^Title:\s*(.+)$", head)
            author = re.search(r"(?m)^Author:\s*(.+)$", head)
            return {
                "id": gid,
                "title": (title.group(1).strip() if title else f"Book {gid}"),
                "authors": [{"name": author.group(1).strip()}] if author else [],
                "formats": {"text/plain; charset=utf-8": f"cache://{gid}"},
            }
        except Exception:
            continue
    return None


def text_url(book):
    for k in TEXT_KEYS:
        u = book.get("formats", {}).get(k)
        if u:
            return u
    return None


def cover_url(book):
    return book.get("formats", {}).get("image/jpeg") or ""


def _cache_path(cache_dir, gid, kind, ext):
    os.makedirs(cache_dir, exist_ok=True)
    return os.path.join(cache_dir, f"{gid}.{kind}.{ext}")


def download_text(book, cache_dir):
    """Download (or load cached) plain text; returns the text."""
    gid = book["id"]
    path = _cache_path(cache_dir, gid, "txt", "txt")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    url = text_url(book)
    if not url:
        raise GutendexError(f"Book {gid} has no plain-text download")
    r = _get(url, timeout=60)
    # utf-8 is preferred; some ascii/iso files are cp1252-ish in practice
    try:
        text = r.content.decode("utf-8")
    except UnicodeDecodeError:
        text = r.content.decode("cp1252", errors="replace")
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return text


def download_cover(book, cache_dir):
    """Download (or load cached) cover image; returns local path or ''."""
    url = cover_url(book)
    if not url:
        return ""
    gid = book["id"]
    ext = url.rsplit(".", 1)[-1].lower() if "." in url else "jpg"
    if ext not in ("jpg", "jpeg", "png", "webp"):
        ext = "jpg"
    path = _cache_path(cache_dir, gid, "cover", ext)
    if os.path.exists(path) and os.path.getsize(path) > 500:
        return path
    try:
        r = _get(url, timeout=60)
        with open(path, "wb") as f:
            f.write(r.content)
        return path
    except GutendexError:
        return ""


def book_to_meta(book):
    """Small serializable summary used for state/metadata."""
    return {
        "gutenberg_id": book["id"],
        "title": book.get("title", ""),
        "author": author_name(book),
        "download_count": book.get("download_count"),
        "subjects": book.get("subjects", [])[:6],
        "bookshelves": book.get("bookshelves", [])[:6],
        "language": (book.get("languages") or ["en"])[0],
    }


def _fmt(text):
    return json.dumps(text, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    # quick self-test: print the top 10 candidates
    import sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    tops = top_books(10)
    for b in tops:
        print(f"{b['id']:>6}  {b.get('download_count'):>8}  {b['title'][:60]:60}  {author_name(b)}")
