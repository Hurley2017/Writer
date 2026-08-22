"""Taste test: Fish Audio TTS (open API) reads the book's Prologue.

The Prologue paragraphs come from tools/extract_prologue.py (the faithful
transcription of 'Second Light of March.pdf').

Requires a Fish Audio API key from a free account:
    https://fish.audio/app/api-keys/
Provide it via the FISH_API_KEY env var, or type it when prompted
(the prompt hides your input).

Free model used: s2.1-pro-free  ->  POST https://api.fish.audio/v1/tts
"""
import base64
import getpass
import importlib.util
import os
import re
import struct
import sys

import msgpack
import requests

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)

# Load the canonical prologue paragraphs without importing tools as a package.
_spec = importlib.util.spec_from_file_location(
    "extract_prologue", os.path.join(_HERE, "extract_prologue.py"))
_ext = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_ext)
PARAGRAPHS = _ext.PARAGRAPHS

API_URL = "https://api.fish.audio/v1/tts"
DESIGN_URL = "https://api.fish.audio/v1/voice-design"
MODEL = "s2.1-pro-free"          # free developer tier (same S2.1 quality)
OUT_DIR = os.path.join(_ROOT, "output", "fish-prologue-sample")
KEY_FILE = os.path.join(_ROOT, ".fish_key")   # git-ignored local key file
TEMP_PLAIN = 0.7
TEMP_HOT = 1.0                   # higher temperature = more expressive/varied delivery

# A custom narrator voice, designed by Fish Audio's Voice Design API and then
# used for zero-shot TTS cloning so the prologue is read in THIS voice.
DRAMA_VOICE_INSTRUCTION = (
    "Deep, warm, highly expressive male audiobook narrator in his forties. "
    "Theatrical and dramatic, reads literary fiction with intense feeling: "
    "melancholic introspection, gentle tenderness, quiet grief, and moments of "
    "resolute determination. Slow, deliberate pacing, rich emotional range, "
    "natural breath and pauses. Somber literary narration."
)
DRAMA_REFERENCE_TEXT = (
    "Four months have elapsed, and I find myself conducting a rather "
    "inconvenient audit of my current psychological state."
)

PROLOGUE_TEXT = "\n\n".join(PARAGRAPHS)

# A genuinely expressive read: EVERY sentence carries its own emotion cue.
# Fish Audio's S2 models perform [bracket] cues - documented fixed tags plus
# natural-language intensity/delivery descriptions ([whispering], [soft tone],
# [break], [slow and heavy]...). One cue per paragraph is too weak; sentence-
# level cues are what actually make the narrator perform the emotion.
EMOTIVE_CUES = [
    # P1 - somber introspection (3 sentences)
    ["[somber]", "[somber]", "[sad][whispering]"],
    # P2 - warm / nostalgic / moved (5 sentences)
    ["[warm]", "[sarcastic][soft tone]", "[warm][hopeful]", "[moved][break]", "[calm]"],
    # P3 - sad / resigned / regretful (3 sentences)
    ["[sad]", "[resigned]", "[regretful][soft tone]"],
    # P4 - heavy then determined (2 sentences)
    ["[somber][slow and heavy]", "[determined][hopeful]"],
    # P5 - calm / empathetic (3 sentences)
    ["[calm][soft tone]", "[calm]", "[empathetic][gentle]"],
]


def _split_sentences(para):
    """Split a paragraph into sentences on . ! ? followed by a new sentence."""
    return [s.strip() for s in
            re.split(r"(?<=[.!?])\s+(?=[A-Z\"'])", para.strip()) if s.strip()]


EMOTIVE_PARAGRAPHS = []
for cues, para in zip(EMOTIVE_CUES, PARAGRAPHS):
    sentences = _split_sentences(para)
    if len(sentences) != len(cues):
        raise SystemExit(
            f"Mismatch: {len(cues)} cues vs {len(sentences)} sentences in paragraph:\n{para}")
    EMOTIVE_PARAGRAPHS.append(" ".join(f"{cue} {s}" for cue, s in zip(cues, sentences)))
EMOTIVE_TEXT = "\n\n".join(EMOTIVE_PARAGRAPHS)

# (label, reference_id or None for the default voice, text override or None, temperature)
VOICES = [
    ("default", None, None, TEMP_PLAIN),
    ("male", "9a9cf47702da476aa4629e2506d4a857", None, TEMP_PLAIN),   # "Energetic Male" (public library)
    ("emotive-default", None, EMOTIVE_TEXT, TEMP_HOT),
    ("emotive-male", "9a9cf47702da476aa4629e2506d4a857", EMOTIVE_TEXT, TEMP_HOT),
]


