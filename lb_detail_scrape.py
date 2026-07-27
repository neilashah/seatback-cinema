#!/usr/bin/env python3
"""
lb_detail_scrape.py — Pull (title, year) pairs from a Letterboxd list's
DETAIL view, so the matcher can disambiguate remakes/same-name films.

The grid view has no years; the /detail/ view renders each film's release
year as text. This scrapes every page and writes a TAB-separated file
ready to feed straight into delta_ic_match.py.

WHY A REAL BROWSER (nodriver), NOT plain HTTP requests
-------------------------------------------------------
This used to be a plain urllib scraper with realistic browser headers.
That stopped being enough: Letterboxd sits behind Cloudflare, and
Cloudflare's Turnstile-based "Managed Challenge" (confirmed via response
headers 2026-07-25/26 — `cf-mitigated: challenge`, a "Just a moment..."
interstitial referencing challenges.cloudflare.com) requires actually
executing JavaScript to pass. No plain HTTP client can do that, on any IP,
once it's triggered — headers alone don't help.

nodriver (successor to undetected-chromedriver) drives a real Chrome and
is specifically built to minimize automation fingerprints. Empirically
(2026-07-26 testing): headless=True still got challenged; headless=False
(a real, visible Chrome window) passed cleanly and consistently across a
2-page pagination test. So this now runs a real, visible Chrome — fine for
a local/launchd run on a machine with an active user session, but it does
mean a Chrome window will briefly appear during the scheduled scrape.

One-time setup: `pip install nodriver` needs a real Chrome install (not
just Chromium) to drive. Known packaging bug in nodriver 0.50.3: a
mis-encoded byte in its bundled cdp/network.py (`\xb1Inf` in a comment)
throws a SyntaxError on import under Python 3.14's stricter source-encoding
handling. Fix by hand if this happens:
    python3 -c "
    p = '<path to>/site-packages/nodriver/cdp/network.py'
    d = open(p, 'rb').read()
    open(p, 'wb').write(d.replace(b'\xb1Inf', b'+/-Inf'))
    "
(Check whether a newer nodriver release has fixed this before reapplying —
this workaround shouldn't be needed forever.)

A side benefit of the real-browser switch: the rendered DOM exposes
cleaner data than the old raw-HTML approach ever had — `data-item-name`
carries "Title (Year)" and `data-item-slug` sits on the very same tag, no
need to chase title text across `alt`/`data-film-name`/anchor-text
fallbacks like the old server-rendered HTML required.

Run:
    python3 lb_detail_scrape.py > titles_with_years.tsv

Then:
    python3 delta_ic_match.py titles_with_years.tsv > matched.csv

It prints progress + a final count to the screen (stderr); only the
title<TAB>year<TAB>slug rows go to the file (stdout). If the count comes
back far short of the last known baseline, something's off — paste Claude
a snippet of the page HTML.
"""
import asyncio
import html
import re
import sys

import nodriver as uc

LIST_URL = "https://letterboxd.com/ebusch0320/list/delta-in-flight-movies/detail/"

# Each entry in the rendered DOM is a "LazyPoster" component carrying both
# the display name (title + year, already formatted by Letterboxd's own
# JS) and the slug on the same tag — far simpler than reconstructing this
# from the old raw server HTML's scattered attributes.
ITEM_RE = re.compile(r'data-item-name="([^"]+)"[\s\S]*?data-item-slug="([^"]+)"')
TITLE_YEAR_RE = re.compile(r'^(.*) \((\d{4})\)$')

# How long to let a navigated page settle before reading its content — long
# enough for Letterboxd's JS to hydrate the poster grid and, if Cloudflare
# serves a Managed Challenge, for it to auto-resolve. If a page still looks
# challenged after this, one extra wait is tried before giving up on it.
SETTLE_SECONDS = 4
RETRY_SETTLE_SECONDS = 6


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


def looks_challenged(page_html):
    return "Just a moment" in page_html or "challenge-platform" in page_html


async def fetch(tab, url):
    await tab.get(url)
    await tab.sleep(SETTLE_SECONDS)
    page_html = await tab.get_content()
    if looks_challenged(page_html):
        sys.stderr.write("  still looks challenged, waiting longer...\n")
        await tab.sleep(RETRY_SETTLE_SECONDS)
        page_html = await tab.get_content()
    if looks_challenged(page_html):
        sys.stderr.write("  challenge did not clear for this page\n")
        return ""
    return page_html


async def scrape():
    seen = set()
    rows = []
    browser = await uc.start(headless=False)
    try:
        tab = await browser.get(LIST_URL)
        page = 1
        while True:
            url = LIST_URL if page == 1 else f"{LIST_URL}page/{page}/"
            sys.stderr.write(f"fetching page {page}...\n")
            page_html = await fetch(tab, url)
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
    finally:
        browser.stop()

    return rows


def main():
    rows = asyncio.run(scrape())

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
                         "shifted, or the Cloudflare challenge didn't clear —"
                         " send Claude a sample of the page HTML.\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.stderr.write("\ncancelled.\n")
