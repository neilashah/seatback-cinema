# Seatback Cinema — deployment

Static site on **GitHub Pages**, with scores precomputed into `catalog.json`
by `build_catalog.js`. No proxy, no server, no API keys in anything shipped to
the browser — the keys only ever live in GitHub Actions secrets and on your
laptop.

---

## 1. Repo layout

```
/
  index.html                  <- SeatbackCinema.html, RENAMED
  scoring.js                  <- shared engine (same file Impure Cinema uses)
  catalog.json                <- generated; committed
  sw.js
  manifest.webmanifest
  icon-192.png
  icon-512.png
  icon-maskable-512.png
  apple-touch-icon.png
  icon.svg                    <- editable icon source (not served)

  pipeline/
    build_catalog.js
    matched.csv               <- from delta_ic_match.py
    new_this_month.txt        <- optional: one TMDB id per line -> "New" pill
    verdict-debug.csv         <- generated sidecar, for calibration

  .github/workflows/
    refresh-catalog.yml
```

**The rename to `index.html` is required.** `sw.js` precaches `./index.html`
for offline navigation; leave the file named `SeatbackCinema.html` and offline
launches will fail.

`scoring.js` stays at the repo root and is used by *both* the browser app and
the pipeline (the workflow passes `SCORING_PATH=../scoring.js`). One engine,
one copy — that's the point.

---

## 2. Turn on GitHub Pages

1. Push the repo to GitHub.
2. **Settings → Pages**
3. **Source:** "Deploy from a branch"
4. **Branch:** `main`, folder `/ (root)` → Save

The site appears at `https://<user>.github.io/<repo>/` within a minute or two.
Every push to `main` redeploys, which is how the refresh workflow publishes.

Two things that matter here:

- **HTTPS is required for service workers.** GitHub Pages is HTTPS by default,
  so this works — but `file://` never will. Local testing needs a server:
  `python3 -m http.server` in the repo folder, then `localhost:8000`.
- **Project subpaths are fine.** Everything uses relative paths, so serving
  from `/<repo>/` rather than a domain root needs no changes.

---

## 3. Add the API keys as secrets

**Settings → Secrets and variables → Actions → New repository secret**, three
times:

| Name | Value |
|---|---|
| `TMDB_KEY` | your TMDB v3 key |
| `MDBLIST_KEY` | your MDBList key |
| `TRAKT_CLIENT_ID` | your Trakt client id |

Same values you used locally. Secrets are write-only once saved — GitHub will
never show them back to you, so keep your own copy.

---

## 4. The refresh workflow

`refresh-catalog.yml` runs on the **1st of each month at midnight and noon
Eastern**, and can be triggered by hand from the **Actions** tab
(`workflow_dispatch`) any time.

What it does: rebuilds `catalog.json` from the committed `matched.csv`,
validates it, commits, and Pages redeploys.

**What it deliberately does not do: change which films are in the catalog.**
That's `sync-catalog.yml`'s job (§5 below) — this workflow only refreshes
scores for titles already in `matched.csv`.

- **Scores** — automated, twice on the 1st of each month.
- **Membership** — automated for anything that matches TMDB cleanly (see
  §5); a human is only needed for titles the matcher itself flags as
  ambiguous.

### Stale-fallback

The workflow validates before publishing and **refuses to commit** if:

- fewer than 50 titles, or
- the catalog shrank more than 20% versus the live one, or
- fewer than half the titles scored (which means the APIs were failing)

If validation fails, nothing is committed and the previously deployed
`catalog.json` stays live. Passengers get last cycle's data instead of an empty
app. The run shows as failed in the Actions tab so you know to look.

`verdict-debug.csv` is uploaded as a build artifact on every run, pass or fail
— that's your calibration record if a verdict ever looks wrong.

### About the cron time

Actions cron is **always UTC and does not follow daylight saving**, so a
fixed-UTC schedule drifts by one hour twice a year relative to local time.
`0 4,16 1 * *` is pinned to EDT (UTC-4): midnight and noon Eastern. During
EST (roughly early Nov - mid March) that lands at 1am/1pm Eastern instead —
shift both hours back by one (`0 3,15 1 * *`) for that stretch if exact local
time matters, or just accept the seasonal drift. If you want the *catalog*
refresh timed to Delta's monthly rotation rather than a fixed date, that's
worth checking against when new titles actually appear.

Also note: scheduled workflows on free runners can start late (queueing), and
GitHub disables schedules in repos with no activity for 60 days. A manual run
from the Actions tab resets that clock.

---

## 5. The membership sync (`sync-catalog.yml`)

Adding/removing titles used to be a fully manual step (re-run the scrape,
re-run the TMDB matcher, eyeball the output, commit). It's now fully
automated, running daily (~9am Eastern, `workflow_dispatch` also available
for an on-demand run) entirely in GitHub Actions:

