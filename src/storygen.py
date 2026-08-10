"""Generate the story outline and per-chapter content via a local LLM."""
import json
import re

from .lmstudio import LMStudioError

LENGTH_PARAGRAPHS = {"short": 3, "medium": 5, "long": 7}
LENGTH_SECTIONS = {"short": (2, 2, 3), "medium": (3, 3, 3), "long": (4, 3, 4)}


def parse_json(text):
    """Best-effort parse of an LLM JSON response. Tries multiple extraction strategies."""
    if not text:
        raise ValueError("Empty response from model")
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text)
    text = text.strip()

    candidates = _json_candidates(text)
    for cand in candidates:
        try:
            return json.loads(cand)
        except json.JSONDecodeError:
            pass
    # retry candidates with trailing-comma fixes
    for cand in candidates:
        fixed = re.sub(r",\s*([}\]])", r"\1", cand)
        try:
            return json.loads(fixed)
        except json.JSONDecodeError:
            pass
    raise ValueError(
        "No valid JSON object found in model response"
    )


def _json_candidates(text):
    """Yield plausible JSON substrings: whole text, then balanced objects/arrays."""
    yield text
    seen = set()
    for sub in _balanced_spans(text, "{", "}"):
        if sub not in seen:
            seen.add(sub)
            yield sub
    for sub in _balanced_spans(text, "[", "]"):
        if sub not in seen:
            seen.add(sub)
            yield sub


def _balanced_spans(text, open_ch, close_ch):
    start = 0
    while True:
        s = text.find(open_ch, start)
        if s == -1:
            return
        depth = 0
        for i in range(s, len(text)):
            if text[i] == open_ch:
                depth += 1
            elif text[i] == close_ch:
                depth -= 1
                if depth == 0:
                    yield text[s:i + 1]
                    start = i + 1
                    break
        else:
            return


def _normalize_chapter(data):
    """Coerce a model response into {paragraphs, image_prompts, emotions}.

    Accepts the exact schema, a few common alternative shapes small models
    emit (content nested under 'chapter'/'content'/'story', paragraph entries
    given as {paragraph|text|content: ...}), or a plain list of paragraph
    strings. Returns None when no usable paragraphs can be found.
    """
    if isinstance(data, list):
        paras = data
    elif isinstance(data, dict):
        paras = data.get("paragraphs")
        if not isinstance(paras, list):
            paras = None
            for key in ("content", "chapter", "story", "body", "text"):
                cand = data.get(key)
                if isinstance(cand, list):
                    paras = cand
                    break
                if isinstance(cand, dict):
                    paras = (cand.get("paragraphs") or cand.get("content")
                             or cand.get("text"))
                    if isinstance(paras, list):
                        break
                    paras = None
    else:
        return None
    if not isinstance(paras, list) or not paras:
        return None
    paragraphs = []
    for p in paras:
        if isinstance(p, str):
            paragraphs.append(p.strip())
        elif isinstance(p, dict):
            for k in ("paragraph", "text", "content", "scene"):
                v = p.get(k)
                if isinstance(v, str) and v.strip():
                    paragraphs.append(v.strip())
                    break
    paragraphs = [p for p in paragraphs if p]
    if not paragraphs:
        return None
    img = data.get("image_prompts") if isinstance(data, dict) else None
    emotions = data.get("emotions") if isinstance(data, dict) else None
    return {
        "paragraphs": paragraphs,
        "image_prompts": img if isinstance(img, list) else [],
        "emotions": emotions if isinstance(emotions, list) else [],
    }


def _split_paragraphs(text):
    """Split model prose into a list of non-empty paragraph strings."""
    if not text or not isinstance(text, str):
        return []
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text)
    text = text.strip()
    if not text:
        return []
    # 1) paragraphs separated by blank lines
    parts = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    if len(parts) >= 2:
        return parts
    # 2) one paragraph per line
    parts = [p.strip() for p in text.splitlines() if p.strip()]
    if len(parts) >= 2:
        return parts
    # 3) single text block: split into sentences
    return [p.strip() for p in re.split(r"(?<=[.!?])\s+", text) if p.strip()]


