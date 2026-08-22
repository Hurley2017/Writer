"""Parse a raw Project Gutenberg plain-text file into a structured book.

Handles the widely-varying Gutenberg header/footer conventions and splits the
body into chapters by heading lines (CHAPTER I, Chapter 1, Book First, Part I,
Volume I, Canto I, Act I, Scene I, Letter I, ...). Output shape:

    {
      "title": str,
      "author": str,
      "front": [str, ...],            # paragraphs before the first chapter
      "chapters": [{"title": str, "paragraphs": [str, ...]}, ...],
      "word_count": int,
    }

Heuristic rules (chosen to be conservative — false *negatives* are fine, we
fall back to a single chapter; false *positives* would wreck the book):
  * a heading line must match a chapter-ish pattern,
  * be <= 100 chars,
  * be a standalone line (blank line before and after, or at the very start).
"""
import re

START_RE = re.compile(r"^\*{3}\s*START OF (?:THE |THIS )?PROJECT GUTENBERG EBOOK.*$", re.I | re.M)
END_RE = re.compile(r"^\*{3}\s*END OF (?:THE |THIS )?PROJECT GUTENBERG EBOOK.*$", re.I | re.M)
META_RE = re.compile(r"^(Title|Author|Illustrator|Translator|Editor|Release [Dd]ate|"
                     r"[Ll]anguage|[Cc]redits|[Pp]roducer|[Nn]ote|[Pp]osting [Dd]ate|"
                     r"[Cc]haracters?|[Ss]ubject):")
PG_HEADER_RE = re.compile(r"^(The Project Gutenberg eBook of|Project Gutenberg's)")

# NOTE: must match at least ONE character — an all-optional Roman pattern
# matches the empty string at any word boundary and flags sentence fragments
# like "letter |which...". [IVXLCDM]+ is conservative and safe.
ROMAN = r"[IVXLCDM]+"
_ORDINALS = (
    r"(?:FIRST|SECOND|THIRD|FOURTH|FIFTH|SIXTH|SEVENTH|EIGHTH|NINTH|TENTH|"
    r"ELEVENTH|TWELFTH|THIRTEENTH|FOURTEENTH|FIFTEENTH|SIXTEENTH|SEVENTEENTH|"
    r"EIGHTEENTH|NINETEENTH|TWENTIETH|TWENTY-[A-Z]+|ONE|TWO|THREE|FOUR|FIVE|SIX|SEVEN|"
    r"EIGHT|NINE|TEN|ELEVEN|TWELVE|THIRTEEN|FOURTEEN|FIFTEEN|SIXTEEN|SEVENTEEN|"
    r"EIGHTEEN|NINETEEN|TWENTY|THIRTY|FORTY|FIFTY|SIXTY|SEVENTY|EIGHTY|NINETY|HUNDRED)"
)

# A heading line must start with one of these tokens (case-insensitive).
_HEAD_TOKEN = (
    r"CHAPTER\b|CHAP\.?\b|BOOK\b|PART\b|VOLUME\b|VOL\.?\b|CANTO\b|ACT\b|SCENE\b|"
    r"LETTER\b|EPISTLE\b|SECTION\b|SEC\.?\b|STORY\b|TALE\b|FABLE\b|SONG\b|"
    r"STAVE\b|CARD\b|DISCOURSE\b|CHAPTER THE\b|BOOK THE\b|PART THE\b"
)
# Heading that is a bare ordinal: "BOOK FIRST", "PART SECOND", "CHAPTER FIRST"
_ORD = rf"(?:{_ORDINALS})"

HEADING_RE = re.compile(
    rf"^(?:{_HEAD_TOKEN})\s*(?:THE\s+)?(?:(?:{ROMAN})|\d{{1,3}}|{_ORD})\b"
    r"(?:\s*[:.\-\u2014\u2013]?\s*.{0,60})?$",
    re.I,
)
# "CHAPTER THE FIRST", "BOOK FIRST", "PART SECOND" (no number, pure ordinal)
HEADING_ORD_RE = re.compile(
    rf"^(?:{_HEAD_TOKEN})\s+(?:THE\s+)?{_ORD}\s*$", re.I,
)
# All-caps title-only headings we can't safely attribute — leave as body text.


def _extract_body(text):
    """Cut the Gutenberg boilerplate header/footer out of the raw text."""
    m = START_RE.search(text)
    if m:
        body = text[m.end():]
    else:
        # older header: 'Project Gutenberg's ... ' + a few lines
        m = re.search(r"Project Gutenberg['\u2019]s .*", text)
        body = text[m.end():] if m else text

    m = END_RE.search(body)
    if m:
        body = body[:m.start()]
    else:
        # strip the trailing license / 'End of Project Gutenberg' footer
        body = re.split(r"(?m)^End of (?:the |this )?Project Gutenberg", body)[0]
    return body