def get_key():
    """Key lookup order: FISH_API_KEY env var -> .fish_key file -> interactive prompt."""
    key = os.environ.get("FISH_API_KEY", "").strip()
    if key:
        return key
    try:
        with open(KEY_FILE, "r", encoding="utf-8") as f:
            key = f.read().strip()
    except OSError:
        key = ""
    if key:
        return key
    return getpass.getpass(
        "Fish Audio API key (free account: https://fish.audio/app/api-keys/): ").strip()


def synth(key, text, reference_id, out_path, temperature=TEMP_PLAIN):
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "model": MODEL,
    }
    payload = {"text": text, "format": "mp3", "sample_rate": 44100,
               "temperature": temperature}
    if reference_id:
        payload["reference_id"] = reference_id
    resp = requests.post(API_URL, json=payload, headers=headers, timeout=180)
    if resp.status_code != 200:
        raise RuntimeError(f"Fish Audio error {resp.status_code}: {resp.text[:400]}")
    with open(out_path, "wb") as f:
        f.write(resp.content)
    print(f"  saved {out_path} ({len(resp.content) / 1024:.1f} KiB)")


def design_voice(key):
    """Design an expressive narrator voice; return the first candidate."""
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "model": "voice-design-1",
    }
    payload = {
        "instruction": DRAMA_VOICE_INSTRUCTION,
        "reference_text": DRAMA_REFERENCE_TEXT,
        "language": "en",
        "n": 2,
        "speed": 1,
        "guidance_scale": 3,
    }
    resp = requests.post(DESIGN_URL, json=payload, headers=headers, timeout=180)
    if resp.status_code != 200:
        raise RuntimeError(f"Voice design error {resp.status_code}: {resp.text[:400]}")
    cands = resp.json().get("candidates", [])
    if not cands:
        raise RuntimeError("Voice design returned no candidates.")
    return cands[0]


def _as_wav_bytes(audio_bytes, sample_rate):
    """Wrap raw 16-bit mono PCM in a WAV container (no-op if already a WAV)."""
    if audio_bytes[:4] == b"RIFF":
        return audio_bytes
    hdr = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF", 36 + len(audio_bytes), b"WAVE",
        b"fmt ", 16, 1, 1, sample_rate, sample_rate * 2, 2, 16,
        b"data", len(audio_bytes),
    )
    return hdr + audio_bytes


def synth_with_reference(key, text, ref_wav, ref_text, out_path, temperature=TEMP_HOT):
    """Zero-shot TTS in a designed voice (MessagePack 'references')."""
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/msgpack",
        "model": MODEL,
    }
    payload = {
        "text": text,
        "references": [{"audio": ref_wav, "text": ref_text}],
        "format": "mp3",
        "sample_rate": 44100,
        "temperature": temperature,
    }
    resp = requests.post(API_URL, data=msgpack.packb(payload), headers=headers, timeout=240)
    if resp.status_code != 200:
        raise RuntimeError(f"Fish Audio error {resp.status_code}: {resp.text[:400]}")
    with open(out_path, "wb") as f:
        f.write(resp.content)
    print(f"  saved {out_path} ({len(resp.content) / 1024:.1f} KiB)")


def make_drama_sample(key):
    """Design a theatrical narrator voice and read the emotive prologue in it."""
    print("  - designing expressive narrator voice ...")
    cand = design_voice(key)
    audio = base64.b64decode(cand["audio_base64"])
    sample_rate = cand.get("sample_rate") or 44100
    ref_wav = _as_wav_bytes(audio, sample_rate)
    preview = os.path.join(OUT_DIR, "drama-voice-preview.wav")
    with open(preview, "wb") as f:
        f.write(ref_wav)
    print(f"  saved voice preview {preview} "
          f"({cand.get('duration_ms', 0) / 1000:.1f}s @ {sample_rate} Hz)")
    ref_text = cand.get("text") or DRAMA_REFERENCE_TEXT
    out = os.path.join(OUT_DIR, "prologue-drama.mp3")
    try:
        # try using the designed voice id directly (simpler); fall back to clone
        synth(key, EMOTIVE_TEXT, cand["id"], out, temperature=TEMP_HOT)
    except RuntimeError as e:
        print(f"    (direct voice id failed: {str(e)[:120]} - using zero-shot clone)")
        synth_with_reference(key, EMOTIVE_TEXT, ref_wav, ref_text, out, temperature=TEMP_HOT)


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    key = get_key()
    if not key:
        print("No API key provided - aborting.")
        return 1
    wanted = sys.argv[1:] or [label for label, _, _, _ in VOICES]
    print(f"Generating prologue sample(s) with Fish Audio ({MODEL}) ...")
    for label, ref, text, temperature in VOICES:
        if label not in wanted:
            continue
        print(f"  - {label} ...")
        synth(key, text or PROLOGUE_TEXT, ref,
              os.path.join(OUT_DIR, f"prologue-{label}.mp3"), temperature=temperature)
    if "drama" in wanted:
        make_drama_sample(key)
    print(f"\nDone. Files in {OUT_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
