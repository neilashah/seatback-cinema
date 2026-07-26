#!/usr/bin/env bash
# push_scrape.sh — the one piece of the catalog pipeline that has to run
# from a real IP: Letterboxd blocks GitHub Actions runner IPs with a 403
# even with realistic browser headers (confirmed 2026-07-25, both scheduled
# watch-catalog.yml runs and a manual sync-catalog.yml run all got blocked
# — see DEPLOY.md §5). So the scrape itself runs here instead of in CI.
#
# Scrapes the Letterboxd list; if it differs from the committed
# pipeline/raw_scrape.tsv, commits and pushes just that file. That push is
# what triggers sync-catalog.yml, which does everything downstream (TMDB
# matching, splitting clean/flagged, committing, issue management) in CI,
# where Letterboxd is never touched again.
#
# Meant to run on a schedule via launchd (see
# com.seatback-cinema.push-scrape.plist) but safe to run by hand any time.
set -euo pipefail
cd "$(dirname "$0")"

SCRATCH="$(mktemp -t seatback-raw-scrape)"
LOG="$(mktemp -t seatback-scrape-log)"
trap 'rm -f "$SCRATCH" "$LOG"' EXIT

git pull --rebase --quiet

python3 lb_detail_scrape.py > "$SCRATCH" 2>"$LOG"
n=$(wc -l < "$SCRATCH" | tr -d ' ')

# Absolute floor catches a totally-blocked scrape (0 titles). But
# 2026-07-26 showed that's not enough on its own: page 2 of the
# Letterboxd pagination silently failed, page 1's ~100 titles cleared this
# floor easily, and a partial scrape got all the way to a real commit
# (dropped 89 titles). Also compare against the last known-good count —
# same ">20% shrink" threshold refresh-catalog.yml already uses for
# scores, applied here to membership.
if [ "$n" -lt 100 ]; then
  echo "Scrape returned only $n titles (expected ~190+) — looks broken, not pushing." >&2
  cat "$LOG" >&2
  exit 1
fi

if [ -f pipeline/raw_scrape.tsv ]; then
  prev_n=$(wc -l < pipeline/raw_scrape.tsv | tr -d ' ')
  threshold=$(( prev_n * 80 / 100 ))
  if [ "$prev_n" -gt 0 ] && [ "$n" -lt "$threshold" ]; then
    echo "Scrape returned $n titles, down from $prev_n (>20% drop) — looks like a partial/broken scrape, not pushing." >&2
    cat "$LOG" >&2
    exit 1
  fi
fi

if [ -f pipeline/raw_scrape.tsv ] && diff -q "$SCRATCH" pipeline/raw_scrape.tsv >/dev/null 2>&1; then
  echo "No change ($n titles)."
  exit 0
fi

cp "$SCRATCH" pipeline/raw_scrape.tsv
git add pipeline/raw_scrape.tsv
git commit -m "Update raw Letterboxd scrape ($(date -u +%Y-%m-%d), $n titles)" --quiet
git push --quiet
echo "Pushed updated scrape: $n titles."
