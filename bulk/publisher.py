"""Supabase publisher client for writers-palette.com.

Implements the exact contract used by the frontend (AuthContext.jsx):
  * login     : POST {supabase_url}/auth/v1/token?grant_type=password
                {email, password} -> {access_token}
  * publish   : POST {supabase_url}/functions/v1/publish-book
                multipart form: title, subtitle, description, category,
                cover (file), pdf (file), audio (file x N)
                Authorization: Bearer <access_token>
  * published : GET  {supabase_url}/rest/v1/published_books?select=title
                (dedupe guard — never re-publish a title already on the site)

The edge function requires an admin account (email ends with an allowed domain,
default @writers-palette.com). Re-publishing the same title REPLACES the old book,
so the bulk publisher must skip titles that are already live.
"""
import os
import re

import requests

TIMEOUT = 600  # publishing big audiobooks can take a while


class PublishError(RuntimeError):
    pass


def normalize_title(t):
    """Robust title normalization for dedupe matching ("The Adventures of Tom
    Sawyer, Complete" == "Adventures of Tom Sawyer")."""
    s = t or ""
    s = re.sub(r"\s*[,;:]?\s*(Complete|Unabridged|Volume\s*[IVXLC0-9]+|Vol\.?\s*[IVXLC0-9]+|\(.*?\)|\[.*?\])\s*$", "", s, flags=re.I).strip()
    s = re.sub(r"^The\s+", "", s, flags=re.I).strip()
    return re.sub(r"[^a-z0-9]+", "", s.lower())


def title_published(published_norm, title):
    """True if `title` (normalized) matches any already-published title."""
    t = normalize_title(title)
    return bool(t) and t in published_norm


class SupabasePublisher:
    def __init__(self, supabase_url, admin_email, admin_password, anon_key=""):
        self.base = (supabase_url or "").rstrip("/")
        self.email = admin_email
        self.password = admin_password
        self.anon_key = anon_key or ""
        self.token = None
        if not self.base:
            raise PublishError("supabase_url is not configured (see bulk/secrets.json)")

    # ---------------------------------------------------------------- auth
    def login(self, force=False):
        if self.token and not force:
            return self.token
        r = requests.post(
            f"{self.base}/auth/v1/token?grant_type=password",
            json={"email": self.email, "password": self.password},
            timeout=60,
        )
        if r.status_code != 200:
            try:
                msg = r.json().get("error_description") or r.json().get("msg") or r.text
            except Exception:
                msg = r.text
            raise PublishError(f"Login failed ({r.status_code}): {msg}")
        self.token = r.json()["access_token"]
        return self.token

    # ------------------------------------------------------------ published
    def published_titles(self):
        """All titles currently on the website (published_books table).

        Used as the dedupe guard so the bulk publisher never re-publishes a
        book that is already live (which would REPLACE the existing one).
        Returns the list of raw titles; [] if the query fails (best-effort —
        never blocks production).
        """
        try:
            token = self.login()
            auth = "Bearer " + token
            # apikey = the project anon key when provided, else the JWT itself
            # (the Supabase gateway accepts a valid project JWT as apikey).
            attempts = [self.anon_key or token]
            if self.anon_key:
                attempts.append(token)
            for apikey in attempts:
                r = requests.get(f"{self.base}/rest/v1/published_books?select=title",
                                 headers={"apikey": apikey, "Authorization": auth},
                                 timeout=30)
                if r.status_code == 200:
                    rows = r.json()
                    return [row.get("title", "") for row in rows if row.get("title")]
            print(f"[!] Could not read published_books ({r.status_code}) — "
                  f"website dedupe check skipped.")
        except Exception as e:
            print(f"[!] published_books check failed ({e}) — website dedupe "
                  f"check skipped.")
        return []

    def published_titles_norm(self):
        """Normalized set of titles already on the website."""
        return {normalize_title(t) for t in self.published_titles()}

    # ------------------------------------------------------------- publish
    def publish(self, title, cover_path, pdf_path,
                subtitle="", description="", category="classics", audio_paths=None,
                dry_run=False):
        """Publish one book. Returns the edge function's JSON response."""
        if not os.path.exists(cover_path):
            raise PublishError(f"Cover file not found: {cover_path}")
        if not os.path.exists(pdf_path):
            raise PublishError(f"PDF file not found: {pdf_path}")

        audio_paths = [a for a in (audio_paths or []) if a and os.path.exists(a)]

        if dry_run:
            print(f"[dry-run] would publish: {title}")
            print(f"           category={category} subtitle={subtitle or '-'}")
            print(f"           cover={cover_path}")
            print(f"           pdf={pdf_path}")
            print(f"           audio={len(audio_paths)} file(s)")
            return {"ok": True, "id": None, "title": title, "audio": len(audio_paths) or False, "dry_run": True}

        token = self.login()
        form = {
            "title": (None, title),
            "subtitle": (None, subtitle or ""),
            "description": (None, description or ""),
            "category": (None, category or "classics"),
        }
        files = [("cover", (os.path.basename(cover_path),
                            open(cover_path, "rb"), _mime(cover_path))),
                 ("pdf", (os.path.basename(pdf_path),
                          open(pdf_path, "rb"), "application/pdf"))]
        for a in audio_paths:
            files.append(("audio", (os.path.basename(a), open(a, "rb"), _mime(a))))

        try:
            r = requests.post(
                f"{self.base}/functions/v1/publish-book",
                headers={"Authorization": f"Bearer {token}"},
                data=form, files=files, timeout=TIMEOUT,
            )
        finally:
            for _, (_, fh, _) in files:
                fh.close()

        if r.status_code != 200:
            try:
                msg = r.json().get("error") or r.text
            except Exception:
                msg = r.text
            raise PublishError(f"Publish failed ({r.status_code}): {msg}")
        return r.json()


def _mime(path):
    ext = os.path.splitext(path)[1].lower()
    return {
        ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".webp": "image/webp", ".mp3": "audio/mpeg", ".wav": "audio/wav",
        ".m4a": "audio/mp4", ".ogg": "audio/ogg",
    }.get(ext, "application/octet-stream")
