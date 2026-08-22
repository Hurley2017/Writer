"""Environment health audit for the Bulk Publisher.

Checks that every model/service the two tracks need is actually in place:
  * LLM server (LM Studio / Ollama) — used only by the GENERATED track
  * Stable Diffusion model file / image backend — cover art
  * TTS (Orpheus cache / supertonic) — audiobooks
  * ffmpeg — WAV -> MP3
  * Python packages (torch/diffusers only needed for generated track)
  * publish credentials (secrets.json)
"""
import os
import shutil
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_PROJ = os.path.dirname(_HERE)

SD_MODELS = [
    r"D:\stable-diffusion-webui\models\Stable-diffusion\RealVisXL_V4.0.safetensors",
    r"D:\stable-diffusion-webui\models\Stable-diffusion\Realistic_Vision_V5.1_fp16-no-ema.safetensors",
    r"D:\stable-diffusion-webui\models\Stable-diffusion\v1-5-pruned-emaonly.safetensors",
]
HF_CACHE = r"D:\hf_cache\hub"
ORPHEUS_IDS = [
    "models--unsloth--orpheus-3b-0.1-ft-unsloth-bnb-4bit",
    "models--unsloth--orpheus-3b-0.1-ft",
    "models--hubertsiuzdak--snac_24khz",
]


def _try_import(name):
    try:
        __import__(name)
        return True
    except Exception:
        return False


def check_llm(cfg, timeout=3):
    """LM Studio / Ollama reachability + loaded models (short timeouts so the
    health panel never blocks for long when the server is down)."""
    lm = _writer(cfg, "lmstudio")
    urls = [lm.get("base_url", "").rstrip("/")]
    for extra in ("http://localhost:1234/v1", "http://127.0.0.1:11434/v1"):
        if extra not in urls:
            urls.append(extra)
    import requests
    for u in urls:
        if not u:
            continue
        try:
            r = requests.get(u + "/models", timeout=timeout)
            if r.status_code == 200:
                models = [m.get("id", "") for m in r.json().get("data", [])]
                non_emb = [m for m in models if "embed" not in m.lower()]
                return {"ok": True, "url": u, "models": models,
                        "loaded": non_emb or models,
                        "note": "LM Studio reachable" if "1234" in u else "Ollama reachable"}
        except Exception:
            continue
    return {"ok": False, "url": lm.get("base_url", ""),
            "models": [], "loaded": [],
            "note": "LLM server not reachable (start LM Studio / the remote server). "
                    "Only needed for the GENERATED track."}


def _writer(cfg, key):
    """bulk config nests the writer pipeline config under cfg['writer']."""
    w = cfg.get("writer") or {}
    return w.get(key) or cfg.get(key) or {}


def check_image(cfg):
    b = _writer(cfg, "imagegen")
    backend = b.get("backend", "auto")
    model_path = b.get("diffusers", {}).get("model_path", "")
    found = [p for p in SD_MODELS if os.path.exists(p)]
    diff = b.get("diffusers", {})
    configured = os.path.exists(model_path) if model_path else False
    return {
        "ok": bool(found) or backend in ("sdwebui", "openai") or configured,
        "backend": backend,
        "model_path": model_path,
        "model_exists": configured,
        "known_models": found,
        "note": ("Stable Diffusion checkpoint found" if found else
                 "No SD checkpoint found — covers will fall back to typographic "
                 "(classics) or fail (generated)"),
    }


def check_tts(cfg):
    t = _writer(cfg, "tts")
    backend = t.get("backend", "")
    orpheus_ok = any(os.path.isdir(os.path.join(HF_CACHE, i)) for i in ORPHEUS_IDS)
    supertonic = _try_import("supertonic")
    ffmpeg = find_ffmpeg()
    return {
        "ok": orpheus_ok or supertonic,
        "backend": backend,
        "orpheus_cached": orpheus_ok,
        "supertonic_installed": supertonic,
        "ffmpeg": ffmpeg or "",
        "note": ("TTS model cached + ffmpeg ready" if (orpheus_ok or supertonic) and ffmpeg else
                 "TTS partially configured — check orpheus cache / ffmpeg"),
    }


def find_ffmpeg():
    p = shutil.which("ffmpeg")
    if p:
        return p
    for cand in (r"C:\Program Files\ffmpeg\bin\ffmpeg.exe", r"C:\ffmpeg\bin\ffmpeg.exe"):
        if os.path.exists(cand):
            return cand
    return ""


def check_python():
    sd_venv = os.path.exists(r"D:\stable-diffusion-webui\venv\Scripts\python.exe")
    this = sys.executable
    return {
        "ok": True,
        "python": this,
        "sd_venv_present": sd_venv,
        "torch": _try_import("torch"),
        "diffusers": _try_import("diffusers"),
        "transformers": _try_import("transformers"),
        "reportlab": _try_import("reportlab"),
        "flask": _try_import("flask"),
        "note": "Using " + ("the full SD venv" if "stable-diffusion-webui" in this else "this venv"),
    }


def check_secrets():
    path = os.path.join(_HERE, "secrets.json")
    ok = os.path.exists(path)
    return {
        "ok": ok,
        "path": path,
        "note": ("Publish credentials found — runs can publish" if ok else
                 "No bulk/secrets.json — runs will default to no-publish "
                 "(copy secrets.json.example)"),
    }


_CACHE = {"at": 0.0, "data": None}
_CACHE_TTL = 30.0  # seconds


def full_check(cfg=None, refresh=False):
    """Health audit with a short cache (the LLM probes can take ~3s each)."""
    import time
    now = time.time()
    if not refresh and _CACHE["data"] and now - _CACHE["at"] < _CACHE_TTL:
        return _CACHE["data"]
    if cfg is None:
        from bulk.bulk_config import load_bulk_config
        cfg = load_bulk_config()
    data = {
        "llm": check_llm(cfg),
        "image": check_image(cfg),
        "tts": check_tts(cfg),
        "python": check_python(),
        "secrets": check_secrets(),
        "config_lmstudio_url": _writer(cfg, "lmstudio").get("base_url", ""),
        "config_sdwebui_url": _writer(cfg, "imagegen").get("sdwebui_url", ""),
        "config_tts_server": _writer(cfg, "tts").get("server_url", ""),
    }
    _CACHE["at"] = now
    _CACHE["data"] = data
    return data


if __name__ == "__main__":
    import json
    import sys as _sys
    _sys.path.insert(0, _PROJ)
    from bulk.bulk_config import load_bulk_config
    print(json.dumps(full_check(load_bulk_config()), indent=2, ensure_ascii=False))
