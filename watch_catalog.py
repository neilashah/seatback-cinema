#!/usr/bin/env python3
"""
watch_catalog.py — Cheap drift check for the Delta in-flight Letterboxd list.

Scrapes the same list as lb_detail_scrape.py but does nothing with the
result except diff it against the committed titles_with_years.tsv (the file
that was actually fed into delta_ic_match.py to produce the current
matched.csv / catalog.json). If the title set changed, that's the signal
Delta rotated the catalog and the real (manual) matching pipeline should be
re-run — see DEPLOY.md §4.

This script intentionally does NOT touch titles_with_years.tsv, matched.csv,
or catalog.json. Re-running lb_detail_scrape.py + delta_ic_match.py, review,
and committing the result is what moves the baseline forward for next time.

Run:
    python3 watch_catalog.py

Exit codes (read by .github/workflows/watch-catalog.yml):
    0  no change
    1  list changed — added/removed titles printed to stdout
    2  scrape looked broken (far fewer titles than baseline) — not a real
       diff, likely a 403 or markup shift; printed to stdout so the workflow
       can flag it distinctly from a real catalog change
"""
import sys
import time

from lb_detail_scrape import fetch, extract, LIST_URL


def load_baseline(path="titles_with_years.tsv"):
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line.strip():
                continue
            parts = line.split("\t")
            title = parts[0]
            year = parts[1] if len(parts) > 1 else ""
            slug = parts[2] if len(parts) > 2 else ""
            rows.append((title, year, slug))
    return rows


def scrape_current():
    seen = set()
    rows = []
    page = 1
    while True:
        url = LIST_URL if page == 1 else f"{LIST_URL}page/{page}/"
        page_html = fetch(url)
        if not page_html:
            break
        found = extract(page_html)
        new = []
        for (t, y, s) in found:
            key = s or (t, y)
            if key in seen:
                continue
            seen.add(key)
            new.append((t, y, s))
        rows.extend(new)
        if not new:
            break
        page += 1
        time.sleep(1.0)
    return rows


def key_for(title):
    # The committed baseline (titles_with_years.tsv) has no slug column, so
    # slug can't be used to match against it — every row would miss. Match
    # on normalized title instead (case/whitespace-insensitive). Not
    # year-qualified: a scrape-to-scrape year discrepancy for the same title
    # shouldn't read as "removed X, added X".
    return " ".join(title.strip().lower().split())


def main():
    baseline = load_baseline()
    baseline_keys = {key_for(t): t for (t, y, s) in baseline}

    current = scrape_current()

    if len(current) < len(baseline) * 0.5:
        print(f"Scrape returned {len(current)} titles, expected ~{len(baseline)}. "
              f"Likely a 403 or markup shift, not a real catalog change — "
              f"see lb_detail_scrape.py.")
        sys.exit(2)

    current_keys = {key_for(t): t for (t, y, s) in current}

    added = [current_keys[k] for k in current_keys if k not in baseline_keys]
    removed = [baseline_keys[k] for k in baseline_keys if k not in current_keys]

    if not added and not removed:
        print(f"No change. {len(current)} titles match the committed baseline.")
        sys.exit(0)

    print(f"Letterboxd list changed: {len(current)} titles now, "
          f"{len(baseline)} in the committed baseline.\n")
    if added:
        print(f"Added ({len(added)}):")
        for t in sorted(added):
            print(f"  + {t}")
    if removed:
        print(f"\nRemoved ({len(removed)}):")
        for t in sorted(removed):
            print(f"  - {t}")
    print("\nRun the matching pipeline locally (lb_detail_scrape.py -> "
          "delta_ic_match.py), review, commit the new titles_with_years.tsv "
          "+ matched.csv, then trigger refresh-catalog.yml. See DEPLOY.md §4.")
    sys.exit(1)


if __name__ == "__main__":
    main()
