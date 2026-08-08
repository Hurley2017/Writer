"""Extract precise layout (margins, alignment) and render key pages to PNG."""
import pymupdf as fitz

PDF = r"d:\Writer\Second Light of March.pdf"
OUT = r"d:\Writer\tools\preview"

doc = fitz.open(PDF)
PAGES = [0, 1, 2, 4, 5, 6, 46]  # cover, contents, prologue, section1, chapter1, chapter1p2, back cover

for pno in PAGES:
    page = doc[pno]
    d = page.get_text("dict")
    print(f"\n===== PAGE {pno+1} ({page.rect.width:.0f}x{page.rect.height:.0f}) =====")
    for block in d["blocks"]:
        if block["type"] != 0:
            continue
        bbox = block["bbox"]
        x0, y0, x1, y1 = bbox
        txt = " ".join(span["text"] for line in block["lines"] for span in line["spans"])
        txt = txt[:70].replace("\n", " ")
        # alignment estimate: compare x0 to left margin, x1 to right margin
        print(f"  bbox=({x0:.1f},{y0:.1f})-({x1:.1f},{y1:.1f}) | x0={x0:.1f} x1={x1:.1f} | {txt!r}")
    # render
    pix = page.get_pixmap(dpi=110)
    pix.save(f"{OUT}\\page_{pno+1:02d}.png")

print("\nSaved previews to", OUT)
