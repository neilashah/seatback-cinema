#!/usr/bin/env python3
"""
delta_ic_match.py — Resolve raw Delta catalog titles to TMDB IDs.

Proof-of-concept matcher for the Impure Cinema "Delta in-flight" app.
Takes a list of raw title strings (optionally with a year) and resolves
each to a canonical TMDB movie, emitting a confidence tier so you know
which rows are safe to auto-ship and which need a human eye / override.

WHY THIS SHAPE
--------------
The whole title-matching risk is: a raw string like "Cinderella" or
"The Running Man" maps to several TMDB films. A YEAR collapses almost
all of that ambiguity. The Letterboxd *grid* view has no years; the
Letterboxd *detail* view (/detail/) does — so feed this (title, year)
pairs from the detail view and the ambiguous bucket nearly empties.

USAGE
-----
    export TMDB_KEY=your_key_here
    python3 delta_ic_match.py titles.tsv > matched.csv

  titles.tsv: one title per line, optional TAB year:
    The Running Man<TAB>2025
    Cinderella<TAB>2015
    Parasite

OUTPUT (CSV): raw_title, year_hint, tmdb_id, matched_title, release_year,
              confidence, popularity, n_candidates, note

CONFIDENCE TIERS
----------------
  auto    exact normalized-title match, and either a year that agrees or
          a single dominant candidate. Safe to ship unattended.
  review  matched, but multiple plausible candidates or no year to break
          a tie, or a remake-collision title. Eyeball before shipping.
  fuzzy   no exact title hit; best fuzzy candidate returned. Likely needs
          an override entry.
  miss    nothing plausible. Definitely an override (or not on TMDB).

No third-party deps required (uses stdlib difflib). rapidfuzz is better
if you have it, but this keeps the PoC install-free.
"""

import csv
import os
import sys
import time
import json
import unicodedata
from difflib import SequenceMatcher
from urllib.parse import urlencode
from urllib.request import urlopen, Request
from urllib.error import HTTPError, URLError

TMDB_KEY = os.environ.get("TMDB_KEY", "")
TMDB_SEARCH = "https://api.themoviedb.org/3/search/movie"
TMDB_MOVIE = "https://api.themoviedb.org/3/movie"   # /{id} for override lookups
OVERRIDES_PATH = os.environ.get("OVERRIDES", "overrides.csv")

# Titles that are famous originals with a recent remake (or vice versa):
# even WITH a year these deserve a human glance, because a one-year OCR/
# scrape slip flips you to the wrong film. Extend freely as you learn.
REMAKE_COLLISION = {
    "the running man", "point break", "kiss of the spider woman",
    "anaconda", "wuthering heights", "cinderella", "beauty and the beast",
    "the lion king", "mulan", "the little mermaid", "pinocchio",
    "west side story", "dune", "the great gatsby", "murder on the orient express",
}

# Non-film / thin-data patterns: sports "official films", galas, etc.
# These often DO resolve on TMDB but will have no critic/audience ratings,
# so the IC score will be empty — worth flagging so they don't look "broken".
THIN_DATA_HINTS = ("masters", "official film", "idol", "long live")


def norm(s: str) -> str:
    """Lowercase, strip accents/punctuation/articles for comparison."""
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    s = s.lower().strip()
    for lead in ("the ", "a ", "an "):
        if s.startswith(lead):
            s = s[len(lead):]
    return "".join(ch for ch in s if ch.isalnum() or ch == " ").strip()


def ratio(a: str, b: str) -> float:
    return SequenceMatcher(None, norm(a), norm(b)).ratio()


def tmdb_search(title, year=None):
    if not TMDB_KEY:
        raise SystemExit("Set TMDB_KEY in your environment first.")
    params = {"api_key": TMDB_KEY, "query": title, "include_adult": "false"}
    if year:
        params["year"] = year
    req = Request(f"{TMDB_SEARCH}?{urlencode(params)}",
                  headers={"User-Agent": "impure-cinema-poc"})
    for attempt in range(4):
        try:
            with urlopen(req, timeout=15) as r:
                return json.loads(r.read()).get("results", [])
        except HTTPError as e:
            if e.code == 429:               # rate limited — back off
                time.sleep(2 * (attempt + 1))
                continue
            raise
        except URLError:
            time.sleep(1.5 * (attempt + 1))
    return []


