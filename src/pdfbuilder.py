"""Render a story into a PDF that replicates the layout of 'Second Light of March.pdf'.

Layout spec captured from the sample:
  - A5 portrait (419.53 x 595.28 pt), side margins 31.2 pt
  - Body: Palatino 9.5pt, justified, leading 15, ~11pt paragraph gap
  - Chapter/Prologue/Epilogue first page: italic 9pt centered title near top,
    body starts at y=68.6
  - Continuation pages: italic 7pt centered running header, body starts at y=48.8
  - Section title pages: bold 20pt centered title + italic 9.5pt centered chapter list
  - Contents page: bold 16pt 'Contents', bold 10pt section entries,
    9.5pt indented chapter entries with right-aligned page numbers
  - Footer: italic 7pt centered page number = pageIndex - 2 (cover has none)
  - Cover / back cover: full-bleed images
"""
import os
import xml.sax.saxutils as sax

from reportlab.lib import colors
from reportlab.lib.enums import TA_JUSTIFY
from reportlab.lib.pagesizes import A5
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    Image as RLImage,
    KeepTogether,
    NextPageTemplate,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Flowable,
)

PAGE_W, PAGE_H = A5  # 419.528, 595.276

FONT = "Palatino"
FONT_B = "Palatino-Bold"
FONT_I = "Palatino-Italic"
FONT_BI = "Palatino-BoldItalic"

FONT_FILES = {
    FONT: r"C:\Windows\Fonts\pala.ttf",
    FONT_B: r"C:\Windows\Fonts\palab.ttf",
    FONT_I: r"C:\Windows\Fonts\palai.ttf",
    FONT_BI: r"C:\Windows\Fonts\palabi.ttf",
}

MARGIN = 31.2
CONTENT_W = PAGE_W - 2 * MARGIN            # 357.13
BODY_TOP = 46.25                           # frame top, from page top (reportlab drops the
                                           # first line 2.55pt below the frame top, so this
                                           # makes text start at y=48.8 like the sample)
BODY_BOTTOM = 535.0                        # body frame bottom, from page top
FIRST_PAGE_EXTRA_TOP = 19.8                # pushes body start to y=68.6 on chapter first pages

# y positions converted to bottom-origin canvas coordinates
BOTTOM = lambda top_y: PAGE_H - top_y     # noqa: E731

_fonts_registered = False


def register_fonts():
    global _fonts_registered
    if _fonts_registered:
        return
    for name, path in FONT_FILES.items():
        if os.path.exists(path):
            pdfmetrics.registerFont(TTFont(name, path))
        else:
            raise RuntimeError(f"Font file not found: {path} (needed for the book layout)")
    _fonts_registered = True


class _StateFlowable(Flowable):
    """Base for invisible flowables; always fits, updates doc state at draw time."""
    _ZEROSIZE = True

    def _doc(self):
        return getattr(self.canv, "_doctemplate", None)


class _SetChapter(_StateFlowable):
    """Draws nothing; sets the current chapter title (used by body onPage)."""

    def __init__(self, title):
        super().__init__()
        self.title = title
        self.width = 0
        self.height = 0

    def draw(self):
        doc = self._doc()
        if doc is not None:
            doc.current_chapter = self.title


class _SetSection(_StateFlowable):
    """Draws nothing; sets the current section page data."""

    def __init__(self, title, chapters):
        super().__init__()
        self.title = title
        self.chapters = chapters
        self.width = 0
        self.height = 0

    def draw(self):
        doc = self._doc()
        if doc is not None:
            doc.section_data = {"title": self.title, "chapters": self.chapters}


class _PageMarker(_StateFlowable):
    """Records the page number where it is drawn (for the contents table)."""

    def __init__(self, key):
        super().__init__()
        self.key = key
        self.width = 0
        self.height = 0

    def draw(self):
        doc = self._doc()
        if doc is not None and hasattr(doc, "page_of"):
            doc.page_of[self.key] = self.canv.getPageNumber()


# ---------------------------------------------------------------- onPage hooks

def _draw_footer(canv, doc):
    pn = canv.getPageNumber()
    if pn < 2:
        return
    canv.saveState()
    canv.setFont(FONT_I, 7)
    canv.setFillColor(colors.black)
    canv.drawCentredString(PAGE_W / 2, BOTTOM(566.4), str(pn - 2))
    canv.restoreState()


def _draw_cover(canv, doc):
    img = getattr(doc, "cover_image", None)
    if img and os.path.exists(img):
        canv.drawImage(img, 0, 0, width=PAGE_W, height=PAGE_H, preserveAspectRatio=False, mask="auto")


