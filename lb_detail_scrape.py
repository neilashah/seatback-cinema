#!/usr/bin/env python3
"""
lb_detail_scrape.py — Pull (title, year) pairs from a Letterboxd list's
DETAIL view, so the matcher can disambiguate remakes/same-name films.

The grid view has no years; the /detail/ view renders each film's release
year as text. This scrapes every page and writes a TAB-separated file
ready to feed straight into delta_ic_match.py.

Run:
    python3 lb_detail_scrape.py > titles_with_years.tsv

Then:
    python3 delta_ic_match.py titles_with_years.tsv > matched.csv

It prints progress + a final count to the screen (stderr); only the
title<TAB>year rows go to the file (stdout). If the count comes back far
from ~198, the markup shifted — paste Claude a snippet and we adjust the
regex.
"""
import re
import sys
import time
import html
from urllib.request import urlopen, Request
from urllib.error import HTTPError, URLError

LIST_URL = "https://letterboxd.com/ebusch0320/list/delta-in-flight-movies/detail/"
# Full browser-like headers — Letterboxd 403s requests whose User-Agent looks
# like a script. A complete, real UA plus the Accept headers a browser sends
# gets us treated as an ordinary visitor.
HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/126.0.0.0 Safari/537.36"),
    "Accept": ("text/html,application/xhtml+xml,application/xml;q=0.9,"
               "image/avif,image/webp,*/*;q=0.8"),
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://letterboxd.com/",
}

# Each film entry in the detail view is a poster container carrying the slug,
# followed (within the same list item) by the title and a /films/year/YYYY/
# link. We split the page into per-film chunks on the slug attribute, then
# pull title + year out of each chunk. Splitting first makes the pairing
# robust to markup reordering.
SLUG_SPLIT = re.compile(r'data-(?:film|item)-slug="')
YEAR_RE    = re.compile(r'/films/year/(\d{4})/')
# Title: prefer the poster img alt text (reliably the clean title), then
# fall back to data-film-name or the film-link anchor text.
ALT_RE     = re.compile(r'alt="([^"]+)"')
NAME_ATTR  = re.compile(r'data-(?:film|item)-name="([^"]+)"')
ANCHOR_RE  = re.compile(r'/film/[^/"]+/"[^>]*>([^<]+)<')


def fetch(url):
    for attempt in range(6):
        try:
            with urlopen(Request(url, headers=HEADERS), timeout=20) as r:
                return r.read().decode("utf-8", "replace")
        except HTTPError as e:
            sys.stderr.write(f"  fetch retry {attempt+1} (HTTP {e.code})\n")
            time.sleep(3 * (attempt + 1))   # gentler, longer backoff on 403
        except URLError as e:
            sys.stderr.write(f"  fetch retry {attempt+1} ({e})\n")
            time.sleep(3 * (attempt + 1))
    return ""


def extract(page_html):
    chunks = SLUG_SPLIT.split(page_html)[1:]   # first chunk is pre-list header
    out = []
    for ch in chunks:
        # The slug is the value we just split on — it sits at the very start of
        # the chunk, up to the closing quote. This is the STABLE identifier for
        # overrides (survives Letterboxd tweaking a display title).
        slug = ch[:ch.index('"')] if '"' in ch[:200] else ""
        ch = ch[:4000]                          # stay within this film's block
        year_m = YEAR_RE.search(ch)
        title_m = ALT_RE.search(ch) or NAME_ATTR.search(ch) or ANCHOR_RE.search(ch)
        if not title_m:
            continue
        title = html.unescape(title_m.group(1)).strip()
        year = year_m.group(1) if year_m else ""
        # Skip obvious non-film chrome that slipped through.
        if not title or title.lower() in ("letterboxd", "add to your films…"):
            continue
        out.append((title, year, slug))
    return out


def main():
    seen = set()
    rows = []
    page = 1
    while True:
        url = LIST_URL if page == 1 else f"{LIST_URL}page/{page}/"
        sys.stderr.write(f"fetching page {page}...\n")
        page_html = fetch(url)
        if not page_html:
            break
        found = extract(page_html)
        # Dedupe on slug when present (the durable key), else title+year.
        new = []
        for (t, y, s) in found:
            key = s or (t, y)
            if key in seen:
                continue
            seen.add(key)
            new.append((t, y, s))
        rows.extend(new)
        sys.stderr.write(f"  page {page}: {len(found)} entries ({len(new)} new)\n")
        # Stop when a page yields nothing new (past the last page).
        if not new:
            break
        page += 1
        time.sleep(1.0)

    # Output: title <TAB> year <TAB> slug. Downstream matcher reads title as
    # column 0, year as column 1, slug as column 2 (all optional after col 0).
    for title, year, slug in rows:
        print("\t".join([title, year, slug]))

    n_with_year = sum(1 for _, y, _ in rows if y)
    n_with_slug = sum(1 for _, _, s in rows if s)
    sys.stderr.write(f"\n--- scraped {len(rows)} films, {n_with_year} with a year, "
                     f"{n_with_slug} with a slug ---\n")
    if len(rows) < 150:
        sys.stderr.write("WARNING: fewer than expected (~198). Markup may have "
                         "shifted — send Claude a sample of the page HTML.\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.stderr.write("\ncancelled.\n")
