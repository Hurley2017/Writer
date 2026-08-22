"""Bulk Publisher CLI — one command to bulk-produce books for writers-palette.com.

  py -3 -m bulk.run_bulk --classics 5                # 5 public-domain classics
  py -3 -m bulk.run_bulk --classics 3 --curated 1342,84,11
  py -3 -m bulk.run_bulk --generated 2               # 2 on-device AI books
  py -3 -m bulk.run_bulk --classics 2 --generated 1  # mixed run
  py -3 -m bulk.run_bulk --list-top 25               # preview Gutendex candidates

Publishing requires bulk/secrets.json (see secrets.json.example). Without it the
run defaults to --no-publish (books are still produced locally).
"""
import argparse
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_PROJ = os.path.dirname(_HERE)
if _PROJ not in sys.path:
    sys.path.insert(0, _PROJ)

os.environ.setdefault("HF_HOME", r"D:\hf_cache")
os.environ.setdefault("HF_HUB_CACHE", r"D:\hf_cache\hub")
os.environ["HF_HUB_DISABLE_SYMLINKS"] = "1"


def main(argv=None):
    ap = argparse.ArgumentParser(prog="bulk", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--classics", type=int, default=0, metavar="N",
                    help="produce N public-domain classics (Gutendex -> PDF + cover + LibriVox)")
    ap.add_argument("--generated", type=int, default=0, metavar="N",
                    help="produce N on-device AI books (story + cover + audio + PDF)")
    ap.add_argument("--curated", default="", metavar="IDS",
                    help="comma-separated Gutenberg ids to produce first (e.g. 1342,84,11)")
    ap.add_argument("--list-top", type=int, default=0, metavar="N",
                    help="list the top N Gutendex candidates and exit")
    ap.add_argument("--librivox", choices=["link", "upload", "skip"], default=None,
                    help="how to handle LibriVox audio (default from bulk_config: link)")
    ap.add_argument("--sd-covers", action="store_true",
                    help="classic covers via Stable Diffusion instead of typographic")
    ap.add_argument("--backfill-covers", action="store_true",
                    help="regenerate covers of ALREADY-produced classics with AI art "
                         "(re-publishes so the new cover goes live, unless --no-publish)")
    ap.add_argument("--publish-ready", action="store_true",
                    help="publish books that are produced locally ('ready') but not yet "
                         "on the website (no-duplicate guard applies)")
    ap.add_argument("--limit", type=int, default=0, metavar="N",
                    help="only process the first N books (with --backfill-covers/--publish-ready)")
    ap.add_argument("--no-publish", action="store_true",
                    help="produce everything but skip publishing")
    ap.add_argument("--dry-run", action="store_true",
                    help="like --no-publish but also skip downloads; just show the plan")
    ap.add_argument("--out", default=None, help="output directory (default: output/)")
    ap.add_argument("--max-pdf-chapters", type=int, default=None,
                    help="cap chapters rendered into the classic PDF")
    ap.add_argument("--category", default=None, help="website category override")
    ap.add_argument("--author", default=None, help="author name for generated books")
    ap.add_argument("--length", choices=["short", "medium", "long"], default=None,
                    help="length of generated books")
    ap.add_argument("--narrator", choices=["auto", "male", "female"], default=None,
                    help="TTS narrator gender for generated books")
    ap.add_argument("--yes", action="store_true", help="skip the confirmation prompt")
    args = ap.parse_args(argv)

    from bulk.bulk_config import load_bulk_config, ensure_dirs
    cfg = ensure_dirs(load_bulk_config())

    if args.out:
        cfg["bulk"]["output_dir"] = args.out
    if args.librivox:
        cfg["bulk"]["librivox"] = args.librivox
    if args.max_pdf_chapters:
        cfg["bulk"]["max_chapters_pdf"] = args.max_pdf_chapters
    if args.category:
        cfg["bulk"]["category"] = args.category

    # ---- preview mode ----
    if args.list_top:
        from bulk import pipeline_classics
        pipeline_classics.list_candidates(cfg, args.list_top)
        return 0

    # ---- publish-ready mode ----
    if args.publish_ready:
        from bulk import pipeline_classics
        print("=" * 64)
        print("  PUBLISH READY BOOKS — produced locally, not yet on the website")
        print("=" * 64)
        if not args.yes and not args.dry_run:
            try:
                r = input("Continue? [y/N] ").strip().lower()
                if r not in ("y", "yes"):
                    print("Aborted.")
                    return 0
            except EOFError:
                pass
        opts = dict(dry_run=args.dry_run, no_publish=args.no_publish)
        pipeline_classics.publish_ready(cfg, opts, limit=args.limit)
        return 0

    # ---- backfill covers mode ----
    if args.backfill_covers:
        from bulk import pipeline_classics
        print("=" * 64)
        print("  BACKFILL AI COVERS — classics already in bulk/state.json")
        print(f"  publish : {'NO' if args.no_publish or args.dry_run else 'YES'}")
        print("=" * 64)
        if not args.yes and not args.dry_run:
            try:
                r = input("Continue? [y/N] ").strip().lower()
                if r not in ("y", "yes"):
                    print("Aborted.")
                    return 0
            except EOFError:
                pass
        opts = dict(dry_run=args.dry_run, no_publish=args.no_publish)
        pipeline_classics.backfill_covers(cfg, opts, limit=args.limit)
        return 0

    total = args.classics + args.generated
    if total == 0:
        ap.print_help()
        return 0

    print("=" * 64)
    print("  BULK PUBLISHER — writers-palette.com")
    print(f"  classics: {args.classics}   generated: {args.generated}")
    print(f"  publish : {'NO' if args.no_publish or args.dry_run else 'YES'}")
    print("=" * 64)

    if not args.yes and not args.dry_run:
        try:
            r = input("Continue? [y/N] ").strip().lower()
            if r not in ("y", "yes"):
                print("Aborted.")
                return 0
        except EOFError:
            pass

    curated = [int(x) for x in args.curated.split(",") if x.strip().isdigit()] if args.curated else None

    results = []
    if args.classics:
        from bulk import pipeline_classics
        opts = dict(dry_run=args.dry_run, no_publish=args.no_publish,
                    librivox=cfg["bulk"]["librivox"],
                    max_pdf_chapters=cfg["bulk"]["max_chapters_pdf"],
                    sd_covers=args.sd_covers, category=cfg["bulk"]["category"])
        r = pipeline_classics.run_classics(cfg, args.classics, curated, opts)
        results += [("classics", x) for x in r]
    if args.generated:
        from bulk import pipeline_generated
        opts = dict(dry_run=args.dry_run, no_publish=args.no_publish,
                    length=args.length, author=args.author, narrator=args.narrator,
                    category=cfg["bulk"]["generated_category"])
        r = pipeline_generated.run_generated(cfg, args.generated, opts)
        results += [("generated", x) for x in r]

    print("\n" + "=" * 64)
    print("SUMMARY")
    for kind, x in results:
        st = x.get("status")
        icon = {"published": "PUBLISHED", "ready": "ready", "failed": "FAILED"}.get(st, st)
        print(f"  [{icon:>9}] ({kind}) {x.get('title')}  "
              f"{('audio=' + str(x.get('audio'))) if x.get('audio') is not None else ''} "
              f"{('- ' + x.get('error')) if x.get('error') else ''}")
    print("=" * 64)
    return 0


if __name__ == "__main__":
    sys.exit(main())