def _split_paragraphs(lines):
    """Blank-line separated paragraphs; wrapped lines are joined."""
    paras, cur = [], []
    for ln in lines:
        s = ln.strip()
        if not s:
            if cur:
                paras.append(" ".join(cur))
                cur = []
            continue
        cur.append(s)
    if cur:
        paras.append(" ".join(cur))
    return paras


def _is_heading(line):
    s = line.strip().rstrip(".")
    if not s or len(s) > 100:
        return False
    return bool(HEADING_RE.match(s) or HEADING_ORD_RE.match(s))


def _next_nonblank(lines, idx, max_skip=5):
    """Index of the next non-blank line within max_skip lines, or None."""
    for k in range(1, max_skip + 1):
        j = idx + k
        if j >= len(lines):
            return None
        if lines[j].strip():
            return j
    return None


def _toc_entry(lines, idx):
    """Heading lines that are followed (within a few lines) by another heading
    line are Table-of-Contents entries — real body headings are followed by body
    paragraphs. Wrapped TOC entries ("CHAPTER 56. Of the ..." \n "Pictures of
    Whaling Scenes." \n "CHAPTER 57. ...") are caught by tolerating short
    continuation lines (< 40 chars) between headings; a long line (> 40 chars)
    means this is a real chapter heading."""
    for k in range(1, 11):
        j = idx + k
        if j >= len(lines):
            return False
        s = lines[j].strip()
        if not s:
            continue
        if _is_heading(lines[j]):
            return True
        if len(s) > 40:
            return False
    return False


_CONTENTS_RE = re.compile(r"^\s*(?:TABLE OF )?CONTENTS\s*$", re.I)

_ROMAN_VAL = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}
_ORD_VAL = {w: i for i, w in enumerate(
    ["FIRST", "SECOND", "THIRD", "FOURTH", "FIFTH", "SIXTH", "SEVENTH", "EIGHTH",
     "NINTH", "TENTH", "ELEVENTH", "TWELFTH", "THIRTEENTH", "FOURTEENTH", "FIFTEENTH",
     "SIXTEENTH", "SEVENTEENTH", "EIGHTEENTH", "NINETEENTH", "TWENTIETH"], 1)}


def _roman_to_int(s):
    """Standard Roman -> int: a digit smaller than the NEXT one is subtracted
    (IV=4, IX=9, XLVII=47)."""
    chars = s.upper()
    total = 0
    for i, ch in enumerate(chars):
        v = _ROMAN_VAL.get(ch, 0)
        nxt = _ROMAN_VAL.get(chars[i + 1], 0) if i + 1 < len(chars) else 0
        total += -v if v < nxt else v
    return total


def _heading_number(title):
    """Extract a chapter number (arabic/roman/ordinal) or None."""
    s = (title or "").upper()
    m = re.search(r"\d+", s)
    if m:
        return int(m.group(0))
    m = re.search(r"\b([IVXLCDM]+)\b", s)
    if m:
        r = m.group(1)
        if all(c in _ROMAN_VAL for c in r):
            return _roman_to_int(r)
    m = re.search(r"\b([A-Z]{2,})\b", s)
    if m and m.group(1) in _ORD_VAL:
        return _ORD_VAL[m.group(1)]
    return None


def _find_body_start(lines):
    """Index where the real book starts after a CONTENTS listing (or 0).

    Primary signal: TOC chapter numbers are monotonic (1..N); the body restarts
    at the first heading whose number is SMALLER than the previous heading's
    number ("CHAPTER I." real heading right after the TOC ended at XII). This
    handles split chapter titles ("CHAPTER I." / "Down the Rabbit-Hole").
    Fallback: the first long prose line after the CONTENTS marker (a real
    heading sitting just before it is kept).
    """
    limit = min(len(lines), 1500)
    cidx = next((i for i in range(limit) if _CONTENTS_RE.match(lines[i])), None)
    if cidx is None:
        return 0
    last_num = None
    for i in range(cidx + 1, min(len(lines), cidx + 2500)):
        s = lines[i].strip()
        if not s:
            continue
        if _is_heading(lines[i]):
            num = _heading_number(s)
            if num is not None:
                if last_num is not None and num < last_num:
                    return i  # numbering reset -> the real book begins here
                last_num = num
            continue
        if len(s) > 60:
            j = i - 1
            while j >= 0 and not lines[j].strip():
                j -= 1
            if j >= 0 and _is_heading(lines[j]):
                return j
            return i  # real prose begins here
    return cidx + 1


def _starts_sentence(p):
    """True if p looks like the start of a new sentence/paragraph."""
    for ch in p:
        if ch.isalpha():
            return ch.isupper()
        if ch.isdigit():
            return True
        if ch in "\u201c\u2018\u00ab[(":
            continue
        return True
    return False


def _merge_wrapped(paras):
    """Join paragraphs that are actually wrapped lines (files where a blank
    line separates EVERY physical line, e.g. illustrated editions)."""
    out = []
    for p in paras:
        if not p:
            continue
        if out and not _starts_sentence(p):
            out[-1] = out[-1] + " " + p
        else:
            out.append(p)
    return out


