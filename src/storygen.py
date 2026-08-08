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


class StoryGenerator:
    def __init__(self, lm, model, cfg):
        self.lm = lm
        self.model = model
        self.cfg = cfg
        self.story_cfg = cfg["story"]
        self.lm_cfg = cfg["lmstudio"]

    def _chat_json(self, system, user, temperature):
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
                msgs.append({
                    "role": "user",
                    "content": "That response was not valid JSON. Respond with ONLY valid "
                               "JSON matching the exact structure requested. No prose, no "
                               "markdown fences, no explanations.",
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
                return parse_json(text)
            except ValueError as e:
                last_err = e
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
  "prologue": true,
  "sections": [
    {{"title": "section title", "chapters": ["chapter one title", "chapter two title"]}}
  ],
  "epilogue": true
}}

Rules:
- Chapters have evocative, scene-setting titles (do NOT prefix with 'Chapter N').
- Section titles are short and thematic.
- If the title was provided, keep it.
- prologue/epilogue are booleans (false means omit them)."""
        outline = self._chat_json(sys_prompt, user, self.lm_cfg.get("temperature_outline", 0.7))
        if "sections" not in outline or not isinstance(outline["sections"], list):
            raise LMStudioError("Model returned an invalid outline (missing 'sections'). Try again.")
        return outline

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
  "image_prompts": ["one-line visual description of paragraph 1's scene", "one-line visual description of paragraph 2's scene"]
}}

Rules for image_prompts (same length as paragraphs):
- Describe ONLY the visual content of that paragraph: characters, setting, objects, lighting, mood.
- Write it as an image-generation prompt (e.g. "a boy studying by lamplight in a rain-soaked village at dusk").
- NO text, letters, words, or captions inside the image. Never spell a character's name in the image.
- Keep each image prompt under 20 words.
Do not include headings or section markers - paragraphs only."""
        data = self._chat_json(sys_prompt, user, self.lm_cfg.get("temperature_story", 0.9))
        if "paragraphs" not in data or not isinstance(data["paragraphs"], list) or not data["paragraphs"]:
            raise LMStudioError("Model returned invalid chapter content (missing 'paragraphs'). Try again.")
        return data

    # ------------------------------------------------------------------
    def generate_cover_prompt_from_title(self, outline):
        return outline.get("cover_prompt") or f"an atmospheric cover scene for '{outline.get('title')}'"
