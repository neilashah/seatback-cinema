#!/usr/bin/env python3
"""
sync_catalog.py — Match the latest raw scrape against TMDB, safe to run
unattended.

Reads pipeline/raw_scrape.tsv (the raw Letterboxd scrape — title, year,
slug), matches every title against TMDB (respecting overrides.csv), then
SPLITS the result:

  - Titles that matched cleanly (auto or override tier) are written straight
    to titles_with_years.tsv + pipeline/matched.csv — the same files the
    manual pipeline produces — ready to commit as-is.
  - Titles that didn't (review/fuzzy/miss tier) are held OUT of both files
    entirely, so a bad match can't ship into the live catalog unreviewed.
    They're written to flagged.txt instead, for the caller to surface
    however it likes (the CI workflow opens a GitHub issue). They'll keep
    reappearing on every future run until an overrides.csv entry resolves
    them one way or the other — see DEPLOY.md §5.

Note this script does NOT do the Letterboxd scrape itself (that used to be
a subprocess call to lb_detail_scrape.py here, but Letterboxd blocks
requests from GitHub Actions' runner IPs with a 403 even with realistic
browser headers — confirmed 2026-07-25 — so the scrape can't run in CI at
all). push_scrape.sh runs the scrape from a real machine instead and pushes
pipeline/raw_scrape.tsv when it changes; that push is what triggers this
script in CI. Running lb_detail_scrape.py by hand and pointing this at its
output works identically for a local/manual run.

Known limitation: if a title that matched cleanly on a previous run becomes
ambiguous on a later run (e.g. TMDB gains a same-title collision film), it
is DROPPED from the catalog until re-resolved, even though it shipped fine
before. This is deliberate — silently keeping a possibly-stale match isn't
safer than holding it back — but worth knowing if a previously-fine title
unexpectedly disappears.

Run (from repo root, TMDB_KEY set, pipeline/raw_scrape.tsv present):
    python3 sync_catalog.py

Writes (only touches these on success — a failure leaves everything as-is):
    titles_with_years.tsv   — clean-tier titles only
    pipeline/matched.csv    — clean-tier titles only
    flagged.txt             — human-readable summary of held-back titles
                              (present but empty if there are none)

Exit codes:
    0  ran fine (flagged.txt may or may not be empty — check its size)
    1  raw_scrape.tsv missing/empty, or the match step failed outright (e.g.
       TMDB_KEY missing/invalid, or a row-count mismatch)
"""
import csv
import io
import os
import subprocess
import sys

CLEAN_TIERS = {"auto", "override"}
RAW_SCRAPE = "pipeline/raw_scrape.tsv"
SCRATCH_TSV = "titles_with_years.tsv.tmp"


def main():
    if not os.path.exists(RAW_SCRAPE):
        sys.stderr.write(f"{RAW_SCRAPE} not found — run push_scrape.sh (or "
                          f"lb_detail_scrape.py) first. Aborting, nothing written\n")
        sys.exit(1)
    with open(RAW_SCRAPE, encoding="utf-8") as f:
        titles_tsv = f.read()
    if not titles_tsv.strip():
        sys.stderr.write(f"{RAW_SCRAPE} is empty — aborting, nothing written\n")
        sys.exit(1)

    # delta_ic_match.py reads a file path, not stdin — hand it the scrape
    # unchanged, same as the manual pipeline does.
    with open(SCRATCH_TSV, "w", encoding="utf-8") as f:
        f.write(titles_tsv)

    match = subprocess.run([sys.executable, "delta_ic_match.py", SCRATCH_TSV],
                            capture_output=True, text=True)
    sys.stderr.write(match.stderr)   # progress + tier summary, for the CI log
    os.remove(SCRATCH_TSV)
    if match.returncode != 0 or not match.stdout.strip():
        sys.stderr.write("match failed — aborting, nothing written\n")
        sys.exit(1)

    tsv_lines = [l for l in titles_tsv.splitlines() if l.strip()]
    rows = list(csv.DictReader(io.StringIO(match.stdout)))
    if len(rows) != len(tsv_lines):
        sys.stderr.write(f"row count mismatch: {len(tsv_lines)} scraped vs "
                          f"{len(rows)} matched — aborting, nothing written\n")
        sys.exit(1)

    clean_tsv, clean_rows, flagged_rows = [], [], []
    for line, row in zip(tsv_lines, rows):
        if row["confidence"] in CLEAN_TIERS:
            clean_tsv.append(line)
            clean_rows.append(row)
        else:
            flagged_rows.append(row)

    with open("titles_with_years.tsv", "w", encoding="utf-8") as f:
        f.write("\n".join(clean_tsv) + ("\n" if clean_tsv else ""))

    with open("pipeline/matched.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(clean_rows)

    with open("flagged.txt", "w", encoding="utf-8") as f:
        if flagged_rows:
            f.write(f"{len(flagged_rows)} title(s) held back from the catalog "
                     f"this sync — matcher wasn't confident enough to ship them "
                     f"unreviewed:\n\n")
            for row in flagged_rows:
                f.write(f"- \"{row['raw_title']}\" ({row['year_hint'] or 'no year'}) "
                        f"[{row['confidence']}] — {row['note']}\n")
                if row.get("tmdb_id"):
                    f.write(f"  best guess: https://www.themoviedb.org/movie/"
                            f"{row['tmdb_id']} — \"{row['matched_title']}\" "
                            f"({row['release_year']})\n")
            f.write("\nTo resolve: add a line to overrides.csv pinning the "
                    "correct tmdb_id (or the same id shown above to bless it), "
                    "and it'll pick up cleanly next sync. See overrides.csv's "
                    "own header for the exact format.\n")

    print(f"clean: {len(clean_rows)}, flagged: {len(flagged_rows)}")


if __name__ == "__main__":
    main()
