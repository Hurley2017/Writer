"""Bulk Publisher — standalone bulk publisher for writers-palette.com.

Two production tracks, fully local except the final publish step:
  Track 1 (classics): Gutendex public-domain text  ->  A5 Palatino PDF
                       ->  cover  ->  LibriVox audiobook (matched + uploaded)
                       ->  publish-book edge function
  Track 2 (generated): on-device story + cover + audio + PDF  ->  publish

Run:  py -3 -m bulk.run_bulk --help
"""
