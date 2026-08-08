"""Image generation backends for the story illustrations.

Supported backends:
  - sdwebui     : local Stable Diffusion WebUI (AUTOMATIC1111)  http://127.0.0.1:7860
  - comfyui     : local ComfyUI (needs an API-format workflow JSON)  http://127.0.0.1:8188
  - openai      : OpenAI Images API (DALL-E / gpt-image-1), needs an API key
  - placeholder : built-in gradient + caption images, no server needed (for testing)

"auto" tries sdwebui -> comfyui -> placeholder.
"""
import base64
import io
import os

import requests
from PIL import Image, ImageDraw, ImageFont

STYLE_KEYWORDS = ["cinematic", "illustration", "storybook"]


def detect_backend(cfg, force=None):
    """Return the backend id to use."""
    requested = force or cfg["imagegen"].get("backend", "auto")
    if requested != "auto":
        return requested
    g = cfg["imagegen"]
    if _reachable(g["sdwebui_url"] + "/sdapi/v1/sd-models", timeout=5):
        return "sdwebui"
    if _reachable(g["comfyui_url"] + "/system_stats", timeout=5):
        return "comfyui"
    return "placeholder"


def _reachable(url, timeout=5):
    try:
        requests.get(url, timeout=timeout)
        return True
    except requests.exceptions.RequestException:
        return False


class SDWebUI:
    def __init__(self, cfg):
        g = cfg["imagegen"]
        self.url = g["sdwebui_url"].rstrip("/")
        self.style = g.get("style_prompt", "")
        self.negative = g.get("negative_prompt", "")
        self.steps = g.get("steps", 24)
        self.cfg_scale = g.get("cfg_scale", 7)
        self.sampler = g.get("sampler", "DPM++ 2M Karras")

    def generate(self, prompt, width, height):
        payload = {
            "prompt": f"{prompt}, {self.style}",
            "negative_prompt": self.negative,
            "steps": self.steps,
            "width": width,
            "height": height,
            "cfg_scale": self.cfg_scale,
            "sampler_name": self.sampler,
            "batch_size": 1,
        }
        try:
            resp = requests.post(self.url + "/sdapi/v1/txt2img", json=payload, timeout=600)
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"Stable Diffusion WebUI unreachable: {e}") from e
        if resp.status_code != 200:
            raise RuntimeError(f"SD WebUI error {resp.status_code}: {resp.text[:300]}")
        data = resp.json()
        if not data.get("images"):
            raise RuntimeError("SD WebUI returned no images")
        img_bytes = base64.b64decode(data["images"][0])
        return Image.open(io.BytesIO(img_bytes)).convert("RGB")


class ComfyUI:
    def __init__(self, cfg):
        g = cfg["imagegen"]
        self.url = g["comfyui_url"].rstrip("/")
        self.workflow_file = g.get("comfyui_workflow_file", "")
        if not self.workflow_file or not os.path.exists(self.workflow_file):
            raise RuntimeError(
                "ComfyUI backend requires config.json -> imagegen.comfyui_workflow_file "
                "pointing to an API-format workflow JSON (exported from ComfyUI with "
                "'Save (API Format)'). The workflow must contain a node with a 'text' input "
                "that will receive the prompt."
            )

    def generate(self, prompt, width, height):
        import json

        with open(self.workflow_file, "r", encoding="utf-8") as f:
            workflow = json.load(f)
        # put the prompt into any node whose inputs contain a 'text' field
        prompt_node = None
        for nid, node in workflow.items():
            inputs = node.get("inputs", {})
            if isinstance(inputs, dict) and "text" in inputs and prompt_node is None:
                prompt_node = nid
        if prompt_node is None:
            raise RuntimeError("ComfyUI workflow has no node with a 'text' input for the prompt.")
        workflow[prompt_node]["inputs"]["text"] = f"{prompt}, {self.style}" if False else prompt

        # also try to set dimensions on the empty latent / image size
        payload = {"prompt": workflow}
        try:
            resp = requests.post(self.url + "/prompt", json=payload, timeout=30)
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"ComfyUI unreachable: {e}") from e
        if resp.status_code != 200:
            raise RuntimeError(f"ComfyUI error {resp.status_code}: {resp.text[:300]}")
        prompt_id = resp.json().get("prompt_id")
        # poll for output images
        import time
        for _ in range(120):
            time.sleep(1)
            try:
                hist = requests.get(self.url + f"/history/{prompt_id}", timeout=10).json()
            except requests.exceptions.RequestException:
                continue
            if prompt_id in hist:
                outputs = hist[prompt_id].get("outputs", {})
                for node_id, out in outputs.items():
                    for img in out.get("images", []):
                        sub = img.get("subfolder", "")
                        fn = img["filename"]
                        p = f"/view?filename={fn}&subfolder={sub}&type={img.get('type', 'output')}"
                        data = requests.get(self.url + p, timeout=30).content
                        return Image.open(io.BytesIO(data)).convert("RGB")
                # prompt finished but no image found
                break
        raise RuntimeError("ComfyUI finished without producing an image.")


