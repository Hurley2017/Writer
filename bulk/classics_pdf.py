"""Render a parsed public-domain book into the 'Second Light of March' layout.

Architecture is the VERIFIED one from src/pdfbuilder.py (two-pass build):
  - A5 (419.53 x 595.28 pt), side margins 31.2 pt, Palatino 9.5pt/15 justified
  - Page 1: cover (full-bleed image)
  - Page 2: Contents (drawn on the canvas from pass-1 page numbers)
  - Chapter first page: italic 9pt centered title near top, body starts y=68.6
  - Continuation pages: italic 7pt centered running header, body starts y=48.8
  - Footer: italic 7pt centered page number = pageIndex - 2
  - A single "body" template is used for all chapter pages; the onPage handler
    decides first-page-title vs running-header via doc.last_chapter != current.
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_PROJ = os.path.dirname(_HERE)
if _PROJ not in sys.path:
    sys.path.insert(0, _PROJ)

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    NextPageTemplate,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
)

from src.pdfbuilder import (
    register_fonts,
    _SetChapter,
    _PageMarker,
    FONT,
    FONT_I,
    FONT_B,
    PAGE_W,
    PAGE_H,
    MARGIN,
    CONTENT_W,
    BODY_TOP,
    BODY_BOTTOM,
    FIRST_PAGE_EXTRA_TOP,
)

BOTTOM = lambda top_y: PAGE_H - top_y  # noqa: E731

_BODY = ParagraphStyle(
    "classic_body", fontName=FONT, fontSize=9.5, leading=15, alignment=TA_JUSTIFY,
    spaceBefore=0, spaceAfter=11, textColor=colors.black,
)
_FRONT = ParagraphStyle(
    "classic_front", fontName=FONT_I, fontSize=9.5, leading=15, alignment=TA_CENTER,
    spaceBefore=0, spaceAfter=11, textColor=colors.black,
)


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
        canv.drawImage(img, 0, 0, width=PAGE_W, height=PAGE_H,
                       preserveAspectRatio=False, mask="auto")


def _draw_contents(canv, doc):
    _draw_footer(canv, doc)
    canv.saveState()
    canv.setFont(FONT_B, 16)
    canv.drawCentredString(PAGE_W / 2, BOTTOM(49), "Contents")
    y = BOTTOM(91.6)
    for entry in getattr(doc, "contents_entries", []) or []:
        text, page_no = entry
        y -= 18.5
        canv.setFont(FONT, 9.5)
        canv.drawString(MARGIN + 12, y, text)
        if page_no is not None:
            canv.drawRightString(PAGE_W - MARGIN, y, str(page_no))
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

class _ClassicDoc(BaseDocTemplate):
    def __init__(self, filename, **kw):
        kw.setdefault("pagesize", (PAGE_W, PAGE_H))
        kw.setdefault("leftMargin", MARGIN)
        kw.setdefault("rightMargin", MARGIN)
        kw.setdefault("topMargin", 0)
        kw.setdefault("bottomMargin", 0)
        super().__init__(filename, **kw)
        self.page_of = {}
        self.current_chapter = None
        self.last_chapter = None
        self.contents_entries = []
        self.cover_image = None

        body_frame = Frame(
            MARGIN, BOTTOM(BODY_BOTTOM), CONTENT_W,
            BOTTOM(BODY_TOP) - BOTTOM(BODY_BOTTOM),
            leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0,
        )
        full_frame = Frame(0, 0, PAGE_W, PAGE_H, leftPadding=0, rightPadding=0,
                           topPadding=0, bottomPadding=0)
        self.addPageTemplates([
            PageTemplate(id="cover", frames=[full_frame], onPage=_draw_cover),
            PageTemplate(id="contents", frames=[full_frame], onPage=_draw_contents),
            PageTemplate(id="body", frames=[body_frame], onPage=_draw_body),
        ])


def _clean_text(s):
    import xml.sax.saxutils as sax
    return sax.escape(s or "", {'"': "&quot;"})


def _make_contents_entries(chapters, page_numbers):
    entries = []
    for i, ch in enumerate(chapters):
        title = ch.get("title") or f"Chapter {i + 1}"
        num = page_numbers.get(f"chapter_{i}") if page_numbers else None
        entries.append((_clean_text(title), max(num - 2, 0) if num is not None else None))
    return entries


def _assemble(chapters, front, cover_path, out_path, page_numbers,
              use_numbers=False, numbers=None):
    doc = _ClassicDoc(out_path)
    doc.page_of = page_numbers
    doc.cover_image = cover_path
    doc.contents_entries = _make_contents_entries(chapters, numbers if use_numbers else None)

    flow = []

    # ---- cover (page 1) ----
    flow.append(Spacer(1, 1))
    flow.append(NextPageTemplate("contents"))
    flow.append(PageBreak())

    # ---- contents (page 2) ----
    flow.append(Spacer(1, 1))

    # ---- front matter (dedication, optional) ----
    if front:
        flow.append(NextPageTemplate("body"))
        flow.append(PageBreak())
        flow.append(Spacer(0, FIRST_PAGE_EXTRA_TOP + 40))
        for p in front:
            flow.append(Paragraph(_clean_text(p), _FRONT))

    # ---- chapters ----
    for i, ch in enumerate(chapters):
        ctitle = ch.get("title") or f"Chapter {i + 1}"
        flow.append(_SetChapter(ctitle))
        flow.append(NextPageTemplate("body"))
        flow.append(PageBreak())
        flow.append(_PageMarker(f"chapter_{i}"))
        flow.append(Spacer(0, FIRST_PAGE_EXTRA_TOP))
        for p in ch.get("paragraphs", []):
            if p and p.strip():
                flow.append(Paragraph(_clean_text(p), _BODY))

    doc.build(flow)


def build_classic_pdf(book, cover_path, out_path, max_chapters=0, toc=True):
    """Build the A5 PDF for a parsed book dict. Returns out_path."""
    register_fonts()
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)

    chapters = book.get("chapters", [])
    if max_chapters and len(chapters) > max_chapters:
        chapters = chapters[:max_chapters]
    front = book.get("front", []) or []

    # pass 1: collect page numbers; pass 2: render contents with numbers
    page_numbers = {}
    _assemble(chapters, front, cover_path, out_path, page_numbers,
              use_numbers=False, numbers=None)
    _assemble(chapters, front, cover_path, out_path, page_numbers,
              use_numbers=True, numbers=page_numbers)
    return out_path


if __name__ == "__main__":
    # self-test: parse Pride and Prejudice and build the A5 PDF
    from bulk.gutendex import get_book, download_text, author_name
    from bulk.gutenberg_text import parse_book
    from bulk.cover import classic_cover

    b = get_book(1342)
    txt = download_text(b, os.path.join(_HERE, "cache"))
    book = parse_book(txt, b["title"], author_name(b))
    out = os.path.join(_HERE, "cache", "pride-and-prejudice.pdf")
    cover = os.path.join(_HERE, "cache", "covers", "pnp.png")
    classic_cover(book["title"], book["author"], cover)
    build_classic_pdf(book, cover, out)
    print("PDF written:", out, os.path.getsize(out), "bytes")
