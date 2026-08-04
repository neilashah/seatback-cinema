# Seatback Cinema — deployment

Static site on **GitHub Pages**, with scores precomputed into `catalog.json`
by `build_catalog.js`. No proxy, no server, no API keys in anything shipped to
the browser — the keys only ever live in GitHub Actions secrets and on your
laptop.

---

## 1. Repo layout

```
/
  index.html                  <- the app (passenger-facing)
  curator.html                <- manual add/remove admin page (§8) — private, unlinked
  catalog-ops.html            <- read-only sync/review dashboard
  scoring.js                  <- shared engine (same file Impure Cinema uses)
  catalog.json                <- generated; committed
  curation.csv                <- manual pins/blocklist (§8); survives every rebuild
  overrides.csv               <- TMDB match corrections for scraped titles
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
    sync-catalog.yml
```

`sw.js` precaches `./index.html` for offline navigation, so the app shell
must be named `index.html` at the repo root — this is already the case.

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

What it does: rebuilds `catalog.json` from the committed `matched.csv`
**merged with `curation.csv`** (manual pins/blocklist — see §8), validates
the result, commits, and Pages redeploys.

- **Scores** — automated, twice on the 1st of each month.
- **Membership** — automated for anything that matches TMDB cleanly (see
  §5); a human is only needed for titles the matcher itself flags as
  ambiguous, or for one-off adds/removes made by hand via `curator.html`
  (§8).

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
automated, running Mon/Wed/Fri (~9am Eastern, `workflow_dispatch` also
available for an on-demand run) entirely in GitHub Actions:

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

**Why Mon/Wed/Fri and not daily:** the scrape isn't free — see §5b. The
list itself also moves much more slowly than daily; if you know Em just
updated it, fire a `workflow_dispatch` rather than waiting.

