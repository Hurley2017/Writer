"""Audiobook narration via Orpheus 3B TTS - local, expressive, GPU-accelerated.

Orpheus 3B (fine-tuned Llama 3.2 3B) emits SNAC audio-codec tokens; a SNAC
vocoder turns them into 24 kHz speech.

Emotion tags (<laugh> <chuckle> <sigh> <cough> <sniffle> <groan> <yawn>
<gasp>) are plain text the model was fine-tuned to PERFORM as paralinguistic
sounds - but only when they appear INLINE mid-sentence with text after them.
A tag trailing at the very end of the prompt is read aloud as the word itself,
so we inject each paragraph's emotion tag right after its first sentence.

Only the narrator voice goes in the "{voice}: " prefix - anything else there
would be spoken as words, so style phrases ("slow, deep") are intentionally
NOT injected.

Dual-voice narration: the actual story paragraphs are read by a narrator voice
chosen by the protagonist's gender (female -> voice_female, male -> voice_male),
and every chapter title is ANNOUNCED by the other voice (like a book reader).
The protagonist's gender comes from the story itself ("narrator" field, added by
storygen from the outline) and falls back to config/heuristics.

The model is loaded 4-bit (bitsandbytes) so it fits comfortably in 8 GB VRAM
while leaving room for the KV cache during generation.
"""
import os
import re
import requests

# emotion label -> Orpheus paralinguistic tag appended to the narration text
EMOTION_TAG = {
    "calm": "",
    "neutral": "",
    "warm": "",
    "somber": " <sigh>",
    "mysterious": " <gasp>",
    "tense": "",
    "sad": " <sigh>",
    "dramatic": " <gasp>",
    "fearful": " <gasp>",
    "excited": " <laugh>",
    "joyful": " <laugh>",
    "angry": " <groan>",
    "": "",
}

SILENCE_PARA = 0.9     # seconds between paragraphs (deliberate pacing)
SILENCE_CHAPTER = 1.5  # seconds between chapters

SAMPLE_RATE = 24000  # Orpheus / snac_24khz output rate

# Special token ids used by the Orpheus prompt wrapper
START_TOKEN = 128259  # <|start_of_human|>
END_TOKENS = [128009, 128260, 128261, 128257]  # <|eot_id|>, <|end_of_human|>, <|eom_id|>, <|end_of_audio|>
AUDIO_END_MARK = 128257  # crop everything up to the last occurrence
AUDIO_PAD = 128258  # dropped if present; also used as eos_token_id
AUDIO_BASE = 128266  # first audio-codec token id (= 128256 + 10)

DEFAULT_MODEL = "unsloth/orpheus-3b-0.1-ft-unsloth-bnb-4bit"


class AudiobookError(Exception):
    pass


