"""Configuration loader for the story writer pipeline."""
import json
import os

DEFAULTS = {
    "lmstudio": {
        "base_url": "http://localhost:1234/v1",
        "model": "",
        "temperature_outline": 0.7,
        "temperature_story": 0.9,
        "max_tokens": 4096,
    },
    "story": {
        "language": "English",
        "length": "medium",
    },
    "imagegen": {
        "backend": "auto",
        "style_prompt": "photorealistic, ultra detailed, professional photography, sharp focus, natural lighting, realistic textures, 8k uhd, film photography",
        "negative_prompt": "illustration, painting, cartoon, anime, drawing, 3d render, text, watermark, signature, logo, words, letters, low quality, blurry, distorted, deformed, ugly, bad hands, missing fingers, extra limbs, bad anatomy, jpeg artifacts, oversaturated",
        "width": 640,
        "height": 640,
        "steps": 32,
        "cfg_scale": 7,
        "sampler": "DPM++ 2M Karras",
        "sdwebui_url": "http://127.0.0.1:7860",
        "comfyui_url": "http://127.0.0.1:8188",
        "comfyui_workflow_file": "",
        "diffusers": {"model_path": ""},
        "openai": {"api_key": "", "base_url": "https://api.openai.com/v1",
                   "image_model": "gpt-image-1", "size": "1024x1024"},
        "cover_size": [768, 1088],
        "back_cover": "reuse",
    },
    "pdf": {"divider": True},
    "output": {"dir": "output", "open_pdf": True},
}


def _deep_merge(base, override):
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            _deep_merge(base[k], v)
        else:
            base[k] = v
    return base


def load_config(path=None):
    cfg = json.loads(json.dumps(DEFAULTS))  # deep copy
    if path is None:
        here = os.path.dirname(os.path.abspath(__file__))
        path = os.path.join(os.path.dirname(here), "config.json")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            user_cfg = json.load(f)
        _deep_merge(cfg, user_cfg)
    return cfg
