# Seatback Cinema — running TODO

Running list, updated as items close or new ones surface. See the latest
`SEATBACK-HANDOFF-*.md` for narrative context on any item below.

---

## Open

- [ ] **Gate scope decision (§6a of the 07-18 handoff).** The agreement gate
      currently overrides any M value. `verdict-debug.csv` shows 8 gated
      titles; 7 have M ≥ 40 (Inception 45.3, Moonlight 52.4, Dark Knight 52.3,
      One Battle 67.8, 3 Idiots 59.5, Puss in Boots 60.7, plus one more).
      Only **The Shawshank Redemption** (M = 19.5) would lose its "Loved by
      All" phrase if the gate were restricted to the `partial` band (M ≥ 40)
      only. Decide: keep gate unrestricted, or add the M ≥ 40 floor.
- [ ] **Push the gated `scoring.js` to Impure Cinema.** Same file, both
      deployments — otherwise the two apps disagree on the same film's
      verdict. Not yet done.
- [ ] **Decide the fate of `SeatbackCinema-preview.html`.** It's the old
      design mockup, not the deployed app. Currently sitting at repo root.
      Keep as a design reference or delete.
- [ ] **Delete dead CSS vars** `--plum-panned` / `--plum-mixed` in
      `index.html`. Pre-darkening leftovers; `tierColor()` in JS already uses
      the correct current values, so nothing renders wrong — just clutter.
- [ ] **Poster placeholder** is a plain bordered rectangle for titles with no
      poster (currently 1 title: "2025 Masters Official Film"). Could carry
      the Seatback mark instead.
- [ ] **Stale docs to update** — `SEATBACK-ISSUES.md` (close the 3
      live-verification items + correct the thin-tail estimate from ~8-10 to
      1), `SEATBACK-FUNCTIONAL-PLAN.md` (mark Phase 1 + PWA phase done),
      `SEATBACK-CINEMA-IDENTITY.md` §5 (icon treatment closed), `SPEC.md` /
      Impure Cinema docs (record the agreement gate). None of these docs
      currently exist in this folder — confirm where they actually live
      before editing.
- [ ] **Decide where the non-deploy pipeline scripts belong** —
      `catalog-ops.html`, `delta_ic_match.py`, `diag.py`, `lb_detail_scrape.py`,
      `overrides.csv`, `overrides.numbers`, `probe_mi.js`, `sync_catalog.py`,
      `titles.tsv`, `titles_with_years.tsv`, `triage.py`. Currently at repo
      root; not part of `DEPLOY.md`'s repo tree. Fine as-is, but worth a
      deliberate call (e.g., a `matching/` folder) rather than leaving it
      implicit — more pressing now that CI (not just local runs) depends on
      these paths, so a move means updating the workflow files too.
- [ ] **Track ScraperAPI's real-world reliability and free-tier usage.**
      Switched the scrape to ScraperAPI 2026-07-27. Track record so far:
      2 clean manual tests (07-27), then the **first real scheduled
      (`schedule`-triggered, not manual) run on 07-28 failed** — ScraperAPI's
      own endpoint returned HTTP 500 three times in a row (not a
      Cloudflare-challenge marker, not an auth/quota error). Safety floor
      correctly refused at 0 titles, nothing shipped. A manual retry
      minutes later succeeded cleanly (189 titles, 0 flagged), confirming
      it was a transient ScraperAPI-side error, not a recurring block. 3 of
      4 real attempts have now passed. No code change made in response to a
      single transient 500 — keep watching for a pattern before reacting.
      Also still worth checking free-tier usage stays comfortably inside
      1,000 credits/month (expected ~90/month at 1 request/day, more on
      days sync-catalog.yml is manually re-run).
- [ ] **Keep `catalog-ops.html` in sync with the published Artifact.** The
      committed copy is a point-in-time source snapshot, not a live link —
      if the published dashboard gets edited/republished in a future
      session, the repo copy needs updating separately or it'll drift.