class AudiobookGenerator:
    """Generate an audiobook from a story dict using Orpheus 3B TTS."""

    def __init__(self, cfg, device=None):
        self.cfg = cfg
        self.tcfg = cfg.get("tts", {}) or {}
        self.model_id = self.tcfg.get("model", "") or DEFAULT_MODEL
        self.voice = self.tcfg.get("voice", "") or ""  # legacy single-voice override
        self.voice_female = self.tcfg.get("voice_female", "jess") or "jess"
        self.voice_male = self.tcfg.get("voice_male", "zac") or "zac"
        self.narrator = (self.tcfg.get("narrator", "auto") or "auto").lower().strip()
        self.style = self.tcfg.get("style", "") or ""
        self.hf_cache = self.tcfg.get("hf_cache_dir", "") or ""
        self.backend = (self.tcfg.get("backend", "") or "orpheus").lower().strip()
        self.server_url = (self.tcfg.get("server_url", "") or "").rstrip("/")
        # remote mode: synthesize on the headless server instead of locally
        self._remote = self.backend in ("orpheus-http", "remote", "http") or bool(self.server_url)
        self._set_hf_env()
        self._model = None
        self._tok = None
        self._snac = None

    # ----------------------------------------------------------------
    def _set_hf_env(self):
        if self.hf_cache:
            os.environ.setdefault("HF_HOME", self.hf_cache)
            os.environ.setdefault("HF_HUB_CACHE", os.path.join(self.hf_cache, "hub"))
        os.environ["HF_HUB_DISABLE_SYMLINKS"] = "1"

    def _get_model(self):
        if self._remote:
            return None
        if self._model is not None:
            return self._model
        try:
            import torch
            from transformers import AutoModelForCausalLM, AutoTokenizer
            from snac import SNAC
        except ImportError as e:
            raise AudiobookError(
                "Orpheus deps missing. Run:  pip install transformers snac bitsandbytes"
            ) from e

        print(f"      Loading Orpheus 3B TTS (voice={self.voice}, "
              f"model={self.model_id}) ...")
        self._tok = AutoTokenizer.from_pretrained(self.model_id)
        self._model = AutoModelForCausalLM.from_pretrained(
            self.model_id, dtype=torch.bfloat16, device_map="cuda"
        )
        self._model.eval()
        self._snac = SNAC.from_pretrained("hubertsiuzdak/snac_24khz").to("cuda").eval()
        print(f"      Orpheus on {self._model.device} | "
              f"VRAM used (GiB): {torch.cuda.memory_allocated() / 1024 ** 3:.2f}")
        return self._model

    # ----------------------------------------------------------------
    def emotion_tag(self, emotion):
        return EMOTION_TAG.get((emotion or "").lower().strip(), "")

    def _inject_tag(self, text, cue):
        """Place an emotion tag INLINE (after the first sentence) so the model
        performs it instead of reading it aloud as a word."""
        if not cue:
            return text
        m = re.search(r"(?<=[.!?])\s+", text)
        if m:
            pos = m.end()
            return text[:pos] + cue + " " + text[pos:].lstrip()
        return text + cue

    def _build_prompt(self, text, cue=None, voice=None):
        """{voice}: {text with inline emotion tag} - canonical Orpheus format."""
        body = self._inject_tag(text, cue)
        v = voice or self.voice or "zac"
        return f"{v}: {body}"

    # ----------------------------------------------------------------
    def _narrator_gender(self, story):
        """Decide narrator gender: story field > config > pronoun heuristic > male."""
        s = (story or {}).get("narrator", "") or ""
        if s in ("male", "female"):
            return s
        if self.narrator in ("male", "female"):
            return self.narrator
        g = self._guess_gender(story)
        return g or "male"

    @staticmethod
    def _guess_gender(story):
        """Rough heuristic: count masculine vs feminine pronouns in the prose."""
        import re
        parts = []

        def add(ch):
            if ch:
                parts.extend(ch.get("paragraphs") or [])

        if story:
            add(story.get("prologue"))
            for sec in story.get("sections", []):
                for ch in sec.get("chapters", []):
                    add(ch)
            add(story.get("epilogue"))
        blob = " ".join(parts).lower()
        m = len(re.findall(r"\b(he|him|his)\b", blob))
        f = len(re.findall(r"\b(she|her|hers)\b", blob))
        if m == f:
            return ""
        return "male" if m > f else "female"

    def _voices(self, story):
        """Return (narrator_voice, announcer_voice) for a story."""
        if self._narrator_gender(story) == "female":
            return self.voice_female, self.voice_male
        return self.voice_male, self.voice_female

    def _decode_audio(self, generated_ids, input_len):
        """Turn generated token ids into 24 kHz mono float32 audio via SNAC."""
        import torch

        ids = generated_ids[0, input_len:].cpu()
        # Crop everything up to & including the last end-of-audio marker.
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

        device = next(self._snac.parameters()).device
        codes = [
            torch.tensor(l0, dtype=torch.int32, device=device).unsqueeze(0),
            torch.tensor(l1, dtype=torch.int32, device=device).unsqueeze(0),
            torch.tensor(l2, dtype=torch.int32, device=device).unsqueeze(0),
        ]
        with torch.inference_mode():
            audio = self._snac.decode(codes)
        # Drop the codec warm-up (~2048 samples) and flatten to mono 1-D.
        audio = audio[:, :, 2048:].squeeze()
        return audio.detach().float().cpu().numpy()

    def synthesize_text(self, text, cue=None, voice=None):
        """Return a numpy mono float32 audio array for one text chunk."""
        if self._remote:
            return self._synthesize_remote(text, cue=cue, voice=voice)
        import torch

        model = self._get_model()
        tok = self._tok

        prompt = self._build_prompt(text, cue=cue, voice=voice)
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
        return self._decode_audio(generated, full_ids.shape[1])

    def _synthesize_remote(self, text, cue=None, voice=None):
        """Call the Orpheus HTTP service on the server; return mono float32 audio."""
        import io
        import numpy as np
        import soundfile as sf

        if not self.server_url:
            raise AudiobookError(
                "tts.backend is remote but tts.server_url is not set in config.json.")
        try:
            resp = requests.post(
                self.server_url + "/synthesize",
                json={"text": text, "cue": cue or "", "voice": voice or "zac"},
                timeout=600)
            resp.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise AudiobookError(
                f"TTS server unreachable at {self.server_url}: {e}") from e
        data, _sr = sf.read(io.BytesIO(resp.content), dtype="float32")
        return np.asarray(data, dtype=np.float32).reshape(-1)

    # ----------------------------------------------------------------
    def _silence(self, seconds):
        import numpy as np
        return np.zeros(int(seconds * SAMPLE_RATE), dtype=np.float32)

    def _to_mono_1d(self, wav):
        import numpy as np
        return np.asarray(wav, dtype=np.float32).reshape(-1)

    # ----------------------------------------------------------------
    def synthesize_chapter(self, title, chapter, voice=None):
        """Synthesize one chapter's paragraphs (with pauses) into one numpy array."""
        import numpy as np

        self._get_model()
        paras = chapter.get("paragraphs") or []
        emotions = chapter.get("emotions") or []
        chunks = []
        for i, p in enumerate(paras):
            if i > 0:
                chunks.append(self._silence(SILENCE_PARA))
            emotion = emotions[i] if i < len(emotions) else ""
            cue = self.emotion_tag(emotion)
            chunks.append(self._to_mono_1d(self.synthesize_text(p, cue=cue, voice=voice)))
        if not chunks:
            return None
        return np.concatenate(chunks)

    # ----------------------------------------------------------------
    def generate_book(self, story, out_dir):
        """Synthesize the whole book; write per-chapter WAVs + one combined audiobook."""
        import numpy as np
        import soundfile as sf

        self._get_model()
        os.makedirs(out_dir, exist_ok=True)

        sr = SAMPLE_RATE
        narrator, announcer = self._voices(story)
        print(f"      Narrator: {narrator} (body) | Announcer: {announcer} (chapter titles)")
        chapter_files = []
        full = []
        count = 0

        def save_wav(path, audio):
            sf.write(path, audio, sr)

        def add_block(title, chapter, label):
            nonlocal count
            if not chapter:
                return
            count += 1
            print(f"      Narrating {label}: {title}")
            # announce the chapter title in the announcer voice, then narrate
            ann = self._to_mono_1d(self.synthesize_text(title, voice=announcer))
            body = self.synthesize_chapter(title, chapter, voice=narrator)
            if body is None:
                return
            audio = np.concatenate([ann, self._silence(0.5), body])
            wav_path = os.path.join(out_dir, f"{label:02d}_{_slug(title)}.wav")
            save_wav(wav_path, audio)
            chapter_files.append(wav_path)
            if full:
                full.append(self._silence(SILENCE_CHAPTER))
            full.append(audio)

        if story.get("prologue"):
            add_block(story["prologue"].get("title", "Prologue"), story["prologue"], 1)
        for si, sec in enumerate(story.get("sections", [])):
            for ci, ch in enumerate(sec.get("chapters", []), start=1):
                add_block(ch.get("title", f"Chapter {ci}"), ch, 2 + ci)
        if story.get("epilogue"):
            add_block(story["epilogue"].get("title", "Epilogue"), story["epilogue"], 999)

        if full:
            audiobook = np.concatenate(full)
            audiobook_path = os.path.join(out_dir, "audiobook.wav")
            save_wav(audiobook_path, audiobook)
            print(f"      Audiobook: {audiobook_path}")
        return chapter_files


def _slug(text):
    import re
    s = re.sub(r"[^A-Za-z0-9]+", "-", text).strip("-").lower()
    return s[:50] or "part"