def _draw_back(canv, doc):
    _draw_footer(canv, doc)
    img = getattr(doc, "back_image", None)
    if img and os.path.exists(img):
        canv.drawImage(img, 0, 0, width=PAGE_W, height=PAGE_H, preserveAspectRatio=False, mask="auto")


def _draw_contents(canv, doc):
    _draw_footer(canv, doc)
    canv.saveState()
    canv.setFont(FONT_B, 16)
    canv.drawCentredString(PAGE_W / 2, BOTTOM(49), "Contents")
    y = BOTTOM(91.6)  # bottom-origin cursor
    for kind, text, page_no in getattr(doc, "contents_entries", []) or []:
        if kind == "section":
            y -= 24
            canv.setFont(FONT_B, 10)
        else:
            y -= 18.5
            canv.setFont(FONT, 9.5)
        if kind == "chapter":
            canv.drawString(MARGIN + 12, y, text)
        else:
            canv.drawString(MARGIN, y, text)
        if page_no is not None and page_no != "":
            canv.setFont(FONT, 9.5)
            canv.drawRightString(PAGE_W - MARGIN, y, str(page_no))
    canv.restoreState()


def _draw_section(canv, doc):
    _draw_footer(canv, doc)
    canv.saveState()
    sd = getattr(doc, "section_data", None)
    if sd:
        canv.setFont(FONT_B, 20)
        canv.drawCentredString(PAGE_W / 2, BOTTOM(136.8), sd["title"])
        canv.setFont(FONT_I, 9.5)
        y = BOTTOM(211.3)
        for ch in sd["chapters"]:
            canv.drawCentredString(PAGE_W / 2, y, ch)
            y -= 20
    canv.restoreState()


def _draw_body(canv, doc):
    _draw_footer(canv, doc)
    ch = getattr(doc, "current_chapter", None)
    if not ch:
        return
    canv.saveState()
    if getattr(doc, "last_chapter", None) != ch:
        canv.setFont(FONT_I, 9)
        canv.drawCentredString(PAGE_W / 2, BOTTOM(40), ch)
        doc.last_chapter = ch
    else:
        canv.setFont(FONT_I, 7)
        canv.drawCentredString(PAGE_W / 2, BOTTOM(37.6), ch)
    canv.restoreState()


# ---------------------------------------------------------------- doc template

class _StoryDoc(BaseDocTemplate):
    def __init__(self, filename, **kw):
        kw.setdefault("pagesize", A5)
        kw.setdefault("leftMargin", MARGIN)
        kw.setdefault("rightMargin", MARGIN)
        kw.setdefault("topMargin", 0)
        kw.setdefault("bottomMargin", 0)
        super().__init__(filename, **kw)
        self.page_of = {}
        self.current_chapter = None
        self.last_chapter = None
        self.contents_entries = []
        self.section_data = None
        self.cover_image = None
        self.back_image = None

        body_frame = Frame(
            MARGIN,
            BOTTOM(BODY_BOTTOM),
            CONTENT_W,
            BOTTOM(BODY_TOP) - BOTTOM(BODY_BOTTOM),
            leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0,
        )
        full_frame = Frame(0, 0, PAGE_W, PAGE_H, leftPadding=0, rightPadding=0,
                           topPadding=0, bottomPadding=0)

        self.addPageTemplates([
            PageTemplate(id="cover", frames=[full_frame], onPage=_draw_cover),
            PageTemplate(id="contents", frames=[full_frame], onPage=_draw_contents),
            PageTemplate(id="section", frames=[full_frame], onPage=_draw_section),
            PageTemplate(id="body", frames=[body_frame], onPage=_draw_body),
            PageTemplate(id="back", frames=[full_frame], onPage=_draw_back),
        ])


# ---------------------------------------------------------------- helpers

def _sized_image(path, max_w, max_h):
    from PIL import Image as PILImage
    with PILImage.open(path) as im:
        w, h = im.size
    scale = min(max_w / w, max_h / h, 1.0)
    rl = RLImage(path, width=w * scale, height=h * scale)
    rl.hAlign = "CENTER"
    return rl


def _para(text, style):
    return Paragraph(sax.escape(text), style)


def _add_chapter_body(flow, doc, chapter, images, prefix, opts):
    paras = chapter.get("paragraphs") or []
    prompts = chapter.get("image_prompts") or []
    style = ParagraphStyle(
        "body", fontName=FONT, fontSize=9.5, leading=15,
        alignment=TA_JUSTIFY, spaceBefore=0, spaceAfter=11,
    )
    n = len(paras)
    interval = max(1, opts.get("image_interval", 1))
    after_last = opts.get("images_after_last", False)
    for i, p in enumerate(paras):
        flow.append(_para(p, style))
        is_last = i == n - 1
        if after_last or not is_last:
            if (i + 1) % interval == 0:
                img_path = images.get(f"{prefix}_p{i}")
                if img_path and os.path.exists(img_path):
                    flow.append(Spacer(0, 4))
                    flow.append(KeepTogether(_sized_image(
                        img_path, opts.get("image_max_width", 300),
                        opts.get("image_max_height", 340))))
                    flow.append(Spacer(0, 4))


