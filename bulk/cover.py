"""Cover art for the classic-books track.

Default: an elegant typographic cover (deep palette + serif title + ornament),
matching the site's 400x600 cover ratio at 896x1152 px. No AI needed — fast,
consistent, and era-appropriate for public-domain classics.

Optional: `--sd-covers` routes cover generation through the existing
src.imagegen pipeline (RealVisXL / diffusers) for painterly art covers.
"""
import os
import random

from PIL import Image, ImageDraw, ImageFont

PALETTES = [
    {"bg": (74, 29, 29), "accent": (212, 175, 55), "text": (245, 235, 220)},     # oxblood
    {"bg": (28, 42, 74), "accent": (201, 162, 39), "text": (240, 233, 216)},     # navy
    {"bg": (30, 58, 47), "accent": (217, 180, 91), "text": (244, 237, 222)},     # forest
    {"bg": (35, 35, 35), "accent": (201, 162, 39), "text": (240, 234, 220)},     # charcoal
    {"bg": (58, 33, 70), "accent": (217, 168, 91), "text": (243, 235, 224)},     # plum
    {"bg": (16, 28, 43), "accent": (168, 195, 217), "text": (238, 243, 248)},    # midnight
]

_FONT_DIR = r"C:\Windows\Fonts"


def _font(name, size):
    path = os.path.join(_FONT_DIR, name)
    if not os.path.exists(path):
        # fall back to any available serif
        for cand in ("georgia.ttf", "times.ttf", "cour.ttf"):
            p = os.path.join(_FONT_DIR, cand)
            if os.path.exists(p):
                return ImageFont.truetype(p, size)
        return ImageFont.load_default()
    return ImageFont.truetype(path, size)


def _wrap(draw, text, font, max_width):
    """Wrap text into lines that fit max_width (word-based)."""
    words, lines, cur = text.split(), [], ""
    for w in words:
        test = (cur + " " + w).strip()
        if draw.textlength(test, font=font) <= max_width:
            cur = test
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines or [""]


def _ornament(draw, cx, y, accent, width=260):
    """A thin rule + diamond centered at (cx, y)."""
    half = width // 2
    draw.line([(cx - half, y), (cx - 12, y)], fill=accent, width=2)
    draw.line([(cx + 12, y), (cx + half, y)], fill=accent, width=2)
    d = 7
    draw.polygon([(cx, y - d), (cx + d, y), (cx, y + d), (cx - d, y)], outline=accent)


def classic_cover(title, author, out_path, size=(896, 1152), palette=None, seed=None):
    """Generate a typographic book cover. Returns out_path."""
    rng = random.Random(seed)
    pal = palette or rng.choice(PALETTES)
    W, H = size
    bg, accent, text = pal["bg"], pal["accent"], pal["text"]

    img = Image.new("RGB", (W, H), bg)
    draw = ImageDraw.Draw(img)

    # subtle vertical gradient (darken bottom) for depth
    for y in range(H):
        t = y / H
        shade = int(40 * t)
        c = tuple(max(0, min(255, v - shade)) for v in bg)
        draw.line([(0, y), (W, y)], fill=c)

    # double frame border
    draw.rectangle([24, 24, W - 25, H - 25], outline=accent, width=2)
    draw.rectangle([36, 36, W - 37, H - 37], outline=accent, width=1)

    cx = W // 2
    brand_font = _font("pala.ttf", 30)
    title_font = _font("palab.ttf", 86)
    author_font = _font("palai.ttf", 42)
    sub_font = _font("pala.ttf", 26)

    # brand at top
    draw.text((cx, 90), "W R I T E R ' S   P A L E T T E", font=brand_font,
              fill=accent, anchor="mm")
    _ornament(draw, cx, 150, accent, width=220)

    # title in the middle band
    t_font = title_font
    max_w = W - 220
    lines = _wrap(draw, title, t_font, max_w)
    if len(lines) > 4:  # shrink if very long
        t_font = _font("palab.ttf", 64)
        lines = _wrap(draw, title, t_font, max_w)
    line_h = int(t_font.size * 1.22)
    total_h = line_h * len(lines)
    start_y = H // 2 - total_h // 2 - 40
    for i, ln in enumerate(lines):
        y = start_y + i * line_h + line_h // 2
        # soft drop shadow
        draw.text((cx + 2, y + 2), ln, font=t_font, fill=(0, 0, 0), anchor="mm")
        draw.text((cx, y), ln, font=t_font, fill=text, anchor="mm")

    # ornament under title
    _ornament(draw, cx, start_y + total_h + 70, accent, width=260)

    # author (italic, gold)
    a_font = author_font
    a_lines = _wrap(draw, author, a_font, max_w)
    if len(a_lines) > 2:
        a_font = _font("palai.ttf", 34)
        a_lines = _wrap(draw, author, a_font, max_w)
    ay = start_y + total_h + 140
    for i, ln in enumerate(a_lines):
        draw.text((cx, ay + i * int(a_font.size * 1.25)), ln, font=a_font,
                  fill=accent, anchor="mm")

    # footer: public-domain note
    draw.text((cx, H - 90), "PUBLIC DOMAIN  •  PROJECT GUTENBERG", font=sub_font,
              fill=text, anchor="mm")
    draw.text((cx, H - 56), "W R I T E R ' S   P A L E T T E", font=brand_font,
              fill=accent, anchor="mm")

    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    img.save(out_path, "PNG")
    return out_path


def sd_cover(book, cfg, out_path, seed=None):
    """Painterly AI cover via the writer pipeline's image backend (pure art,
    no text — the library card shows the title).

    `cfg` may be the bulk config (writer config nested under cfg['writer']) or
    the flat writer config; the imagegen section is resolved from either.
    """
    from src import imagegen  # noqa: imported lazily (heavy deps)
    os.environ.setdefault("HF_HOME", "D:\\hf_cache")
    os.environ.setdefault("HF_HUB_CACHE", "D:\\hf_cache\\hub")
    os.environ["HF_HUB_DISABLE_SYMLINKS"] = "1"
    wcfg = cfg.get("writer") or cfg  # bulk config nests the writer config
    backend, backend_id = imagegen.create_backend(wcfg)
    cw, ch = wcfg["imagegen"]["cover_size"]
    era = "classic 19th century" if (book.get("author") or "") else "vintage"
    prompt = (f"elegant vintage hardcover book cover art for the classic novel "
              f"'{book['title']}' by {book['author']}, {era} atmosphere, "
              f"literary illustration, rich colors, timeless, painterly, "
              f"no text, no letters, no typography")
    path = imagegen.generate_and_save(backend, prompt, cw, ch, out_path,
                                      caption=book["title"])
    if hasattr(backend, "free"):
        backend.free()
    return path


if __name__ == "__main__":
    # self-test: render two sample covers
    import sys
    d = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cache", "covers")
    classic_cover("Pride and Prejudice", "Jane Austen", os.path.join(d, "pnp.png"))
    classic_cover("Moby Dick; Or, The Whale", "Herman Melville", os.path.join(d, "moby.png"), seed=2)
    print("covers written to", d)
