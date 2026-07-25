# Seatback Cinema — Handoff 2026-07-25 13:58

**Supersedes:** `SEATBACK-HANDOFF-2026-07-24-0319.md`

**Status:** Live and current, membership sync now runs with effectively no
manual steps for the common case. One thing to watch: a Cloudflare
challenge just blocked the local scraper too (separate from the
already-fixed GitHub Actions IP block) — very likely a self-inflicted
rate-limit from heavy testing today, left to self-resolve, see §3.

---

## 1. What this session did

1. **Caught a second same-day Letterboxd update.** Em updated the list
   again at 23:47 UTC on 07-24, ~17 hours after the first sync. Re-ran the
   pipeline: 189 titles (18 added, 24 removed), added a bless override for
   "Ready or Not 2: Here I Come" (TMDB's own title omits the "2" — verified
   same Le Domas-family sequel plot before pinning). Verified live.
2. **Added a way to force-refresh the catalog from a standalone launch.**
   Root cause of a real bug Neil hit: reopening the PWA from the home
   screen icon has no browser reload button, and iOS often just resumes
   the already-loaded page rather than re-running scripts, so a passenger
   could sit on a stale catalog indefinitely. Fixed with a header refresh
   button (bypasses the service worker's cache-first response via a new
   `X-Seatback-Refresh` header, routed to a network-first path in `sw.js`)
   plus a silent auto-recheck on `visibilitychange`/`pageshow`.
   `CACHE_VERSION` bumped to `v2`.