def tmdb_get_by_id(movie_id):
    """Fetch one movie by TMDB id — used to fill display fields for an
    override (and to validate the pinned id is real). Returns {} on failure
    so an override still emits its pinned id even if the lookup hiccups."""
    if not TMDB_KEY:
        raise SystemExit("Set TMDB_KEY in your environment first.")
    url = f"{TMDB_MOVIE}/{movie_id}?{urlencode({'api_key': TMDB_KEY})}"
    req = Request(url, headers={"User-Agent": "impure-cinema-poc"})
    for attempt in range(4):
        try:
            with urlopen(req, timeout=15) as r:
                return json.loads(r.read())
        except HTTPError as e:
            if e.code == 429:
                time.sleep(2 * (attempt + 1)); continue
            return {}
        except URLError:
            time.sleep(1.5 * (attempt + 1))
    return {}


def load_overrides(path):
    """Load the manual overrides table. Each row pins a title to a confirmed
    TMDB id, so it never re-enters the review queue.

    CSV columns: key, tmdb_id, note
      key     = Letterboxd slug (preferred, stable) OR a title string
      tmdb_id = the confirmed TMDB movie id
      note    = why (e.g. 'confirmed correct' or 'was matching the 1987 film')

    Blank lines and lines starting with '#' are ignored, so you can comment
    the file freely. Returns ({} , 0) if the file doesn't exist yet."""
    overrides = {}
    count = 0
    if not os.path.exists(path):
        return overrides, count
    with open(path, encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            parts = next(csv.reader([line]))
            if len(parts) < 2 or not parts[1].strip():
                continue
            key = parts[0].strip()
            tmdb_id = parts[1].strip()
            note = parts[2].strip() if len(parts) > 2 else "manual override"
            # Index under both the raw key and its normalized form, so a slug
            # OR a loosely-typed title both resolve. (Slug and title normalize
            # differently, so both forms are needed.)
            overrides[key] = (tmdb_id, note)
            overrides[norm(key)] = (tmdb_id, note)
            count += 1
    return overrides, count


def override_row(raw, year, tmdb_id, note):
    """Build an output row for an override hit, filling display fields from a
    by-id lookup where possible."""
    row = {"raw_title": raw, "year_hint": year or "", "tmdb_id": tmdb_id,
           "matched_title": "", "release_year": "", "confidence": "override",
           "popularity": "", "n_candidates": "", "note": note}
    info = tmdb_get_by_id(tmdb_id)
    if info:
        row["matched_title"] = info.get("title", "")
        row["release_year"] = (info.get("release_date") or "")[:4]
        row["popularity"] = round(info.get("popularity", 0), 1)
    else:
        row["note"] = note + "; WARNING: id lookup failed — verify id is valid"
    return row


def classify(raw, year, results):
    base = {"raw_title": raw, "year_hint": year or "", "tmdb_id": "",
            "matched_title": "", "release_year": "", "confidence": "miss",
            "popularity": "", "n_candidates": len(results), "note": ""}
    if not results:
        base["note"] = "no TMDB results"
        return base

    # Rank: exact normalized-title matches first, then by popularity.
    exact = [r for r in results if norm(r.get("title", "")) == norm(raw)
             or norm(r.get("original_title", "")) == norm(raw)]
    pool = exact or results
    pool = sorted(pool, key=lambda r: r.get("popularity", 0), reverse=True)
    best = pool[0]
    ry = (best.get("release_date") or "")[:4]

    base.update({
        "tmdb_id": best.get("id", ""),
        "matched_title": best.get("title", ""),
        "release_year": ry,
        "popularity": round(best.get("popularity", 0), 1),
    })

    year_ok = (year and ry == year)
    year_conflict = (year and ry and ry != year)
    collision = norm(raw) in REMAKE_COLLISION
    thin = any(h in raw.lower() for h in THIN_DATA_HINTS)

    if not exact:
        r = ratio(raw, best.get("title", ""))
        base["confidence"] = "fuzzy"
        base["note"] = f"no exact title match (best ratio {r:.2f})"
        return base

    # We have at least one exact-title candidate.
    # A year mismatch only matters when there's ANOTHER film it could be
    # confused with. With a single candidate on all of TMDB, a Letterboxd-vs-
    # TMDB year disagreement is just festival-vs-release-date metadata noise
    # for the same film — auto-accept it, with a quiet note.
    if year_conflict and len(results) == 1 and not collision:
        base["confidence"] = "auto"
        base["note"] = f"year differs (LB {year} / TMDB {ry}); sole candidate, same film"
    elif year_conflict:
        base["confidence"] = "review"
        base["note"] = f"year hint {year} != top match {ry}; {len(results)} candidates — check remake/original"
    elif collision and not year_ok:
        base["confidence"] = "review"
        base["note"] = "remake-collision title; supply a year to disambiguate"
    elif len(exact) > 1 and not year_ok:
        base["confidence"] = "review"
        base["note"] = f"{len(exact)} same-title films; year would disambiguate"
    else:
        base["confidence"] = "auto"
    if thin:
        base["note"] = (base["note"] + "; " if base["note"] else "") + \
                        "likely thin/absent ratings — IC score may be empty"
    return base


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("usage: python3 delta_ic_match.py titles.tsv > out.csv")
    overrides, n_over = load_overrides(OVERRIDES_PATH)
    if n_over:
        sys.stderr.write(f"loaded {n_over} override(s) from {OVERRIDES_PATH}\n")
    # Read every title up front so we can show "N of TOTAL" progress.
    # Input columns: title <TAB> year <TAB> slug (year and slug optional).
    entries = []
    with open(sys.argv[1], encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line.strip():
                continue
            parts = line.split("\t")
            title = parts[0].strip()
            year = parts[1].strip() if len(parts) > 1 and parts[1].strip() else None
            slug = parts[2].strip() if len(parts) > 2 and parts[2].strip() else ""
            entries.append((title, year, slug))

    total_in = len(entries)
    rows = []
    for i, (title, year, slug) in enumerate(entries, 1):
        # Progress goes to stderr so it prints live to the screen without
        # landing in matched.csv. \r keeps it on one updating line.
        sys.stderr.write(f"\r[{i:3}/{total_in}] {title[:40]:<40}")
        sys.stderr.flush()

        # Overrides win before any TMDB search: look up by slug, then by raw
        # title, then by normalized title. A hit pins the id and skips review.
        hit = (overrides.get(slug) or overrides.get(title)
               or overrides.get(norm(title)))
        if hit:
            tmdb_id, note = hit
            rows.append(override_row(title, year, tmdb_id, note))
            time.sleep(1.0)
            continue

        results = tmdb_search(title, year)
        # If a year filter returned nothing, retry unfiltered before giving up.
        if not results and year:
            results = tmdb_search(title, None)
        rows.append(classify(title, year, results))
        time.sleep(1.0)   # be polite to TMDB's rate limit
    sys.stderr.write("\n")   # finish the progress line

    w = csv.DictWriter(sys.stdout, fieldnames=list(rows[0].keys()))
    w.writeheader()
    w.writerows(rows)

    # Summary to stderr so it doesn't pollute the CSV.
    from collections import Counter
    c = Counter(r["confidence"] for r in rows)
    total = len(rows)
    print("\n--- match summary ---", file=sys.stderr)
    for tier in ("auto", "override", "review", "fuzzy", "miss"):
        n = c.get(tier, 0)
        print(f"{tier:8} {n:3}  {n/total*100:5.1f}%", file=sys.stderr)
    print(f"total    {total}", file=sys.stderr)
    n_review = c.get("review", 0)
    if n_review:
        print(f"\n{n_review} title(s) to review — see the ',review,' rows in "
              f"the CSV, then add decisions to {OVERRIDES_PATH}", file=sys.stderr)


if __name__ == "__main__":
    main()
