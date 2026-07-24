# Seatback Cinema — Handoff 2026-07-24 03:19

**Supersedes:** `SEATBACK-HANDOFF-2026-07-24-0233.md`

**Status:** Live and current. The two open items from the 0233 handoff
("decide cron timing", "trigger refresh-catalog.yml once") are both closed
this session, and the catalog has been caught up with Delta's latest
rotation. Remaining work is unchanged from `TODO.md` — nothing urgent is
outstanding.

---

## 1. What this session did

1. **Cron timing decided and set.** Neil chose the 1st of each month,
   midnight and noon **Eastern**. Since Actions cron is UTC-only and ignores
   DST, this is pinned to EDT: `0 4,16 1 * *` (04:00/16:00 UTC). During EST
   (roughly early Nov – mid March) that lands at 1am/1pm Eastern instead —
   noted in both `refresh-catalog.yml` and `DEPLOY.md` §4, with the
   EST-equivalent cron string (`0 3,15 1 * *`) given as a swap-in if exact
   local time ever matters enough to flip twice a year.
2. **Built a catalog-membership watcher** — the score-refresh workflow
   deliberately never adds/removes titles (matching needs manual review), so
   nothing was watching for Delta actually rotating the catalog. New:
   - `watch_catalog.py` — reuses `lb_detail_scrape.py`'s fetch/extract,
     scrapes the Letterboxd list, diffs title names against the committed
     `titles_with_years.tsv`. No TMDB/MDBList/Trakt calls, so it's cheap
     enough to run daily. Exit 0 (no change) / 1 (drift — diff printed) / 2
     (scrape looks broken — far fewer titles than baseline, e.g. a 403 or
     markup shift, reported separately so it isn't mistaken for a real
     catalog change).
   - `.github/workflows/watch-catalog.yml` — runs daily at 13:00 UTC, opens
     a `catalog-drift` GitHub issue on change (or `catalog-watch-broken` on
     a suspected scrape failure), labels auto-created on first run, won't
     duplicate an issue that's already open.
   - Found by inspecting the list page's own markup: Letterboxd exposes the
     list's `Published`/`Updated` timestamps directly
     (`<span class="updated">Updated <time datetime="...">`). Delta's list
     was last updated **2026-07-18T11:15 UTC**. That timestamp is a cheaper
     drift signal than a full title diff, but Neil chose to keep the
     full-diff approach since it also produces the added/removed list for
     free — worth revisiting only if API load ever becomes a concern.
3. **Ran the matching pipeline** to catch up with that July 18 rotation:
   - Re-scraped: 197 titles (was 198).
   - `TMDB_KEY` wasn't available locally (it only lived in the GitHub
     Actions secret, which GitHub never displays again after saving — normal
     behavior, not a lost key). Neil retrieved it from TMDB's own account
     settings and pasted it in chat; it was exported for the one matching
     run and never written to any file or log.
   - Matched: 195 auto, 2 override, 0 review, 0 fuzzy, 0 miss. The 2 override
     hits (`Protector` → tmdb 1383731, `Tinā` → tmdb 1262426) were staged as
     commented-out "confirmed correct" entries in `overrides.csv` from a
     prior session; this run's fresh TMDB match independently landed on the
     identical ids, so they were activated (uncommented) rather than
     re-litigated.
   - Diff vs. the previous baseline: 23 added (Forrest Gump, Apollo 13,
     Deadpool, Elvis, Ocean's Eleven, Independence Day, and others), 24
     removed (Fast Five, Mad Max: Fury Road, Napoleon Dynamite, Hoosiers,
     and others) — matched the watcher's own diff exactly, a good
     cross-check that both tools agree.
4. **Committed, pushed, and triggered `refresh-catalog.yml` manually** (via
   `gh workflow run` — the gh CLI installed last session at
   `~/.local/gh-cli/gh_2.96.0_macOS_arm64/bin/gh` still works, still
   authenticated). Watched the run to completion: build → validate (197
   titles, 197 scored) → publish → Pages redeploy, all green. Verified
   **live**, not just in CI: fetched the deployed `catalog.json` directly
   and confirmed 197 titles, Forrest Gump present, Fast Five absent.
   - One hiccup: the CI run's own commit (`github-actions[bot]`, catalog
     scores) landed on `origin/main` while a local doc-only commit was being
     prepared, so a later `git push` was rejected (non-fast-forward). Fixed
     with `git pull --rebase` — clean, no conflicts, since the two commits
     touched disjoint files.

---

## 2. Current live state

- **Repo:** [github.com/neilashah/seatback-cinema](https://github.com/neilashah/seatback-cinema) (public, `main`)
- **Live site:** [neilashah.github.io/seatback-cinema](https://neilashah.github.io/seatback-cinema/) — verified serving the current 197-title catalog
- **`refresh-catalog.yml`** — 1st of month, 00:00/12:00 Eastern (pinned EDT), verified working end-to-end in CI (not just locally, for the first time)
- **`watch-catalog.yml`** — new, daily 13:00 UTC, not yet observed catching a real future drift (built and tested against the *current* known drift, which has since been resolved by the pipeline run above)
- **Catalog:** 197 titles, current as of Delta's 2026-07-18 rotation

---

## 3. What's next

Unchanged from `TODO.md` — see that file for the full itemized list. Nothing
from this session is blocking. Highest-value remaining items:

1. Decide the gate-scope question (§6a from the 07-18 handoff, still open —
   `verdict-debug.csv` has the numbers to decide with).
2. Push the same `scoring.js` to Impure Cinema so both apps agree.
3. Decide where the non-deploy pipeline scripts belong (currently at repo
   root, undecided whether that's deliberate or just how it landed).

---

## 4. Environment notes worth keeping

- `gh` CLI: `~/.local/gh-cli/gh_2.96.0_macOS_arm64/bin/gh`, authenticated as
  `neilashah`. Not on `PATH` by default in a fresh shell — prefix commands
  with `export PATH="$HOME/.local/gh-cli/gh_2.96.0_macOS_arm64/bin:$PATH"`.
- **`TMDB_KEY` is not stored anywhere locally.** It only exists as a GitHub
  Actions secret (write-only, unreadable via the UI or API) and in Neil's
  TMDB account settings. Running the matching pipeline locally requires
  asking Neil for it fresh each time, or having him run that step himself.
- `watch_catalog.py` imports directly from `lb_detail_scrape.py` (`from
  lb_detail_scrape import fetch, extract, LIST_URL`), so it must be run
  from the repo root where that file lives — same constraint the workflow's
  checkout already satisfies.
- `gh run watch <id>` is a local polling loop only — killing it does **not**
  cancel the underlying GitHub Actions run, which keeps executing on GitHub's
  servers regardless. Safe to interrupt and re-run.
