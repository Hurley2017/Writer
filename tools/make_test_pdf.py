"""Build a demo PDF from a hardcoded story + placeholder images.

Use this to validate the layout against 'Second Light of March.pdf'
without needing LM Studio or an image server.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import pdfbuilder, imagegen
from src.config import load_config

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "output", "test-layout")


def demo_story():
    para = lambda t: t  # noqa
    P = [
        "The rain had not stopped for eleven days. It drummed on the tin roofs of Ratnapur "
        "like a restless audience, turning every street into a mirror of grey water. Inside "
        "the lamplit room, a boy of fourteen pressed his palm against the window and watched "
        "the city drown in its own reflection.",
        "His father believed that silence was a language, and the house spoke it fluently. "
        "Meals were eaten without ceremony, goodbyes without embraces, and yet the boy had "
        "learned to read the weather in his father's hands - the way they tightened around a "
        "cup when the harvest failed, the way they opened, briefly, like a gift, when the "
        "letter from the academy arrived.",
        "The letter sat on the table now, its seal unbroken. Outside, the rain kept its "
        "steady percussion, and the boy understood, with the terrible clarity of the young, "
        "that some doors only open once.",
    ]
    return {
        "title": "The Rainkeeper's Promise",
        "author": "Demo Author",
        "prologue": {"title": "The Opening", "paragraphs": P, "image_prompts": []},
        "sections": [
            {
                "title": "The Roots",
                "chapters": [
                    {"title": "The Echoes of Beginning", "paragraphs": P, "image_prompts": []},
                    {"title": "The Underlying Currents", "paragraphs": P, "image_prompts": []},
                ],
            },
            {
                "title": "The Storm Within",
                "chapters": [
                    {"title": "The Threshold", "paragraphs": P, "image_prompts": []},
                    {"title": "The First Reckoning", "paragraphs": P, "image_prompts": []},
                ],
            },
        ],
        "epilogue": {"title": "The Closing", "paragraphs": P, "image_prompts": []},
    }


def main():
    cfg = load_config()
    os.makedirs(OUT, exist_ok=True)
    images_dir = os.path.join(OUT, "images")
    os.makedirs(images_dir, exist_ok=True)

    backend = imagegen.Placeholder(cfg)
    story = demo_story()

    # cover + back only (no in-paragraph pictures)
    images = {}
    images["cover"] = imagegen.generate_and_save(
        backend, "cover scene", 768, 1088, os.path.join(images_dir, "cover.png"),
        caption=story["title"])
    images["back"] = images["cover"]

    pdf_path = os.path.join(OUT, "test-layout.pdf")
    pdfbuilder.build_pdf(story, images, pdf_path, opts={
        "divider": True,
    })
    print("Wrote", pdf_path)


if __name__ == "__main__":
    main()