class OpenAIImages:
    def __init__(self, cfg):
        g = cfg["imagegen"]["openai"]
        self.api_key = g.get("api_key", "")
        self.base_url = g.get("base_url", "https://api.openai.com/v1").rstrip("/")
        self.model = g.get("image_model", "gpt-image-1")
        self.size = g.get("size", "1024x1024")
        self.style = cfg["imagegen"].get("style_prompt", "")
        if not self.api_key:
            raise RuntimeError("OpenAI image backend requires an API key in config.json -> imagegen.openai.api_key")

    def generate(self, prompt, width, height):
        headers = {"Authorization": f"Bearer {self.api_key}"}
        payload = {
            "model": self.model,
            "prompt": f"{prompt}, {self.style}",
            "n": 1,
            "size": self.size,
        }
        try:
            resp = requests.post(self.base_url + "/images/generations", json=payload,
                                 headers=headers, timeout=300)
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"OpenAI images API unreachable: {e}") from e
        if resp.status_code != 200:
            raise RuntimeError(f"OpenAI error {resp.status_code}: {resp.text[:300]}")
        item = resp.json()["data"][0]
        if item.get("b64_json"):
            return Image.open(io.BytesIO(base64.b64decode(item["b64_json"]))).convert("RGB")
        if item.get("url"):
            data = requests.get(item["url"], timeout=120).content
            return Image.open(io.BytesIO(data)).convert("RGB")
        raise RuntimeError("OpenAI returned no image data")


class Placeholder:
    """No-server fallback: draws a gradient card with the prompt as a caption."""

    def __init__(self, cfg):
        self.style = cfg["imagegen"].get("style_prompt", "")

    def generate(self, prompt, width, height, caption=None):
        im = Image.new("RGB", (width, height))
        d = ImageDraw.Draw(im)
        top = (60, 74, 110)
        bottom = (24, 28, 44)
        for y in range(height):
            t = y / max(height - 1, 1)
            r = int(top[0] + (bottom[0] - top[0]) * t)
            g = int(top[1] + (bottom[1] - top[1]) * t)
            b = int(top[2] + (bottom[2] - top[2]) * t)
            d.line([(0, y), (width, y)], fill=(r, g, b))
        text = caption or prompt or "illustration"
        font = None
        for fp in (r"C:\Windows\Fonts\palab.ttf", r"C:\Windows\Fonts\arialbd.ttf"):
            if os.path.exists(fp):
                font = ImageFont.truetype(fp, size=max(18, width // 34))
                break
        if font is None:
            font = ImageFont.load_default()
        # wrap the caption
        words = text.split()
        lines, cur = [], ""
        for w in words:
            trial = f"{cur} {w}".strip()
            if d.textlength(trial, font=font) > width * 0.85 and cur:
                lines.append(cur)
                cur = w
            else:
                cur = trial
        lines.append(cur)
        y = height * 0.4
        for ln in lines[:6]:
            w = d.textlength(ln, font=font)
            d.text(((width - w) / 2, y), ln, fill=(235, 238, 245), font=font)
            y += int(font.size * 1.4)
        return im


def create_backend(cfg, force=None):
    backend = detect_backend(cfg, force=force)
    g = cfg["imagegen"]
    if backend == "sdwebui":
        return SDWebUI(cfg), backend
    if backend == "comfyui":
        return ComfyUI(cfg), backend
    if backend == "openai":
        return OpenAIImages(cfg), backend
    return Placeholder(cfg), backend


def generate_and_save(backend, prompt, width, height, out_path, caption=None):
    """Generate one image and save to out_path (PNG). Returns the path."""
    if isinstance(backend, Placeholder):
        img = backend.generate(prompt, width, height, caption=caption)
    else:
        img = backend.generate(prompt, width, height)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    img.save(out_path, "PNG")
    return out_path