## Reminders (standing, not one-time)

- **First real `last-updated.json` write is still pending.** It only gets
  created on the next `sync-catalog.yml` run where
  `titles_with_years.tsv`/`pipeline/matched.csv` actually change (see
  Done). Until then the app's "last updated" indicator stays hidden on a
  first-ever deploy where the file has never existed — that's expected,
  not a bug; confirm it appears correctly once a real membership change
  lands.

- **Bump `CACHE_VERSION` in `sw.js`** on any deploy that changes
  `index.html`, `scoring.js`, or the icons. `catalog.json` is exempt.
- **`scoring.js` is shared with Impure Cinema.** Any scoring change ships to
  both.

## Done

- [x] Agreement gate implemented in `scoring.js` and catalog rebuilt with it
      (verified: Dark Knight → "Loved by All", 8 titles gated).
- [x] `icon-maskable-512.png` generated from `icon.svg`, verified within the
      maskable safe zone.
- [x] Repo assembled per `DEPLOY.md` §1 (`index.html` rename, `pipeline/`,
      `.github/workflows/`).
- [x] GitHub repo created — [github.com/neilashah/seatback-cinema](https://github.com/neilashah/seatback-cinema)
      (public), pushed.
- [x] GitHub Pages enabled and live —
      [neilashah.github.io/seatback-cinema](https://neilashah.github.io/seatback-cinema/)
- [x] Live URL loads; offline mode verified (server killed, full catalog +
      posters rendered from service worker cache).
- [x] Three Actions secrets added (`TMDB_KEY`, `MDBLIST_KEY`,
      `TRAKT_CLIENT_ID`) — 2026-07-24.
- [x] Installed to phone home screen; icon and standalone launch confirmed —
      2026-07-24.
- [x] Cron timing set — `refresh-catalog.yml` now runs the 1st of each month
      at midnight and noon Eastern (`0 4,16 1 * *`, pinned to EDT; shifts to
      1am/1pm during EST) — 2026-07-24.
- [x] Catalog-membership watcher built — `watch_catalog.py` +
      `.github/workflows/watch-catalog.yml`, runs daily, scrapes only the
      Letterboxd title list (no TMDB/MDBList/Trakt calls), diffs against
      committed `titles_with_years.tsv`, opens a `catalog-drift` GitHub
      issue on change (or `catalog-watch-broken` if the scrape itself looks
      broken). Verified locally against the live list — 2026-07-24.
      **Superseded 2026-07-25 — see below: it never actually worked in CI.**
- [x] Matching pipeline re-run to catch up with Delta's July 18 rotation —
      197 titles (23 added, 24 removed vs. the prior baseline), 195 auto +
      2 override, 0 left in review. Activated the staged `Protector` /
      `Tinā` overrides from the prior session (same TMDB ids the fresh match
      landed on independently). Committed, pushed, and confirmed CI run
      succeeded end-to-end (build → validate → commit → Pages redeploy) —
      live site verified serving 197 titles, Forrest Gump present, Fast Five
      gone — 2026-07-24.
- [x] List drifted again same day (Em updated it a second time, 23:47 UTC
      07-24) — caught via the watcher, re-synced to 189 titles (18 added, 26
      removed), added a bless override for "Ready or Not 2: Here I Come"
      (TMDB's own title omits the "2"), verified live — 2026-07-25.
- [x] Added a way to force-refresh the catalog from a standalone home-screen
      launch — a refresh button (bypasses the service worker's normal
      cache-first response via an X-Seatback-Refresh header, routed to a new
      network-first path in `sw.js`) plus a silent auto-recheck on
      visibilitychange/pageshow. `CACHE_VERSION` bumped to `v2`. Fixed the
      bug where reopening from the home screen icon had no way to pick up a
      newer catalog short of opening the site in Safari — 2026-07-25.
- [x] **Membership sync automated, then corrected after a real CI failure.**
      First version (`sync_catalog.py` scraping directly + `watch-catalog.yml`
      triggering it) looked right and got built and pushed, but a live test
      run of `sync-catalog.yml` immediately 403'd — and checking the history
      showed **both prior scheduled `watch-catalog.yml` runs (07-24, 07-25)
      had been silently 403'd too**, since day one. Letterboxd blocks
      requests from GitHub Actions runner IPs even with realistic browser
      headers; TMDB/MDBList/Trakt are unaffected. (The safety net worked as
      designed though — it correctly opened `catalog-watch-broken` issue #1
      on the first blocked run instead of misreporting a false catalog
      change, it just went unnoticed until this session's manual test.)
      Fixed by moving the scrape out of CI entirely: new `push_scrape.sh`
      runs locally (scheduled via launchd —
      `com.seatback-cinema.push-scrape.plist`, installed and loaded same
      session, see below), scrapes, and pushes `pipeline/raw_scrape.tsv`
      only when it changes. That push triggers `sync-catalog.yml` (now an
      `on: push` trigger instead of being called from a watcher), which does
      the TMDB match, commits clean-tier titles straight to `main`, triggers
      `refresh-catalog.yml`, and surfaces anything flagged as a
      `catalog-needs-review` issue. `watch_catalog.py` +
      `.github/workflows/watch-catalog.yml` deleted (their job — cheap
      diff-then-trigger — is now inherently handled by the push itself).
      `DEPLOY.md` §5 documents the corrected chain — 2026-07-25.
- [x] **Verified the corrected chain end-to-end for real.** Ran
      `push_scrape.sh` locally (189 titles, seeded `pipeline/raw_scrape.tsv`
      for the first time) — confirmed the push actually triggered
      `sync-catalog.yml` (`event: push`), which matched cleanly (189/189, 0
      flagged) and correctly found nothing new to commit since it already
      matched what was live. Closed issue #1 with the root-cause writeup.
      Installed the launchd schedule (`launchctl load`) — daily at 9am
      local from now on, no more manual/chat-triggered runs needed for the
      common case — 2026-07-25.
- [x] **Catalog Ops dashboard built** (`catalog-ops.html`, published as a
      claude.ai Artifact) — status strip (titles live, last scrape, last
      membership change, launchd status), a button to copy a ready-to-paste
      "run the scrape now" instruction, and a reconciliation section for
      flagged titles (bless a match / search TMDB / pin the correct id).
      Two real bugs found and fixed along the way, both worth remembering:
      1. Initial version used `sendPrompt()` assuming published Artifacts
         can message back into the chat that published them — they can't;
         that's a different tool's mechanism entirely. Rebuilt around
         copying a ready-to-paste instruction to the clipboard instead.
      2. The "Bless this match" button built its click handler as
         `onclick="sendAction(this, ${JSON.stringify(...)})"` — the JSON
         string's own double quotes closed the HTML attribute early,
         silently truncating it, so the button did nothing. Fixed by
         removing all inline `onclick`/`onsubmit` attributes and wiring
         every action via `addEventListener` after render instead, which
         sidesteps the whole bug class (no string ever round-trips through
         HTML attribute syntax).
      Also hardened the copy mechanism itself once live testing showed the
      async Clipboard API is blocked inside the published Artifact's
      sandbox (likely a Permissions-Policy restriction) — it now falls back
      to `execCommand('copy')` on a pre-selected text reveal, and if even
      that's blocked, honestly shows "Selected below — press ⌘C" rather
      than a false success or alarming failure state. `FLAGGED` data is a
      manually-maintained snapshot embedded at publish time, not live — see
      the Open item above about keeping it in sync — 2026-07-25.
- [x] **Live-tested the dashboard's copy button for real** — user pasted
      the copied instruction back into this chat, confirming the full
      loop works. Running it surfaced a genuine finding (see below).
- [x] **Diagnosed a Cloudflare JS challenge on the local scrape.**
      `push_scrape.sh` hit a 403 — but response headers showed
      `cf-mitigated: challenge` and a Cloudflare "Just a moment..." page,
      a fundamentally different mechanism from the GHA-IP-block issue (no
      plain HTTP client can pass a JS challenge, on any IP). Most likely
      cause: this session scraped the same Letterboxd list 6-8+ times in a
      few hours while building/testing, tripping Cloudflare's bot
      heuristics. Safety floor worked correctly (0 titles scraped, refused
      to push). Decided to wait and see whether tomorrow's normal
      once-daily 9am run goes through cleanly rather than react now — see
      Open item — 2026-07-25.
- [x] **Caught, reverted, and root-caused a real partial-scrape incident —
      2026-07-26.** (Separately, a different session this morning also
      diagnosed and fixed a macOS TCC permissions issue blocking launchd
      from touching `~/Desktop`, moving the whole project to
      `~/seatback-cinema` — see that commit's own message for the
      writeup.) Neil asked to test `push_scrape.sh` again: it got page 1
      (100 titles) but page 2 of the Letterboxd pagination silently
      failed, and 100 titles cleared the old fixed "≥100" safety floor
      easily. That went all the way to a real `sync-catalog.yml` commit on
      `main` dropping 89 titles — caught immediately by checking the CI
      run's own log (its "Trigger score refresh" step had failed, which is
      what prompted a closer look). Live `catalog.json` was never
      rebuilt/redeployed, so passengers were never served bad data.
      **Reverted** the bad commit (`git revert`) within minutes. While
      investigating, found and fixed a second, unrelated real bug:
      `sync-catalog.yml` was missing `actions: write` permission (added it
      to the old `watch-catalog.yml` last session, never to
      `sync-catalog.yml` itself), which is why "Trigger score refresh" had
      403'd. Fixed both: added the missing permission, and replaced the
      fixed-floor check with a percentage-based shrink check (>20% drop
      refuses to push/write) in both `push_scrape.sh` and, as an
      independent second layer, `sync_catalog.py` itself. Re-scraping
      immediately after got fully blocked again (0 titles) — see the Open
      item above, this is not resolved, just safer to fail into.
- [x] **Switched the Letterboxd scraper to a real browser (nodriver),
      2026-07-26.** Researched options for passing Cloudflare's
      Turnstile-based Managed Challenge (confirmed via response headers:
      `cf-mitigated: challenge`) — no plain HTTP client can execute JS, so
      headers/IP tricks were never going to be enough. Compared Nodriver,
      SeleniumBase UC Mode, Playwright+stealth, FlareSolverr, and
      cloudscraper; picked **Nodriver** (successor to
      `undetected-chromedriver`) as the best-maintained free option.
      Installed it, hit and fixed a real upstream packaging bug (a
      mis-encoded byte in nodriver 0.50.3's bundled `cdp/network.py` broke
      import entirely under Python 3.14's stricter source-encoding rules —
      documented the one-line fix in DEPLOY.md §5a). Tested headless vs.
      headful: headless still got challenged, **headful (a real, visible
      Chrome window) passed cleanly** across a live 2-page pagination test
      (100 + 89 = 189, matching the last known-good count exactly).
      Rewrote `lb_detail_scrape.py` around it — same CLI contract (stdout
      TSV, stderr progress), so `push_scrape.sh` needed zero changes. Bonus:
      the real rendered DOM exposes cleaner `data-item-name`/`data-item-slug`
      pairs than the old raw-HTML approach ever had, replacing a
      three-way alt-text/attribute/anchor fallback chain with one regex.
      Not a guaranteed fix — turned out to still be unreliable (see next
      two entries); superseded by the ScraperAPI switch below.
- [x] **nodriver's real track record: 2 passes out of 4 tries, then
      retired.** 2026-07-26: 2 clean passes back to back during initial
      testing, then 2 challenges that didn't clear later the same day
      (plausibly volume-driven from testing so much). 2026-07-27: checked
      whether the scheduled 9am `launchd` run had succeeded that morning —
      no new commit had landed all day, and `launchctl`/log evidence
      couldn't cleanly confirm whether the job had even fired. Ran
      `push_scrape.sh` manually as a fresh (non-testing-volume) data
      point — it failed too. 2 of 4 real attempts passed, roughly matching
      the 55-70% ceiling independent research found for even the best free
      tools against Turnstile. Decided this wasn't reliable enough and
      looked into paid alternatives instead of continuing to tune it.
- [x] **Switched to ScraperAPI, moved the scrape back into GitHub Actions,
      retired the local scraper entirely — 2026-07-27.** Confirmed the
      free tier's pricing/limits first (1,000 credits/month, recurring —
      this project's ~90 requests/month fits easily) before signing up.
      Tested directly against the real list before changing any code:
      clean 200 on the first attempt for both pages, 189/189 titles,
      matching the last known-good count exactly — no retries needed,
      unlike nodriver's 50/50 record. Rewrote `lb_detail_scrape.py` around
      a plain HTTPS call to ScraperAPI's API (`render=true`) instead of
      driving a local browser — simpler code, no more `nodriver`/Chrome
      dependency (uninstalled `nodriver` locally). Key insight that
      reshaped the whole architecture: since the actual Cloudflare bypass
      happens on ScraperAPI's infrastructure, not the caller's IP, the
      request can come from anywhere — including GitHub Actions. Rebuilt
      `sync-catalog.yml` to scrape + match + commit in one scheduled daily
      workflow (~9am Eastern), added `SCRAPERAPI_KEY` as a repo secret,
      and retired `push_scrape.sh` + the `launchd` job entirely (unloaded,
      uninstalled, deleted from the repo) — the whole reason they existed
      (Letterboxd blocking GHA IPs directly) is now moot, since ScraperAPI
      is what actually reaches Letterboxd. This also directly fixes the
      "laptop is often off in the morning" problem — the sync no longer
      depends on any local machine being on at all. DEPLOY.md §5/§5a
      rewritten for the new architecture.
- [x] **Three app-side improvements — 2026-07-28.**
      1. **"Last updated" indicator.** Deliberately tracks only real
         membership changes, not score refreshes or scrape/flag noise:
         `sync-catalog.yml`'s "Commit clean-tier titles" step now does a
         second, narrower diff check specifically on
         `titles_with_years.tsv`/`pipeline/matched.csv`, and only then
         writes root-level `last-updated.json`
         (`{"titlesUpdatedAt": "<UTC ISO8601>"}`) into the same commit.
         `sw.js` gives it the same stale-while-revalidate treatment as
         `catalog.json` (`CACHE_VERSION` bumped to `v3`); `index.html`
         fetches it alongside the catalog and shows "Catalog updated
         Jul 26" under the header, failing silently (indicator just stays
         hidden) if the file's ever missing or unreachable.
      2. **"Release Year" added to the sort menu** — a `year` entry in
         `SORT_OPTIONS` modeled directly on the existing `runtime` entry,
         newest-first, missing years sink to the bottom. No other code
         changes needed; the sort sheet and comparator both already
         iterate `SORT_OPTIONS` generically.
      3. **Folded Search into Browse.** Root cause of the width
         inconsistency Neil noticed: `#results` had its own padding rule,
         `#searchResults`/`#newResults` had none at all (0px, flush to the
         app edge). Rather than patch the CSS, removed the Search tab
         entirely — the search field now lives permanently in the Browse
         pane, `applyFiltersToResults()` gained a title-match predicate
         alongside the existing filter-chip logic (one render path
         instead of two), and `#results`/`#newResults` now share a
         `.result-list` class so New This Month's padding is fixed too as
         part of the same change. `renderSearch()` and `#searchPane`
         deleted outright.
      Verified all three in a real browser (local dev server + Browser
      pane) before committing: search-in-Browse with highlighting intact,
      combined filter+search empty states, Release Year sort ordering,
      New This Month's padding now matching Browse, no console errors.
