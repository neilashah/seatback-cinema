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

## 5. The membership sync (`push_scrape.sh` → `sync-catalog.yml`)

Adding/removing titles used to be a fully manual step (re-run the scrape,
re-run the TMDB matcher, eyeball the output, commit). It's now mostly
automated, in two stages that deliberately run in different places:

1. **`push_scrape.sh` runs locally** (your machine, on a schedule via
   launchd — see `com.seatback-cinema.push-scrape.plist`), because it has
   to: **Letterboxd blocks GitHub Actions runner IPs with a 403**, even with
   realistic browser headers (confirmed 2026-07-25 — both scheduled
   `watch-catalog.yml` runs and a manual `sync-catalog.yml` run all got
   blocked immediately). TMDB/MDBList/Trakt are unaffected; this is
   Letterboxd-specific. The script scrapes the list, and if it differs from
   the committed `pipeline/raw_scrape.tsv`, commits and pushes just that
   file. Two safety checks refuse to push a broken scrape: an absolute
   floor (fewer than 100 titles) and a percentage check against the last
   known-good count (>20% shrink) — added 2026-07-26 after a partial scrape
   (100 titles from page 1 only, page 2 silently failed) cleared the old
   fixed floor and actually shipped a shrunk catalog for a few minutes
   before being caught and reverted. See §5a for why the scraper itself
   changed that same day.
2. **That push triggers `sync-catalog.yml`** (a GitHub Actions `on: push`
   trigger, scoped to `pipeline/raw_scrape.tsv`), which runs the TMDB match
   (`overrides.csv` still applies first) and **splits the result**: titles
   that matched cleanly (`auto`/`override` tier) are committed straight to
   `titles_with_years.tsv` + `matched.csv` on `main`, which then triggers
   `refresh-catalog.yml` to rebuild `catalog.json` and redeploy — no human
   step at all for the common case. Titles the matcher wasn't confident
   about (`review`/`fuzzy`/`miss` tier — a remake collision, no year to
   disambiguate, nothing plausible on TMDB) are held *out* of the catalog
   entirely and surfaced as a `catalog-needs-review` GitHub issue instead,
   so a bad guess can't ship unreviewed. They keep reappearing on every
   future sync until an `overrides.csv` entry resolves them — add a line
   there (see the file's own header for the format) and the next sync picks
   it up cleanly. `sync-catalog.yml` also has `workflow_dispatch` for an
   on-demand run against whatever's already in `pipeline/raw_scrape.tsv`.

The old fully-manual path (`python3 lb_detail_scrape.py > titles_with_years.tsv`
then `python3 delta_ic_match.py titles_with_years.tsv > pipeline/matched.csv`)
still works if you want a full title-by-title look before shipping — nothing
about it changed. `sync_catalog.py` is the matching half of that same
pipeline with the clean/flagged split layered on top, just reading
`pipeline/raw_scrape.tsv` instead of re-scraping itself; its docstring has
the exact logic and a couple of known edge cases worth knowing about.

### 5a. Why `lb_detail_scrape.py` drives a real browser

Realistic headers got requests past Letterboxd for a while, but Letterboxd
sits behind Cloudflare, and Cloudflare's Turnstile-based Managed Challenge
(confirmed via response headers 2026-07-25/26 — `cf-mitigated: challenge`,
a "Just a moment..." interstitial) requires actually executing JavaScript
to pass. No plain HTTP client can do that, on any IP, once it's triggered.

`lb_detail_scrape.py` now drives a real Chrome via
[nodriver](https://github.com/UltrafunkAmsterdam/nodriver) (successor to
`undetected-chromedriver`), **in headful mode** — `headless=True` still got
challenged in testing, `headless=False` (a real, visible window) passed
consistently. Expect a Chrome window to briefly appear during the
scheduled scrape; that's normal, not a bug.

**Not 100% reliable.** Even the best current free tools against Turnstile
land around 55-70% success in independent testing — this is a real
ceiling, not a bug in this setup. Confirmed empirically 2026-07-26: two
clean passes back to back, then two challenges that didn't clear, quite
possibly worsened by how much this exact URL got hit that same day testing
it. The existing safety floors (§5) mean a failed/challenged run is
harmless — it just skips that day's sync — so this is an acceptable
trade, not a blocker. If reliability becomes a real problem, a paid
anti-bot API (ScraperAPI, ZenRows, Bright Data Web Unlocker) is the
fallback that was deliberately not chosen here (cost/complexity vs. a
once-daily personal scrape).

**Setup:** `pip install nodriver`, plus a real Chrome install (not just
Chromium) for it to drive. Known packaging bug in nodriver 0.50.3: a
mis-encoded byte in its bundled `cdp/network.py` (`\xb1Inf` in a comment)
throws a `SyntaxError` on import under Python 3.14's stricter
source-encoding handling. If you hit this, patch the installed file
(check whether a newer nodriver release has fixed it first):

```
python3 -c "
p = '<path to>/site-packages/nodriver/cdp/network.py'
d = open(p, 'rb').read()
open(p, 'wb').write(d.replace(b'\xb1Inf', b'+/-Inf'))
"
```

### Installing the local schedule

`com.seatback-cinema.push-scrape.plist` is a launchd job template (daily,
9am local by default — edit the `Hour`/`Minute` keys to change it). To
activate it:

```
cp "com.seatback-cinema.push-scrape.plist" ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.seatback-cinema.push-scrape.plist
```

launchd only fires while the machine is awake; a missed run (asleep/off at
9am) generally catches up shortly after wake, but isn't guaranteed. To stop
it: `launchctl unload ~/Library/LaunchAgents/com.seatback-cinema.push-scrape.plist`.
Logs land at `/tmp/seatback-push-scrape.log`. The script is also just a
normal shell script — running it by hand any time is fine.

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
