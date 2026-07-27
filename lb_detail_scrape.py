#!/usr/bin/env python3
"""
lb_detail_scrape.py — Pull (title, year) pairs from a Letterboxd list's
DETAIL view, so the matcher can disambiguate remakes/same-name films.

The grid view has no years; the /detail/ view renders each film's release
year as text. This scrapes every page and writes a TAB-separated file
ready to feed straight into delta_ic_match.py.

WHY THIS GOES THROUGH SCRAPERAPI
--------------------------------
Letterboxd sits behind Cloudflare, and Cloudflare's Turnstile-based
"Managed Challenge" (confirmed via response headers 2026-07-25/26 —
`cf-mitigated: challenge`, a "Just a moment..." interstitial) requires
actually executing JavaScript to pass. Plain HTTP requests can't do that,
on any IP, once it's triggered.

Two things were tried before this:
  1. Plain urllib + realistic browser headers — worked initially, then
     started getting challenged.
  2. A real local headful Chrome via `nodriver` — passed sometimes (2026-
     07-26 testing: 100% on the first two attempts), but not reliably (2
     later challenges that didn't clear the same day, then another
     failure on 2026-07-27) — roughly matching the 55-70% success ceiling
     independent research found for even the best free anti-bot tools
     against Turnstile. It also required a real Chrome install and only
     ran locally (a visible browser window, needing an active user
     session), which meant the sync depended on a laptop being on.

ScraperAPI (https://scraperapi.com) handles the Cloudflare bypass on
*their* infrastructure — this script just makes a plain HTTPS request to
their API with the target URL as a parameter, and they return the final
rendered HTML. That means: no local browser needed, and the request can
run from anywhere with network access, including a GitHub Actions runner
(GHA's own IPs are blocked by Letterboxd directly, but that's irrelevant
here since ScraperAPI's infrastructure is what actually reaches
Letterboxd, not GHA's). Confirmed clean on the first attempt for both
pages of this list (2026-07-27), 189/189 titles.

This project's volume (~3 requests/day) comfortably fits ScraperAPI's
free tier (1,000 credits/month, recurring) — see DEPLOY.md §5 for the
account/secret setup.

Run:
    export SCRAPERAPI_KEY=your_key_here
    python3 lb_detail_scrape.py > titles_with_years.tsv

Then:
    python3 delta_ic_match.py titles_with_years.tsv > matched.csv

It prints progress + a final count to the screen (stderr); only the
title<TAB>year<TAB>slug rows go to the file (stdout). If the count comes
back far short of the last known baseline, something's off — paste Claude
a snippet of the page HTML.
"""
import html
import os
import re
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import urlopen

LIST_URL = "https://letterboxd.com/ebusch0320/list/delta-in-flight-movies/detail/"
SCRAPERAPI_URL = "http://api.scraperapi.com"

# Each entry in ScraperAPI's rendered DOM is a "LazyPoster" component
# carrying both the display name (title + year, already formatted by
# Letterboxd's own JS) and the slug on the same tag.
ITEM_RE = re.compile(r'data-item-name="([^"]+)"[\s\S]*?data-item-slug="([^"]+)"')
TITLE_YEAR_RE = re.compile(r'^(.*) \((\d{4})\)$')


def extract(page_html):
    out = []
    for name, slug in ITEM_RE.findall(page_html):
        name = html.unescape(name).strip()
        m = TITLE_YEAR_RE.match(name)
        title, year = (m.group(1), m.group(2)) if m else (name, "")
        if not title:
            continue
        out.append((title, year, slug))
    return out


def fetch(url):
    api_key = os.environ.get("SCRAPERAPI_KEY", "")
    if not api_key:
        raise SystemExit("Set SCRAPERAPI_KEY in your environment first.")
    request_url = f"{SCRAPERAPI_URL}?api_key={api_key}&url={quote(url, safe='')}&render=true"
    for attempt in range(3):
        try:
            with urlopen(request_url, timeout=70) as r:
                return r.read().decode("utf-8", "replace")
        except HTTPError as e:
            sys.stderr.write(f"  fetch retry {attempt+1} (HTTP {e.code})\n")
            time.sleep(3 * (attempt + 1))
        except URLError as e:
            sys.stderr.write(f"  fetch retry {attempt+1} ({e})\n")
            time.sleep(3 * (attempt + 1))
    return ""


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
        # Dedupe on slug (the durable key — survives a display-title edit).
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

    # Output: title <TAB> year <TAB> slug. Downstream matcher reads title as
    # column 0, year as column 1, slug as column 2 (all optional after col 0).
    for title, year, slug in rows:
        print("\t".join([title, year, slug]))

    n_with_year = sum(1 for _, y, _ in rows if y)
    n_with_slug = sum(1 for _, _, s in rows if s)
    sys.stderr.write(f"\n--- scraped {len(rows)} films, {n_with_year} with a year, "
                     f"{n_with_slug} with a slug ---\n")
    if len(rows) < 150:
        sys.stderr.write("WARNING: fewer than expected (~189+). Markup may have "
                         "shifted, or ScraperAPI got challenged too —"
                         " send Claude a sample of the page HTML.\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.stderr.write("\ncancelled.\n")