def _drop_captions(paras):
    """Drop '[Illustration: ...]' caption paragraphs (text-only books)."""
    return [p for p in paras
            if not re.match(r"^\s*\[?\s*Illustration\b", p, re.I)
            and p.strip(" []\u2014\u2013") not in ("", "Illustration")]


def parse_book(text, title="", author=""):
    """Parse raw Gutenberg text -> structured book dict (never raises)."""
    body = _extract_body(text)
    lines = body.splitlines()

    # 1) drop the leading metadata block / PG banner
    i = 0
    while i < len(lines):
        s = lines[i].strip()
        if not s:
            i += 1
            continue
        if META_RE.match(s) or PG_HEADER_RE.match(s):
            i += 1
            continue
        break
    lines = lines[i:]

    # 1b) wholesale Table-of-Contents elimination: when a CONTENTS listing
    # exists, the real book starts at the first long prose line after it.
    # TOC entries are heading-like lines or short continuation lines
    # ("Pictures of Whaling Scenes."), real prose is long (> 60 chars).
    bs = _find_body_start(lines)
    if bs:
        lines = lines[bs:]

    # 2) walk lines, cutting chapters at heading lines.
    #
    # Real-vs-TOC rule: a heading is REAL if the next line is blank AND the line
    # after that is NOT another heading (i.e. not a Table-of-Contents listing).
    # TOC entries ("CHAPTER 1. Loomings." \n "CHAPTER 2. ...") are skipped, which
    # strips the front CONTENTS listing for free.
    chapters, front_paras = [], []
    cur_title, cur_paras = None, []
    para = []

    def flush_paragraph():
        nonlocal para
        if para:
            cur_paras.append(" ".join(para))
            para = []

    def flush_chapter():
        nonlocal cur_title, cur_paras
        if cur_title is not None:
            chapters.append({"title": cur_title, "paragraphs": cur_paras})
        elif cur_paras:
            front_paras.extend(cur_paras)
        cur_title, cur_paras = None, []

    n = len(lines)
    for idx, ln in enumerate(lines):
        s = ln.strip()
        next_blank = idx + 1 >= n or not lines[idx + 1].strip()
        if _is_heading(ln):
            if next_blank and not _toc_entry(lines, idx):
                flush_paragraph()
                flush_chapter()
                cur_title = re.sub(r"\s+", " ", s).rstrip(".").strip("[]")
            # else: TOC entry — skip the line entirely
            continue
        if not s:
            flush_paragraph()
            continue
        para.append(s)
    flush_paragraph()
    flush_chapter()

    # 3) clean up chapters: merge wrapped lines, drop illustration captions,
    # drop empty chapters.
    def clean(paras):
        return _drop_captions(_merge_wrapped([p for p in paras if p.strip()]))

    front_paras = clean(front_paras)
    for c in chapters:
        c["paragraphs"] = clean(c["paragraphs"])
    chapters = [c for c in chapters if c["paragraphs"]]

    # 4) drop a trailing "THE END" paragraph if it exists
    if chapters:
        last = chapters[-1]
        if last["paragraphs"] and re.match(r"^(THE END|FINIS|END)$", last["paragraphs"][-1], re.I):
            last["paragraphs"] = last["paragraphs"][:-1]

    # 5) sanity: drop paragraph fragments and title/author repeats, and only
    # keep short front matter (dedications). Illustrated editions ship a huge
    # front block (publisher pages, prefaces) — that is discarded; the PDF has
    # its own title page + contents.
    chapters = [c for c in chapters if c["paragraphs"]]
    front_paras = [p for p in front_paras if len(p) > 1]
    t_norm, a_norm = (title or "").strip().lower(), (author or "").strip().lower()
    front_paras = [p for p in front_paras if p.strip().lower() not in (t_norm, a_norm)]
    if len(front_paras) > 6 or sum(len(p.split()) for p in front_paras) > 120:
        front_paras = []

    if not chapters:
        chapters = [{"title": title or "Contents", "paragraphs": front_paras or ["(no readable text)"]}]
        front_paras = []

    word_count = sum(len(p.split()) for c in chapters for p in c["paragraphs"])
    return {
        "title": title,
        "author": author,
        "front": front_paras,
        "chapters": chapters,
        "word_count": word_count,
    }


if __name__ == "__main__":
    # self-test against a couple of well-known books
    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from gutendex import get_book, download_text, author_name

    cache = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cache")
    for gid in (1342, 2701):
        b = get_book(gid)
        txt = download_text(b, cache)
        book = parse_book(txt, b["title"], author_name(b))
        print("=" * 70)
        print(f"#{gid} {book['title']} by {book['author']}  words={book['word_count']}")
        print(f"  front paragraphs: {len(book['front'])}  chapters: {len(book['chapters'])}")
        for c in book["chapters"][:12]:
            print(f"    - {c['title']!r} ({len(c['paragraphs'])} paras)")
