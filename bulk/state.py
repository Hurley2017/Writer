"""Bulk-state ledger — prevents duplicate publishing and makes runs resumable.

state.json shape:
{
  "books": [
    {
      "slug": "pride-and-prejudice",
      "title": "Pride and Prejudice",
      "author": "Jane Austen",
      "source": "classics" | "generated",
      "gutenberg_id": 1342,
      "category": "classics",
      "status": "planned" | "ready" | "published" | "failed" | "skipped",
      "output_dir": "...",
      "pdf": "path",
      "cover": "path",
      "audio": ["paths..."],
      "librivox": {"url": "...", "chapters": 37, "uploaded": true} | null,
      "description": "...",
      "created_at": "...",
      "published_at": "...",
      "error": "..."
    }
  ]
}
"""
import json
import os
import re


def slugify(text, maxlen=80):
    s = re.sub(r"[^A-Za-z0-9]+", "-", text).strip("-").lower()
    return s[:maxlen] or "book"


class BulkState:
    def __init__(self, path):
        self.path = path
        self.data = self._load()

    def _load(self):
        if os.path.exists(self.path):
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data.get("books"), list):
                    return data
            except Exception:
                pass
        return {"books": []}

    def save(self):
        os.makedirs(os.path.dirname(os.path.abspath(self.path)), exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)

    # ---- queries ---------------------------------------------------------
    def all(self):
        return self.data["books"]

    def find(self, slug=None, title=None, gutenberg_id=None):
        for b in self.data["books"]:
            if slug and b.get("slug") == slug:
                return b
            if title and self._norm(b.get("title", "")) == self._norm(title):
                return b
            if gutenberg_id is not None and b.get("gutenberg_id") == gutenberg_id:
                return b
        return None

    @staticmethod
    def _norm(s):
        return re.sub(r"[^a-z0-9]+", "", (s or "").lower())

    def is_known(self, title=None, gutenberg_id=None):
        return self.find(title=title, gutenberg_id=gutenberg_id) is not None

    def statuses(self, *statuses):
        return [b for b in self.data["books"] if b.get("status") in statuses]

    # ---- mutations -------------------------------------------------------
    def upsert(self, entry):
        existing = self.find(slug=entry.get("slug"), gutenberg_id=entry.get("gutenberg_id"))
        if existing:
            existing.update(entry)
        else:
            self.data["books"].append(entry)
        self.save()
        return entry

    def set_status(self, slug, status, **extra):
        b = self.find(slug=slug)
        if not b:
            return None
        b["status"] = status
        b.update(extra)
        if status in ("planned", "ready", "published") and "error" in b:
            b.pop("error", None)  # stale failure message from a previous run
        self.save()
        return b

    def new(self, source, title, author, **kw):
        entry = {
            "slug": kw.pop("slug", slugify(title)),
            "title": title,
            "author": author,
            "source": source,
            "status": "planned",
            "created_at": __import__("datetime").datetime.now().isoformat(timespec="seconds"),
        }
        entry.update(kw)
        return self.upsert(entry)
