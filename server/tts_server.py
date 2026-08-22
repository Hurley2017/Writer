"""Orpheus 3B TTS as an HTTP service - runs on the headless Debian server.

The Windows pipeline (src/tts.py) calls this instead of loading the model
locally when config.json -> tts.backend is "orpheus-http".

Endpoints
---------
POST /synthesize   {"text": "...", "cue": "<sigh>", "voice": "zac"}
                   -> 24 kHz mono WAV bytes
GET  /health       -> {"ok": true, "model_loaded": bool, "device": "..."}

IMPORTANT (GTX 1060 / Pascal): this loads the model in float16, NOT
bfloat16 - Pascal has no bfloat16 support and would fail or crawl.
"""
import io
import os
import re

import torch
from flask import Flask, jsonify, request, send_file

app = Flask(__name__)

SAMPLE_RATE = 24000
START_TOKEN = 128259
END_TOKENS = [128009, 128260, 128261, 128257]
AUDIO_END_MARK = 128257
AUDIO_PAD = 128258
AUDIO_BASE = 128266
DEFAULT_MODEL = "unsloth/orpheus-3b-0.1-ft-unsloth-bnb-4bit"

# emotion label -> Orpheus paralinguistic tag (must match src/tts.py)
EMOTION_TAG = {
    "calm": "", "neutral": "", "warm": "",
    "somber": " <sigh>", "mysterious": " <gasp>", "tense": "",
    "sad": " <sigh>", "dramatic": " <gasp>", "fearful": " <gasp>",
    "excited": " <laugh>", "joyful": " <laugh>", "angry": " <groan>", "": "",
}

_state = {"model": None, "tok": None, "snac": None}


def _inject_tag(text, cue):
    """Place the emotion tag inline (after the first sentence)."""
    if not cue:
        return text
    m = re.search(r"(?<=[.!?])\s+", text)
    if m:
        pos = m.end()
        return text[:pos] + cue + " " + text[pos:].lstrip()
    return text + cue


def load():
    if _state["model"] is not None:
        return
    model_id = os.environ.get("ORPHEUS_MODEL", DEFAULT_MODEL)
    print(f"Loading Orpheus {model_id} (float16, 4-bit) ...")
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from snac import SNAC

    tok = AutoTokenizer.from_pretrained(model_id)
    # float16: the GTX 1060 (Pascal sm_61) has no bfloat16 hardware support
    model = AutoModelForCausalLM.from_pretrained(
        model_id, dtype=torch.float16, device_map="cuda")
    model.eval()
    snac = SNAC.from_pretrained("hubertsiuzdak/snac_24khz").to("cuda").eval()
    _state.update(model=model, tok=tok, snac=snac)
    print(f"Orpheus ready on {model.device} | "
          f"VRAM used: {torch.cuda.memory_allocated() / 1024 ** 3:.2f} GiB")


def _decode_audio(generated_ids, input_len):
    ids = generated_ids[0, input_len:].cpu()
    marks = (ids == AUDIO_END_MARK).nonzero()
    if marks.numel():
        ids = ids[marks[-1].item() + 1:]
    ids = ids[ids != AUDIO_PAD]
    ids = ids - AUDIO_BASE
    n = (ids.numel() // 7) * 7
    ids = ids[:n]

    l0, l1, l2 = [], [], []
    for i in range(n // 7):
        f = ids[7 * i:7 * i + 7]
        l0.append(int(f[0]))
        l1.append(int(f[1]) - 4096)
        l2.append(int(f[2]) - 8192)
        l2.append(int(f[3]) - 12288)
        l1.append(int(f[4]) - 16384)
        l2.append(int(f[5]) - 20480)
        l2.append(int(f[6]) - 24576)

    device = next(_state["snac"].parameters()).device
    codes = [
        torch.tensor(x, dtype=torch.int32, device=device).unsqueeze(0)
        for x in (l0, l1, l2)
    ]
    with torch.inference_mode():
        audio = _state["snac"].decode(codes)
    audio = audio[:, :, 2048:].squeeze()
    return audio.detach().float().cpu().numpy()


@app.post("/synthesize")
def synthesize():
    body = request.get_json(force=True)
    text = body.get("text") or ""
    cue = body.get("cue") or ""
    voice = body.get("voice") or "zac"
    if not text:
        return jsonify({"error": "empty text"}), 400

    load()
    model, tok = _state["model"], _state["tok"]
    prompt = f"{voice}: {_inject_tag(text, cue)}"

    input_ids = tok(prompt, return_tensors="pt").input_ids
    start = torch.tensor([[START_TOKEN]], dtype=torch.int64)
    end = torch.tensor([END_TOKENS], dtype=torch.int64)
    full_ids = torch.cat([start, input_ids, end], dim=1).to(model.device)
    attn = torch.ones_like(full_ids)

    max_new = max(1024, min(12000, int(len(text) * 12)))
    with torch.inference_mode():
        generated = model.generate(
            input_ids=full_ids,
            attention_mask=attn,
            max_new_tokens=max_new,
            do_sample=True,
            temperature=0.7,
            top_p=0.9,
            repetition_penalty=1.15,
            eos_token_id=AUDIO_PAD,
            pad_token_id=tok.eos_token_id,
        )
    audio = _decode_audio(generated, full_ids.shape[1])

    import soundfile as sf
    buf = io.BytesIO()
    sf.write(buf, audio, SAMPLE_RATE, format="WAV")
    buf.seek(0)
    return send_file(buf, mimetype="audio/wav")


@app.get("/health")
def health():
    return jsonify({
        "ok": True,
        "model_loaded": _state["model"] is not None,
        "device": torch.cuda.get_device_name(0) if torch.cuda.is_available() else "cpu",
    })


if __name__ == "__main__":
    load()
    app.run(host="0.0.0.0", port=int(os.environ.get("TTS_PORT", "8000")))