def _make_contents_entries(story, page_numbers):
    entries = []
    if story.get("prologue"):
        num = page_numbers.get("prologue") if page_numbers else None
        entries.append(("prologue", f"Prologue : {story['prologue']['title']}", _disp(num)))
    ch = 0
    for si, sec in enumerate(story.get("sections", [])):
        entries.append(("section", f"Section {si + 1} - {sec['title']}", None))
        for c in sec.get("chapters", []):
            ch += 1
            num = page_numbers.get(f"chapter_{si}_{ch}") if page_numbers else None
            entries.append(("chapter", f"Chapter {ch} : {c['title']}", _disp(num)))
    if story.get("epilogue"):
        num = page_numbers.get("epilogue") if page_numbers else None
        entries.append(("epilogue", f"Epilogue : {story['epilogue']['title']}", _disp(num)))
    return entries


def _disp(page_number):
    """Printed page number: pageIndex - 2 (sample numbers its pages this way)."""
    if page_number is None:
        return None
    return max(page_number - 2, 0)


# ---------------------------------------------------------------- build

def build_pdf(story, images, out_path, opts=None):
    """Build the PDF (two passes: first finds page numbers, second fills contents)."""
    register_fonts()
    opts = opts or {}

    page_numbers = {}
    _assemble(story, images, out_path, page_numbers, use_numbers=False, opts=opts)

    page_numbers2 = {}
    _assemble(story, images, out_path, page_numbers2, use_numbers=True,
              numbers=page_numbers, opts=opts)
    return out_path


def _assemble(story, images, out_path, page_numbers, use_numbers=False, numbers=None, opts=None):
    opts = opts or {}
    doc = _StoryDoc(out_path)
    doc.page_of = page_numbers
    doc.cover_image = images.get("cover")
    doc.back_image = images.get("back")
    doc.contents_entries = _make_contents_entries(story, numbers if use_numbers else None)

    flow = []

    # ---- cover (page 1) ----
    flow.append(Spacer(1, 1))
    flow.append(NextPageTemplate("contents"))
    flow.append(PageBreak())

    # ---- contents (page 2) ----
    flow.append(Spacer(1, 1))

    ch_num = 0
    section_titles = []  # (section_index, display title, chapter display titles)

    # ---- prologue ----
    if story.get("prologue"):
        title = f"Prologue : {story['prologue']['title']}"
        flow.append(_SetChapter(title))
        flow.append(NextPageTemplate("body"))
        flow.append(PageBreak())
        flow.append(_PageMarker("prologue"))
        flow.append(Spacer(0, FIRST_PAGE_EXTRA_TOP))
        _add_chapter_body(flow, doc, story["prologue"], images, "prologue", opts)

    # ---- sections + chapters ----
    for si, sec in enumerate(story.get("sections", [])):
        sec_disp = f"Section {si + 1} - {sec['title']}"
        ch_disp = [f"Chapter {ch_num + j + 1} : {c['title']}"
                   for j, c in enumerate(sec.get("chapters", []))]
        section_titles.append((si, sec_disp, ch_disp))

        # section page
        flow.append(_SetSection(sec_disp, ch_disp))
        flow.append(NextPageTemplate("section"))
        flow.append(PageBreak())
        flow.append(_PageMarker(f"section_{si}"))
        flow.append(Spacer(1, 1))

        for c in sec.get("chapters", []):
            ch_num += 1
            title = f"Chapter {ch_num} : {c['title']}"
            flow.append(_SetChapter(title))
            flow.append(NextPageTemplate("body"))
            flow.append(PageBreak())
            flow.append(_PageMarker(f"chapter_{si}_{ch_num}"))
            flow.append(Spacer(0, FIRST_PAGE_EXTRA_TOP))
            _add_chapter_body(flow, doc, c, images, f"s{si}_c{ch_num}", opts)

    # ---- epilogue ----
    if story.get("epilogue"):
        title = f"Epilogue : {story['epilogue']['title']}"
        flow.append(_SetChapter(title))
        flow.append(NextPageTemplate("body"))
        flow.append(PageBreak())
        flow.append(_PageMarker("epilogue"))
        flow.append(Spacer(0, FIRST_PAGE_EXTRA_TOP))
        _add_chapter_body(flow, doc, story["epilogue"], images, "epilogue", opts)

    # ---- back cover ----
    flow.append(NextPageTemplate("back"))
    flow.append(PageBreak())
    flow.append(Spacer(1, 1))

    doc.build(flow)
