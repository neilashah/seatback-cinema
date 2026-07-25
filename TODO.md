# Seatback Cinema — running TODO

Running list, updated as items close or new ones surface. See the latest
`SEATBACK-HANDOFF-*.md` for narrative context on any item below.

---

## Open

- [ ] **Watch for repeat Cloudflare challenges on the local scrape.**
      `push_scrape.sh` hit an HTTP 403 on 2026-07-25 — but this one wasn't
      the GHA-IP-block issue (that's fixed); the response headers showed
      `cf-mitigated: challenge` and a Cloudflare "Just a moment..."
      interstitial, which no plain HTTP client can pass regardless of IP or
      headers. Very likely triggered by this session's unusually heavy
      testing volume that day (6-8+ scrapes of the same list in a few
      hours) tripping Cloudflare's bot heuristics, not a standing block —
      the safety floor correctly refused to push (0 titles scraped). Left
      to self-resolve; check whether the next scheduled 9am launchd run
      goes through cleanly. If this recurs on a normal once-daily cadence
      (not heavy testing), that's a real signal and would need a more
      robust scraper (e.g. headless-browser-based, to actually execute the
      JS challenge) rather than waiting it out.
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
      `overrides.csv`, `overrides.numbers`, `probe_mi.js`, `push_scrape.sh`,
      `sync_catalog.py`, `titles.tsv`, `titles_with_years.tsv`, `triage.py`.
      Currently at repo root; not part of `DEPLOY.md`'s repo tree. Fine
      as-is, but worth a deliberate call (e.g., a `matching/` folder) rather
      than leaving it implicit — more pressing now that CI (not just local
      runs) depends on these paths, so a move means updating the workflow
      files too.
- [ ] **Keep `catalog-ops.html` in sync with the published Artifact.** The
      committed copy is a point-in-time source snapshot, not a live link —
      if the published dashboard gets edited/republished in a future
      session, the repo copy needs updating separately or it'll drift.

## Reminders (standing, not one-time)

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