class StoryGenerator:
    def __init__(self, lm, model, cfg):
        self.lm = lm
        self.model = model
        self.cfg = cfg
        self.story_cfg = cfg["story"]
        self.lm_cfg = cfg["lmstudio"]

    def _chat_json(self, system, user, temperature, validate=None):
        """Ask the model for a JSON object, retrying up to 3 times.

        validate(parsed) -> None if the object is acceptable, or a short
        string describing the problem. Schema problems (not just JSON parse
        failures) therefore also trigger a corrective retry that tells the
        model exactly what it did wrong.
        """
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        last_raw = None
        last_err = None
        for attempt in range(3):
            msgs = list(messages)
            if attempt > 0:
                msgs.append({"role": "assistant", "content": last_raw or ""})
                hint = last_err or "That response was not valid JSON."
                msgs.append({
                    "role": "user",
                    "content": f"{hint} Respond with ONLY valid JSON matching the exact "
                               "structure requested. No prose, no markdown fences, no "
                               "explanations.",
                })
            try:
                text = self.lm.chat(msgs, model=self.model, temperature=temperature,
                                    max_tokens=self.lm_cfg.get("max_tokens", 4096),
                                    json_mode=True)
            except LMStudioError:
                # model may not support response_format=json_object; retry plain
                text = self.lm.chat(msgs, model=self.model, temperature=temperature,
                                    max_tokens=self.lm_cfg.get("max_tokens", 4096),
                                    json_mode=False)
            last_raw = text
            try:
                parsed = parse_json(text)
            except ValueError as e:
                last_err = f"That response was not valid JSON ({e})."
                continue
            if validate is not None:
                problem = validate(parsed)
                if problem:
                    last_err = problem
                    continue
            return parsed
        raise LMStudioError(
            f"Model did not return valid JSON after 3 attempts. Last model response was:\n"
            f"{str(last_raw)[:500]}"
        )

    # ------------------------------------------------------------------
    def generate_outline(self, params):
        """params: genre, topic, tone, length, title, language"""
        genre = params.get("genre") or "general fiction"
        topic = params.get("topic") or ""
        tone = params.get("tone") or ""
        length = params.get("length") or "medium"
        title = params.get("title") or ""
        language = params.get("language") or "English"

        n_sections, min_ch, max_ch = LENGTH_SECTIONS.get(length, LENGTH_SECTIONS["medium"])

        sys_prompt = (
            "You are a master novelist and book architect. You plan books and always "
            "respond with ONLY valid JSON - no markdown fences, no commentary, no prose."
        )
        user = f"""Create a book outline for a {genre} story written in {language}.
Topic / premise: {topic or '(invent something compelling)'}
Tone: {tone or '(pick a fitting tone)'}
Desired length: {length} ({n_sections} sections, {min_ch}-{max_ch} chapters per section).
Title: {title or '(invent a memorable title)'}

Return JSON in EXACTLY this shape (no other keys):
{{
  "title": "book title",
  "cover_prompt": "one detailed visual scene that captures the book's mood; for an image generator - no text, no letters, no words",
  "protagonist_gender": "male",
  "prologue": true,
  "sections": [
    {{"title": "section title", "chapters": ["chapter one title", "chapter two title"]}}
  ],
  "epilogue": true
}}

Rules:
- "protagonist_gender" is the gender of the main protagonist / narrator of the story
  (use exactly "male" or "female") - it decides which voice reads the book aloud.
- Chapters have evocative, scene-setting titles (do NOT prefix with 'Chapter N').
- Section titles are short and thematic.
- If the title was provided, keep it.
- prologue/epilogue are booleans (false means omit them)."""
        outline = self._chat_json(sys_prompt, user, self.lm_cfg.get("temperature_outline", 0.7),
                                  validate=self._validate_outline)
        return outline

    @staticmethod
    def _validate_outline(data):
        """Return None if data is a usable outline, else a short problem message."""
        if not isinstance(data, dict) or not isinstance(data.get("sections"), list):
            return ('Missing a non-empty "sections" array. Use EXACTLY: '
                    '{"title": "...", "cover_prompt": "...", "protagonist_gender": '
                    '"male", "prologue": true, "sections": [{"title": "...", '
                    '"chapters": ["..."]}], "epilogue": true}.')
        return None

    # ------------------------------------------------------------------
    def generate_chapter(self, outline, section_title, chapter_title, chapter_no, params):
        genre = params.get("genre") or "general fiction"
        tone = params.get("tone") or ""
        length = params.get("length") or "medium"
        language = params.get("language") or "English"
        n_paras = LENGTH_PARAGRAPHS.get(length, 5)
        book_title = outline.get("title", params.get("title") or "Untitled")

        sys_prompt = (
            "You are a master novelist writing an illustrated storybook. "
            "Every chapter is a sequence of vivid scene-paragraphs, each of which can be "
            "illustrated. Respond with ONLY valid JSON - no markdown, no commentary."
        )
        user = f"""Write Chapter {chapter_no} of the book '{book_title}'.
Section: {section_title}
Chapter title: {chapter_title}
Genre: {genre} | Tone: {tone} | Language: {language}

Write exactly {n_paras} paragraphs. Each paragraph is a self-contained scene of 3-5 sentences,
with strong sensory detail, so a reader could picture it.

Return JSON in EXACTLY this shape (no other keys):
{{
  "paragraphs": ["paragraph 1", "paragraph 2"],
  "image_prompts": ["one-line visual description of paragraph 1's scene", "one-line visual description of paragraph 2's scene"],
  "emotions": ["calm", "tense"]
}}

Rules for image_prompts (same length as paragraphs):
- Describe ONLY the visual content of that paragraph: characters, setting, objects, lighting, mood.
- Write it as an image-generation prompt (e.g. "a boy studying by lamplight in a rain-soaked village at dusk").
- NO text, letters, words, or captions inside the image. Never spell a character's name in the image.
- Keep each image prompt under 20 words.

Rules for emotions (same length as paragraphs):
- One emotion label per paragraph that a narrator should convey while reading it aloud.
- Use only these labels: calm, neutral, tense, sad, joyful, dramatic, fearful, excited, somber, warm, angry, mysterious.
- Match the emotion to what happens in that paragraph.
Do not include headings or section markers - paragraphs only."""
        try:
            data = self._chat_json(sys_prompt, user,
                                   self.lm_cfg.get("temperature_story", 0.9),
                                   validate=self._validate_chapter)
        except LMStudioError:
            data = self._fallback_prose(sys_prompt, user, book_title)
        return _normalize_chapter(data)

    @staticmethod
    def _validate_chapter(data):
        """Return None if data is a usable chapter, else a short problem message."""
        if _normalize_chapter(data) is None:
            return ('Missing a non-empty "paragraphs" array of strings. Use EXACTLY: '
                    '{"paragraphs": ["..."], "image_prompts": ["..."], '
                    '"emotions": ["..."]}.')
        return None

    def _fallback_prose(self, sys_prompt, user, book_title):
        """Small local models often cannot produce strict JSON - recover the chapter
        as plain prose instead of failing the whole book."""
        messages = [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": user + (
                "\n\nIf you cannot produce valid JSON, just write the chapter as plain "
                "prose instead. Separate every paragraph with an empty line. "
                "No headings, no bullet points, no JSON.")},
        ]
        text = self.lm.chat(messages, model=self.model,
                            temperature=self.lm_cfg.get("temperature_story", 0.9),
                            max_tokens=self.lm_cfg.get("max_tokens", 4096),
                            json_mode=False)
        # the model may still return (broken) JSON - reuse it when usable
        try:
            normalized = _normalize_chapter(parse_json(text))
            if normalized is not None:
                return normalized
        except ValueError:
            pass
        paragraphs = _split_paragraphs(text)
        if not paragraphs:
            raise LMStudioError(
                "Model returned invalid chapter content (missing 'paragraphs'). Try again.")
        print(f"        [!] JSON failed - recovered chapter from plain prose "
              f"({len(paragraphs)} paragraphs)")
        return {
            "paragraphs": paragraphs,
            "image_prompts": [f"an atmospheric scene from '{book_title}'" for _ in paragraphs],
            "emotions": ["neutral"] * len(paragraphs),
        }

    # ------------------------------------------------------------------
    def generate_cover_prompt_from_title(self, outline):
        return outline.get("cover_prompt") or f"an atmospheric cover scene for '{outline.get('title')}'"
