#!/usr/bin/env python3
"""
membership_changed.py — Did this sync actually change the movie list, or
did it just churn diagnostic noise?

This exists to gate root-level last-updated.json, which drives the app's
"last updated" indicator. That indicator answers one specific question for
a passenger: has the list of films itself changed? So it must not fire on
a run where the membership is identical and only matcher diagnostics moved.

WHY A SCRIPT AND NOT `git diff --quiet`
---------------------------------------
sync-catalog.yml used to gate on a plain `git diff` of titles_with_years.tsv
+ pipeline/matched.csv. That was wrong for matched.csv: it carries a
`popularity` column straight from TMDB, and TMDB re-scores popularity daily.
So matched.csv changed on essentially every run — the 2026-08-04 sync rewrote
179 of 189 rows with nothing but popularity drift — and last-updated.json got
bumped every single day while the real membership hadn't moved since
2026-07-26. Passengers saw "updated today", every day, which is exactly the
thing that guard was meant to prevent.

So compare only the columns that actually determine what ships:

    tmdb_id, raw_title, confidence

which is precisely the set pipeline/build_catalog.js reads out of matched.csv.
`popularity` and `n_candidates` are diagnostic output from delta_ic_match.py
and are deliberately ignored here. titles_with_years.tsv has no volatile
columns, so it's compared whole.

Comparison is against HEAD (what's currently committed), so run this BEFORE
committing, from the repo root. A file missing from HEAD counts as changed.

Run:
    python3 pipeline/membership_changed.py

Exit codes:
    0  membership changed — bump last-updated.json
    1  no membership change (or nothing but diagnostic churn) — leave it alone
    2  something went wrong (bad CSV, git unavailable); caller should treat
       this as "don't touch last-updated.json" rather than guessing
"""
import csv
import io
import subprocess
import sys

MATCHED = "pipeline/matched.csv"
TITLES = "titles_with_years.tsv"

# The only matched.csv columns that affect what ends up in the catalog.
# Keep this in sync with build_catalog.js's column reads.
SIGNIFICANT = ("tmdb_id", "raw_title", "confidence")


def head_version(path):
    """The committed contents of `path`, or None if it isn't in HEAD."""
    r = subprocess.run(["git", "show", f"HEAD:{path}"],
                       capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else None


def working_version(path):
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return None


def projection(csv_text):
    """The significant columns of a matched.csv, as an ordered list of rows.

    Order matters: a reordering of the same films is a real change to what
    the catalog looks like, not noise.
    """
    rows = list(csv.DictReader(io.StringIO(csv_text)))
    if rows and not all(c in rows[0] for c in SIGNIFICANT):
        missing = [c for c in SIGNIFICANT if c not in rows[0]]
        raise ValueError(f"{MATCHED} is missing column(s): {', '.join(missing)}")
    return [tuple(r.get(c, "") for c in SIGNIFICANT) for r in rows]


def main():
    old_titles, new_titles = head_version(TITLES), working_version(TITLES)
    if new_titles is None:
        sys.stderr.write(f"{TITLES} not found — refusing to guess\n")
        return 2
    if old_titles != new_titles:
        sys.stderr.write(f"{TITLES} changed — real membership change\n")
        return 0

    old_matched, new_matched = head_version(MATCHED), working_version(MATCHED)
    if new_matched is None:
        sys.stderr.write(f"{MATCHED} not found — refusing to guess\n")
        return 2
    if old_matched is None:
        sys.stderr.write(f"{MATCHED} is new — treating as a membership change\n")
        return 0

    try:
        old_rows, new_rows = projection(old_matched), projection(new_matched)
    except (ValueError, csv.Error) as e:
        sys.stderr.write(f"could not compare {MATCHED}: {e}\n")
        return 2

    if old_rows != new_rows:
        n = sum(1 for a, b in zip(old_rows, new_rows) if a != b)
        n += abs(len(old_rows) - len(new_rows))
        sys.stderr.write(f"{MATCHED} membership changed ({n} row(s)) — "
                          f"real membership change\n")
        return 0

    sys.stderr.write("no membership change (diagnostic columns only) — "
                     "leaving last-updated.json alone\n")
    return 1


if __name__ == "__main__":
    sys.exit(main())