**On `last-updated.json`:** the app's "last updated" indicator is meant to
tell a passenger that the *film list* changed, not that a score moved. The
workflow only touches it when `pipeline/membership_changed.py` says the
membership actually differs. That script exists because the obvious check —
`git diff` on `matched.csv` — is wrong: that file carries TMDB's
`popularity` column, which TMDB re-scores daily, so it changed on nearly
every run (the 2026-08-04 sync rewrote 179 of 189 rows with nothing but
popularity drift) and the indicator claimed a fresh list every day while
membership had been static since 2026-07-26. The script compares only the
columns that decide what ships (`tmdb_id`, `raw_title`, `confidence` — what
`build_catalog.js` actually reads); if you add a column that affects
catalog contents, add it to `SIGNIFICANT` there too.

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
1,000 credits/month, recurring — see §5b for what that actually buys) and
set the API key as the `SCRAPERAPI_KEY` secret (`gh secret set
SCRAPERAPI_KEY`, or via the repo's Settings → Secrets page). For a
local/manual run, `export SCRAPERAPI_KEY=...` first.

Not guaranteed to be 100% reliable forever, but categorically different
from the local-browser approach: the bypass work happens on ScraperAPI's
side regardless of where the request comes from, so there's no "did my
laptop happen to be awake" variable anymore, and no local Chrome/nodriver
dependency. If this ever becomes unreliable, the fallback is a
higher-tier ScraperAPI plan or a comparable service (ZenRows, Bright Data
Web Unlocker) — not a return to local scraping.

### 5b. What the scrape costs

**A JS-rendered ScraperAPI request costs 10 credits, not 1.** Every fetch
in `lb_detail_scrape.py` sets `render=true` (it has to — that's what clears
the Cloudflare challenge), so the free tier's 1,000 credits/month is a
budget of **~100 requests/month**, not ~1,000. Both
[ScraperAPI's credits docs](https://docs.scraperapi.com/credits-and-requests)
and its [JS-rendering cost page](https://docs.scraperapi.com/faq/js-rendering/extra-javascript-rendering-costs)
spell this out; premium/ultra-premium proxies would cost 25/75 instead, but
we don't pass those.

Current budget: 189 titles = 2 pages = 2 requests = **20 credits per sync**.
At Mon/Wed/Fri that's ~13 syncs/month ≈ **260 credits, ~26%** of the tier,
leaving headroom for manual dispatches and retries.

This section exists because the numbers here were wrong until 2026-08-04,
and the account tripped a 70%-usage warning as a result. Two compounding
mistakes, both now fixed:

- These docs and `lb_detail_scrape.py` both claimed "~3 requests/day fits
  comfortably" in the free tier. That assumed **1 credit per request** and
  so understated the real cost by 10x — daily syncing alone was ~910
  credits/month, ~91% of the allowance.
- The paging loop stopped only when a page came back with nothing new, so
  every run paid for one extra empty page — a third of the cost, for
  nothing. It now stops on a short page (`PAGE_SIZE` in that file), which
  is what dropped a sync from 3 requests to 2.

Worth knowing when debugging a bad day: `fetch()` retries up to 3 times per
page, so a run against a flaky ScraperAPI can cost several times the
nominal 20 credits. If usage ever needs cutting further, the next lever is
schedule frequency — the per-run cost is already at its floor of one
request per real page.

---

## 8. Manual curation (`curator.html`)

For a one-off add or remove that shouldn't wait on the Letterboxd scrape —
you spot something on a subreddit, a Letterboxd list we don't track, or
mid-flight on the actual seatback screen — `curator.html` is a private admin
page, unlinked from the app and `manifest.webmanifest`, but publicly
reachable at its URL (it's inert without your own credentials, so that's
fine).

**What it does:** searches TMDB by title, and lets you stage adds/removes
against `curation.csv` (root — see the file's own header comment for the
exact schema). "Commit & rebuild" writes `curation.csv` via the GitHub
Contents API in one commit, then dispatches `refresh-catalog.yml` so the
change is live in a few minutes — `build_catalog.js` merges `matched.csv`
with `curation.csv` (adds injected, blocklisted ids filtered, remove wins on
conflict) before scoring. `curation.csv` isn't touched by `sync-catalog.yml`,
so a manual entry survives the daily scrape indefinitely, until you undo it
from the same page.

**One-time setup, in the page itself:**

1. Create a **fine-grained personal access token** at
   [github.com/settings/personal-access-tokens/new](https://github.com/settings/personal-access-tokens/new),
   scoped to just this repo, with **Contents: Read and write** and
   **Actions: Read and write** permissions. Set an expiry.
2. Grab your **TMDB API key** (the "API Key" field, not the Read Access
   Token) from [themoviedb.org/settings/api](https://www.themoviedb.org/settings/api).
3. Paste both into the page's setup gate. They're stored only in that
   browser's `localStorage` — never sent anywhere but GitHub's and TMDB's
   own APIs, directly from the page.

**Mass removals:** blocklisting more than ~20% of the catalog in one commit
trips `refresh-catalog.yml`'s shrink guard (§4) and the rebuild is refused —
by design, to stop a mistake from gutting the live catalog. Batch large
removals across a couple of commits, or bypass the guard by hand for a
deliberate one-time cleanup.

**Testing changes safely:** open `curator.html?branch=<some-test-branch>`
(after creating that branch on GitHub) to point every write at the test
branch instead of `main` — commits land there, and the rebuild dispatch is
automatically skipped, so nothing touches the live site.

---

## 9. Deploy checklist

- [ ] `scoring.js` at root is the **agreement-gate version**
- [ ] `catalog.json` generated with that same `scoring.js` and committed
- [ ] `pipeline/matched.csv` committed
- [ ] Three secrets added
- [ ] Pages enabled on `main` / root
- [ ] Loaded the live URL once, then tested offline (DevTools → Network →
      Offline → reload) — the full catalog should still render
- [ ] Installed to a phone home screen and checked the icon and standalone launch

---

## 10. One thing to remember later

**`scoring.js` is shared with Impure Cinema.** A scoring change must be pushed
to *both* deployments, or the two apps will report different verdicts for the
same film. The agreement gate is exactly such a change.

(`sw.js` has no `CACHE_VERSION` to bump — every cache name is stable and every
request self-revalidates against the network, so a changed `index.html`,
`scoring.js`, or icon reaches returning visitors on their next fetch without
any manual step.)