1. **Scrapes the Letterboxd list** (`lb_detail_scrape.py`) via
   [ScraperAPI](https://scraperapi.com) — see §5a for why a plain request
   can't do this directly. Two safety checks refuse to proceed on a broken
   scrape: an absolute floor (fewer than 100 titles) and a percentage
   check against the last known-good count (>20% shrink).
2. **Matches every title against TMDB** (`sync_catalog.py`, `overrides.csv`
   applies first) and **splits the result**: titles that matched cleanly
   (`auto`/`override` tier) are committed straight to `titles_with_years.tsv`
   + `matched.csv` on `main`, which then triggers `refresh-catalog.yml` to
   rebuild `catalog.json` and redeploy — no human step at all for the
   common case. Titles the matcher wasn't confident about
   (`review`/`fuzzy`/`miss` tier — a remake collision, no year to
   disambiguate, nothing plausible on TMDB) are held *out* of the catalog
   entirely and surfaced as a `catalog-needs-review` GitHub issue instead,
   so a bad guess can't ship unreviewed. They keep reappearing on every
   future sync until an `overrides.csv` entry resolves them — add a line
   there (see the file's own header for the format) and the next sync
   picks it up cleanly.

The old fully-manual path (`python3 lb_detail_scrape.py > titles_with_years.tsv`
then `python3 delta_ic_match.py titles_with_years.tsv > pipeline/matched.csv`)
still works if you want a full title-by-title look before shipping — nothing
about it changed, though `lb_detail_scrape.py` now needs `SCRAPERAPI_KEY`
set (see §5a). `sync_catalog.py` is the matching half of that same
pipeline with the clean/flagged split layered on top, just reading
`pipeline/raw_scrape.tsv` instead of re-scraping itself; its docstring has
the exact logic and a couple of known edge cases worth knowing about.

**History, briefly** (full story in `TODO.md` if you want the blow-by-blow):
this used to run in two stages in two different places — a local script
(`push_scrape.sh`) scheduled via `launchd` did the scrape, because
Letterboxd blocks GitHub Actions runner IPs directly with a 403, and its
push triggered this workflow to do everything else. That local scraper
first used plain HTTP requests, then a real headful Chrome (`nodriver`)
once Cloudflare's Managed Challenge made plain requests stop working
reliably — but the headful-Chrome approach itself proved unreliable (see
§5a) and meant the whole sync depended on a laptop being on and awake at
9am. Switching to ScraperAPI (2026-07-27) fixed both problems at once:
their infrastructure handles the actual Cloudflare bypass, so the request
can come from anywhere — including this workflow, right here in CI. The
local script and `launchd` job are retired.

### 5a. Why the scrape goes through ScraperAPI

Letterboxd sits behind Cloudflare, and Cloudflare's Turnstile-based
Managed Challenge (confirmed via response headers 2026-07-25/26 —
`cf-mitigated: challenge`, a "Just a moment..." interstitial) requires
actually executing JavaScript to pass. No plain HTTP client can do that,
on any IP, once it's triggered — a real local headful Chrome (via
`nodriver`) got past it sometimes (2 clean passes in initial testing) but
not reliably (2 later failures the same day, then another the day after) —
roughly matching the 55-70% success ceiling independent research found for
even the best free anti-bot tools against Turnstile. It also only ran
locally, tying the whole sync to a laptop being on.

[ScraperAPI](https://scraperapi.com) handles the Cloudflare bypass on
*their* infrastructure — `lb_detail_scrape.py` just makes a plain HTTPS
request to their API with the target URL as a parameter (`render=true`),
and they return the final rendered HTML. Confirmed clean on the first
attempt for both pages of this list (2026-07-27), 189/189 titles, no
retries needed. Bonus: the rendered DOM exposes cleaner data than the old
raw-HTML approach ever had — `data-item-name` carries "Title (Year)" and
`data-item-slug` sits on the same tag, replacing a three-way
alt-text/attribute/anchor fallback chain with one regex.

**Setup:** sign up at [scraperapi.com](https://scraperapi.com) (free tier:
1,000 credits/month, recurring — this project's volume, ~3 requests/day,
fits comfortably inside it) and set the API key as the `SCRAPERAPI_KEY`
secret (`gh secret set SCRAPERAPI_KEY`, or via the repo's Settings →
Secrets page). For a local/manual run, `export SCRAPERAPI_KEY=...` first.

Not guaranteed to be 100% reliable forever, but categorically different
from the local-browser approach: the bypass work happens on ScraperAPI's
side regardless of where the request comes from, so there's no "did my
laptop happen to be awake" variable anymore, and no local Chrome/nodriver
dependency. If this ever becomes unreliable, the fallback is a
higher-tier ScraperAPI plan or a comparable service (ZenRows, Bright Data
Web Unlocker) — not a return to local scraping.

---

## 6. Deploy checklist

- [ ] `SeatbackCinema.html` renamed to `index.html`
- [ ] `scoring.js` at root is the **agreement-gate version**
- [ ] `catalog.json` generated with that same `scoring.js` and committed
- [ ] `pipeline/matched.csv` committed
- [ ] Three secrets added
- [ ] Pages enabled on `main` / root
- [ ] Loaded the live URL once, then tested offline (DevTools → Network →
      Offline → reload) — the full catalog should still render
- [ ] Installed to a phone home screen and checked the icon and standalone launch

---

## 7. Two things to remember later

**Bump `CACHE_VERSION` in `sw.js`** on any deploy that changes `index.html`,
`scoring.js`, or the icons. Otherwise returning visitors keep serving the old
cached shell. `catalog.json` is exempt — it uses stale-while-revalidate, so
refreshes land on their own.

**`scoring.js` is shared with Impure Cinema.** A scoring change must be pushed
to *both* deployments, or the two apps will report different verdicts for the
same film. The agreement gate is exactly such a change.
