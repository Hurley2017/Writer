"""Configuration for the Bulk Publisher.

Layered load:
  1. defaults below
  2. d:\\Writer\\config.json           (existing writer pipeline — imagegen/tts/pdf reuse)
  3. bulk/bulk_config.json           (bulk-specific overrides, optional)
  4. bulk/secrets.json               (Supabase URL + admin login — NEVER committed)
"""
import json
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
_PROJECT = os.path.dirname(_HERE)

BULK_DEFAULTS = {
    "bulk": {
        "cache_dir": os.path.join(_HERE, "cache"),
        "state_file": os.path.join(_HERE, "state.json"),
        "output_dir": os.path.join(_PROJECT, "output"),
        "language": "en",
        "min_downloads": 5000,          # Gutendex candidates must exceed this
        "min_words": 1200,              # skip books shorter than this (garbage filter)
        "max_chapters_pdf": 200,        # hard cap so huge volumes stay buildable
        "cover_size": [896, 1152],
        "category": "classics",         # website category for classics
        "generated_category": "specials",  # website category for generated books
        "ffmpeg_path": "",              # auto-detected if empty (for wav->mp3)
        "librivox": "upload",           # link | upload | skip  (link=record URL only)
        "librivox_max_chapters": 80,    # safety cap for audiobook chapter uploads
        "open_pdf": False,
    },
    "publish": {
        "supabase_url": "",
        "admin_email": "",
        "admin_password": "",
    },
}


def _deep_merge(base, override):
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            _deep_merge(base[k], v)
        else:
            base[k] = v
    return base


def load_bulk_config():
    """Return a merged dict: defaults <- config.json <- bulk_config.json."""
    cfg = json.loads(json.dumps(BULK_DEFAULTS))  # deep copy

    # the existing writer pipeline config (imagegen / tts / pdf / lmstudio)
    writer_cfg_path = os.path.join(_PROJECT, "config.json")
    if os.path.exists(writer_cfg_path):
        with open(writer_cfg_path, "r", encoding="utf-8") as f:
            cfg["writer"] = json.load(f)

    bulk_cfg_path = os.path.join(_HERE, "bulk_config.json")
    if os.path.exists(bulk_cfg_path):
        with open(bulk_cfg_path, "r", encoding="utf-8") as f:
            _deep_merge(cfg, json.load(f))

    return cfg


def load_secrets():
    """Load publish credentials from bulk/secrets.json (git-ignored)."""
    path = os.path.join(_HERE, "secrets.json")
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def resolve_publish(cfg):
    """Merge bulk_config publish settings with secrets.json (secrets win)."""
    out = dict(cfg.get("publish", {}))
    out.update({k: v for k, v in load_secrets().items() if v})
    return out


def find_ffmpeg(cfg):
    """Resolve an ffmpeg executable (config -> PATH -> common install spots)."""
    p = cfg["bulk"].get("ffmpeg_path")
    if p and os.path.exists(p):
        return p
    import shutil
    p = shutil.which("ffmpeg")
    if p:
        return p
    for cand in (r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
                 r"C:\ffmpeg\bin\ffmpeg.exe",
                 os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WinGet\Links\ffmpeg.exe")):
        if os.path.exists(cand):
            return cand
    return None


def ensure_dirs(cfg):
    b = cfg["bulk"]
    for d in (b["cache_dir"], b["output_dir"]):
        os.makedirs(d, exist_ok=True)
    return cfg
