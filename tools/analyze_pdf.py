"""Analyze the sample PDF to capture its exact format for replication."""
import sys
import pymupdf as fitz  # PyMuPDF

PDF = r"d:\Writer\Second Light of March.pdf"


def color_str(c):
    if isinstance(c, (int, float)):
        return f"gray({c})"
    return str(tuple(round(x, 2) for x in c))


def main():
    doc = fitz.open(PDF)
    print(f"=== PDF: {PDF} ===")
    print(f"Pages: {doc.page_count}")
    p0 = doc[0]
    print(f"Page size (pt): {p0.rect.width} x {p0.rect.height}  (A4 = 595.28 x 841.89, Letter = 612 x 792)")
    print(f"Metadata: {doc.metadata}")

    fonts = set()
    for page in doc:
        d = page.get_text("dict")
        for block in d["blocks"]:
            if block["type"] != 0:
                continue
            for line in block["lines"]:
                for span in line["spans"]:
                    fonts.add((span["font"], round(span["size"], 1), color_str(span["color"])))

    print("\n=== Fonts used (font, size, color) ===")
    for f in sorted(fonts):
        print(" ", f)

    print("\n=== Page-by-page summary ===")
    for i, page in enumerate(doc):
        d = page.get_text("dict")
        n_imgs = len(page.get_images(full=True))
        # image placement rects
        img_rects = []
        for img in page.get_images(full=True):
            try:
                rects = page.get_image_rects(img[0])
                img_rects.extend((str(r), round(r.width, 1), round(r.height, 1)) for r in rects)
            except Exception:
                pass
        text = page.get_text().strip()
        first_line = text.splitlines()[0] if text else "(no text)"
        print(f"\n--- Page {i+1} | images: {n_imgs} | img rects: {img_rects}")
        print(f"    first line: {first_line[:90]!r}")
        # font sizes on this page
        sizes = set()
        for block in d["blocks"]:
            if block["type"] != 0:
                continue
            for line in block["lines"]:
                for span in line["spans"]:
                    sizes.add(round(span["size"], 1))
        print(f"    font sizes: {sorted(sizes)}")

    # Dump full text of first 2 pages and the page with the first image
    print("\n=== TEXT PAGE 1 (first 1500 chars) ===")
    print(doc[0].get_text()[:1500])


if __name__ == "__main__":
    main()
