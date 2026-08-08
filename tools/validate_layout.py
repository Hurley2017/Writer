"""Compare the generated test PDF's layout against the sample book's spec."""
import pymupdf as fitz

PDF = r"d:\Writer\output\test-layout\test-layout.pdf"
SAMPLE = r"d:\Writer\Second Light of March.pdf"

doc = fitz.open(PDF)
print(f"Pages: {doc.page_count}")
p0 = doc[0]
print(f"Page size: {p0.rect.width:.1f} x {p0.rect.height:.1f} (A5 = 419.5 x 595.3)")

def spans(page):
    out = []
    d = page.get_text("dict")
    for b in d["blocks"]:
        if b["type"] != 0:
            continue
        for l in b["lines"]:
            for s in l["spans"]:
                t = s["text"].strip()
                if t:
                    out.append((s["font"], round(s["size"], 1), round(l["bbox"][1], 1),
                                round(l["bbox"][0], 1), round(l["bbox"][2], 1), t))
    return out

def heading(page):
    for f, sz, y, x0, x1, t in spans(page):
        if y < 50 and "Italic" in f:
            return f, sz, y, t[:60]
    return None

print("\n--- structural check ---")
for i in range(doc.page_count):
    page = doc[i]
    imgs = page.get_images(full=True)
    h = heading(page)
    foot = [t for f, sz, y, x0, x1, t in spans(page) if sz == 7.0 and y > 555]
    body_first = [t for f, sz, y, x0, x1, t in spans(page) if sz == 9.5 and y < 80 and "Italic" not in f]
    info = []
    if h:
        info.append(f"header=({h[0]},{h[1]}pt,y{h[2]}){h[3]!r}")
    if foot:
        info.append(f"footer={foot}")
    if imgs:
        info.append(f"imgs={len(imgs)}")
    if body_first:
        info.append(f"body_start_y={body_first[0][2] if False else ''}")
    print(f"p{i+1:>2}: {' | '.join(info) if info else '(no text)'}")

print("\n--- first body line y positions (should be ~68.6 first-page, ~48.8 continuation) ---")
for i in range(doc.page_count):
    page = doc[i]
    d = page.get_text("dict")
    ys = []
    for b in d["blocks"]:
        if b["type"] != 0:
            continue
        for l in b["lines"]:
            for s in l["spans"]:
                if s["size"] == 9.5 and "Italic" not in s["font"] and l["bbox"][1] < 200:
                    ys.append(round(l["bbox"][1], 1))
                    break
            if ys:
                break
        if ys:
            break
    if ys:
        print(f"  page {i+1}: first body line y = {ys[0]}")