3. **Automated the membership sync, in two attempts.**
   - First version: `sync_catalog.py` scraped Letterboxd directly in CI,
     triggered by `watch-catalog.yml`. Looked right, got built and pushed.
   - A live test run 403'd immediately. Checking history showed **both
     prior scheduled `watch-catalog.yml` runs (07-24, 07-25) had been
     silently 403'd too, since day one** — Letterboxd blocks GitHub
     Actions runner IPs even with realistic browser headers.
     TMDB/MDBList/Trakt are unaffected. (The safety net worked exactly as
     designed — it opened `catalog-watch-broken` issue #1 on the first
     blocked run rather than misreporting a false catalog change; it just
     went unnoticed until this session's manual test.)
   - **Fixed by moving the scrape out of CI entirely.** New
     `push_scrape.sh` runs locally (installed as a launchd LaunchAgent —
     `com.seatback-cinema.push-scrape.plist`, daily 9am, loaded and
     confirmed via `launchctl list`), scrapes, and pushes
     `pipeline/raw_scrape.tsv` only when it changes. That push now
     triggers `sync-catalog.yml` directly (`on: push`, no more
     `watch-catalog.yml` in between — deleted along with `watch_catalog.py`,
     since its whole job — cheap diff-then-decide — is now inherent in the
     push itself). `sync-catalog.yml` runs the TMDB match, commits
     clean-tier titles straight to `main`, triggers `refresh-catalog.yml`,
     and surfaces anything ambiguous as a `catalog-needs-review` issue
     instead of shipping a bad guess.
   - Verified end-to-end for real (not just reasoned through): ran
     `push_scrape.sh`, confirmed the push actually triggered
     `sync-catalog.yml` (`event: push`), watched it match 189/189 cleanly
     with 0 flagged and correctly find nothing new to commit. Closed issue
     #1 with the root-cause writeup.
4. **Built the Catalog Ops dashboard** (`catalog-ops.html`, published as a
   claude.ai Artifact) at Neil's request — a status strip, a button to
   copy a ready-to-paste "run the scrape now" instruction, and a
   reconciliation section for any flagged titles. Two real bugs surfaced
   and got fixed along the way (both worth remembering, see §4). Neil
   live-tested the copy button for real — pasted the copied instruction
   back into this chat, which then triggered the Cloudflare-challenge
   finding in §5.
5. **Discussed but did not act on:** running the drift-watcher more often
   (concluded detection speed wasn't the actual bottleneck — response
   speed was, which this session's automation work addressed instead) and
   cross-checking against Delta's own inflight-entertainment page (Neil
   redirected to the matching-pipeline speed work instead before that was
   finished).

---

## 2. Current live state

- **Repo:** [github.com/neilashah/seatback-cinema](https://github.com/neilashah/seatback-cinema) (public, `main`)
- **Live site:** [neilashah.github.io/seatback-cinema](https://neilashah.github.io/seatback-cinema/) — 189 titles, `CACHE_VERSION` `v2`
- **Membership sync:** `push_scrape.sh` (local, launchd-scheduled, daily 9am) → pushes `pipeline/raw_scrape.tsv` on change → triggers `sync-catalog.yml` (CI) → matches, commits clean-tier, triggers `refresh-catalog.yml` → live. No human step needed unless a title gets flagged.
- **Catalog Ops dashboard:** published Artifact, source also committed at `catalog-ops.html` (repo copy is a snapshot, not live-linked — see TODO.md). `FLAGGED` data embedded in it is a manual snapshot, currently empty (0 flagged) as of last publish.

---

## 3. Open thread: Cloudflare challenge on the local scraper

Right at session end, Neil pasted the dashboard's copied instruction back
into chat, so `push_scrape.sh` was run for real — and got a 403. Diagnosed
via a direct `curl` with response headers: `cf-mitigated: challenge` and a
Cloudflare "Just a moment..." interstitial body. This is a **different
mechanism from the GHA-IP-block issue** fixed earlier this session — no
plain HTTP client (`urllib`, `curl`, this project's scraper) can pass a JS
challenge, on any IP, once triggered.

Most likely cause: this session scraped the same Letterboxd list 6-8+
times in a few hours (initial pipeline runs, two manual match runs,
watcher tests, the real `push_scrape.sh` run, this one) — very plausibly
tripping Cloudflare's bot heuristics on volume alone, not a standing
block. `push_scrape.sh`'s safety floor worked correctly (0 titles scraped,
refused to push).

**Decision: wait and see.** Nothing was pushed, nothing broke. Check
whether tomorrow's normal once-daily 9am launchd run goes through cleanly.
If this recurs under normal (not heavy-testing) usage, that's a real
signal and would need a more robust scraper — e.g. headless-browser-based
(Playwright), which can actually execute the JS challenge — rather than
waiting it out again. Logged in `TODO.md`.

---

## 4. Two real bugs from building the dashboard (worth remembering)

1. **`sendPrompt()` doesn't exist for published Artifacts.** Assumed
   (wrongly) that a hosted Artifact page could message back into the chat
   that published it, the way a different tool (inline chat "widgets")
   can. There's no such mechanism for a standalone Artifact URL. Rebuilt
   around copying a ready-to-paste instruction to the clipboard instead —
   Neil pastes it into a Claude Code chat himself.
2. **HTML-attribute quote collision silently broke a button.** The
   "Bless this match" button built its click handler as
   `onclick="sendAction(this, ${JSON.stringify(...)})"` — `JSON.stringify`
   produces a double-quoted string, which collided with the surrounding
   double-quoted HTML attribute and truncated it, so the button did
   nothing. Root cause of Neil's "the button does not send anything"
   report — and it was a *second*, unrelated bug on top of the
   `sendPrompt` mistake, not the same issue re-surfacing. Fixed by
   removing all inline `onclick`/`onsubmit` attributes and wiring every
   action through `addEventListener` after render, which eliminates this
   entire bug class (no dynamic string ever round-trips through HTML
   attribute syntax again).

Also hardened once live testing showed the async Clipboard API is blocked
inside the published Artifact's sandbox (likely a Permissions-Policy
restriction, out of this page's control): copy is now layered —
Clipboard API, then `execCommand('copy')` on a pre-selected text reveal,
then a plain "select it yourself" state that's honest about not having
copied anything rather than falsely claiming success.

---

## 5. What's next

Tracked in `TODO.md`. Highest-value remaining items:

1. Check whether tomorrow's 9am `push_scrape.sh` run clears the Cloudflare
   challenge on its own (§3).
2. Gate scope decision (§6a of the 07-18 handoff, still open).
3. Push the same `scoring.js` to Impure Cinema so both apps agree.
4. Decide where the non-deploy pipeline scripts (including the new
   `catalog-ops.html`, `push_scrape.sh`, `sync_catalog.py`) actually
   belong — more pressing now that CI depends on some of these paths.

---

## 6. Environment notes worth keeping

- `gh` CLI: `~/.local/gh-cli/gh_2.96.0_macOS_arm64/bin/gh`, authenticated
  as `neilashah`. Prefix commands with
  `export PATH="$HOME/.local/gh-cli/gh_2.96.0_macOS_arm64/bin:$PATH"`.
- `TMDB_KEY` is not stored anywhere locally or in this environment — only
  in the GitHub Actions secret and Neil's TMDB account. Not needed for
  `push_scrape.sh` (no TMDB calls, just the Letterboxd scrape); still
  needed if ever running `delta_ic_match.py` / the old manual pipeline by
  hand.
- The launchd LaunchAgent (`~/Library/LaunchAgents/com.seatback-cinema.push-scrape.plist`)
  only runs while the Mac is on and Neil is logged in — confirmed
  explicitly with him. Missed runs while asleep generally catch up on
  wake; fully powered off just waits for the next scheduled time, no
  catch-up possible.
- `gh run watch <id>` is a local polling loop only — killing it does not
  cancel the underlying GitHub Actions run.
- The Browser pane's file-preview mode only supports interactive
  screenshot/click testing for files inside the project folder; anything
  in the scratchpad needed a local `python3 -m http.server` to test
  properly (used repeatedly this session for the dashboard artifact).
- `navigator.clipboard.writeText()` requires genuine user-gesture
  activation — a JS-dispatched `.click()` in a test/debug console does
  NOT count, so testing clipboard behavior needs a real simulated click
  (the Browser pane's `computer` tool), not `element.click()` via
  `javascript_tool`.
