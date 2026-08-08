"""Measure how reportlab positions the first text line vs the frame top (for calibration)."""
import os
import pymupdf as fitz
from reportlab.lib.pagesizes import A5
from reportlab.lib.enums import TA_JUSTIFY
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import BaseDocTemplate, PageTemplate, Frame, Paragraph

PAGE_W, PAGE_H = A5
pdfmetrics.registerFont(TTFont("Palatino", r"C:\Windows\Fonts\pala.ttf"))
OUT = r"d:\Writer\tools\calib.pdf"


def measure(frame_top_from_top):
    class Doc(BaseDocTemplate):
        pass

    doc = Doc(OUT, pagesize=A5)
    top = PAGE_H - frame_top_from_top
    frame = Frame(31.2, 60.28, 357.13, top - 60.28, leftPadding=0, rightPadding=0,
                  topPadding=0, bottomPadding=0)
    doc.addPageTemplates([PageTemplate(id="x", frames=[frame])])
    style = ParagraphStyle("body", fontName="Palatino", fontSize=9.5, leading=15,
                           alignment=TA_JUSTIFY, spaceBefore=0, spaceAfter=0)
    doc.build([Paragraph("The quick brown fox jumps over the lazy dog. " * 4, style)])
    d = fitz.open(OUT)
    line = d[0].get_text("dict")["blocks"][0]["lines"][0]
    first_top = line["bbox"][1]
    d.close()
    print(f"frame_top_from_top={frame_top_from_top:6.2f} -> first line bbox top={first_top:6.2f} "
          f"(offset {first_top - frame_top_from_top:+.2f})")
    return first_top - frame_top_from_top


if __name__ == "__main__":
    for t in (48.8, 40.0, 30.0):
        measure(t)
