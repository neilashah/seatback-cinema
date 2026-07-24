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

`refresh-catalog.yml` runs on the **1st and 15th at 09:00 UTC**, and can be
triggered by hand from the **Actions** tab (`workflow_dispatch`) any time.

What it does: rebuilds `catalog.json` from the committed `matched.csv`,
validates it, commits, and Pages redeploys.

**What it deliberately does not do: change which films are in the catalog.**
Adding/removing titles means re-running the Letterboxd scrape and the TMDB
matcher, and matching has a manual review step (`overrides.csv` — 2 of 198
needed hand-matching last time). Automating that would let a bad match go live
unreviewed. So the split is:

- **Scores** — automated, twice monthly. Safe: same titles, fresh numbers.
- **Membership** — manual, when Delta rotates the catalog. Run the Python
  pipeline locally, review the matches, commit the new `matched.csv`, then hit
  "Run workflow" to rescore.

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

Actions cron is **always UTC and does not follow daylight saving**, so a local
hour drifts by one hour twice a year. `0 9 1,15 * *` is 09:00 UTC. If you'd
rather it land at a specific local hour, adjust the hour field — and if you
want the *catalog* refresh timed to Delta's monthly rotation rather than a
fixed date, that's worth checking against when new titles actually appear.

Also note: scheduled workflows on free runners can start late (queueing), and
GitHub disables schedules in repos with no activity for 60 days. A manual run
from the Actions tab resets that clock.

---

## 5. Deploy checklist

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

## 6. Two things to remember later

**Bump `CACHE_VERSION` in `sw.js`** on any deploy that changes `index.html`,
`scoring.js`, or the icons. Otherwise returning visitors keep serving the old
cached shell. `catalog.json` is exempt — it uses stale-while-revalidate, so
refreshes land on their own.

**`scoring.js` is shared with Impure Cinema.** A scoring change must be pushed
to *both* deployments, or the two apps will report different verdicts for the
same film. The agreement gate is exactly such a change.
