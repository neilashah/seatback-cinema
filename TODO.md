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
      `delta_ic_match.py`, `diag.py`, `lb_detail_scrape.py`, `overrides.csv`,
      `overrides.numbers`, `probe_mi.js`, `titles.tsv`,
      `titles_with_years.tsv`, `triage.py`. Currently at repo root; not part
      of `DEPLOY.md`'s repo tree. Fine as-is, but worth a deliberate call
      (e.g., a `matching/` folder) rather than leaving it implicit.

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
- [x] Matching pipeline re-run to catch up with Delta's July 18 rotation —
      197 titles (23 added, 24 removed vs. the prior baseline), 195 auto +
      2 override, 0 left in review. Activated the staged `Protector` /
      `Tinā` overrides from the prior session (same TMDB ids the fresh match
      landed on independently). Committed, pushed, and confirmed CI run
      succeeded end-to-end (build → validate → commit → Pages redeploy) —
      live site verified serving 197 titles, Forrest Gump present, Fast Five
      gone — 2026-07-24.
