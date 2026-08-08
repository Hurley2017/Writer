"""Dump span-level font details for title/header lines on key pages."""
import pymupdf as fitz

PDF = r"d:\Writer\Second Light of March.pdf"
doc = fitz.open(PDF)

# pages: 2 contents, 3 prologue, 5 section, 6 chapter start, 7 continuation
for pno in [1, 2, 4, 5, 6]:
    page = doc[pno]
    d = page.get_text("dict")
    print(f"\n===== PAGE {pno+1} =====")
    for block in d["blocks"]:
        if block["type"] != 0:
            continue
        for line in block["lines"]:
            y0 = line["bbox"][1]
            for span in line["spans"]:
                t = span["text"].strip()
                if not t:
                    continue
                print(f"  y={y0:6.1f} size={span['size']:5.2f} font={span['font']:<28} flags={span['flags']} | {t[:60]!r}")
