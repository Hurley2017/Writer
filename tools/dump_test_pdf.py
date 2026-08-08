"""Dump spans of the generated test PDF pages to debug layout."""
import pymupdf as fitz

PDF = r"d:\Writer\output\test-layout\test-layout.pdf"
doc = fitz.open(PDF)
for pno in range(0, min(9, doc.page_count)):
    page = doc[pno]
    d = page.get_text("dict")
    print(f"\n===== PAGE {pno+1} =====")
    for b in d["blocks"]:
        if b["type"] != 0:
            continue
        for l in b["lines"]:
            y = round(l["bbox"][1], 1)
            x0 = round(l["bbox"][0], 1)
            x1 = round(l["bbox"][2], 1)
            parts = []
            for s in l["spans"]:
                parts.append(f"[{s['font']} {s['size']:.1f}] {s['text'][:45]!r}")
            print(f"  y={y:6.1f} x=({x0:5.1f}-{x1:5.1f}) " + " ".join(parts)[:130])
