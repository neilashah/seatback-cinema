# Seatback Cinema — Handoff 2026-07-24 02:33

**Supersedes:** `SEATBACK-HANDOFF-2026-07-18-0815.md`

**Status:** Live. The app is deployed, verified working online and offline,
installed on Neil's phone, and API secrets are configured. Nothing is
blocking — remaining work is the open decisions and polish tracked in
`TODO.md`, which is now the running list going forward (this handoff won't
duplicate it — see that file for the itemized backlog).

---

## 1. What this session did

Picked up where the 07-18 handoff left off — "everything needed to go live
is built, pending execution." Execution happened:

1. **Recheck found the "missing" files weren't missing** — `index.html`
   material (`SeatbackCinema.html`), `sw.js`, `manifest.webmanifest`, icons,
   `refresh-catalog.yml`, and `DEPLOY.md` had landed on disk between the
   first and second look this session. `SeatbackCinema-preview.html` was
   also present — confirmed as a separate design mockup, not the app
   (title tag: "structure mockup"), so it was correctly excluded from the
   deploy tree.
2. **Built the missing `icon-maskable-512.png`** — the one real gap.
   `manifest.webmanifest` and `sw.js` both reference it but it didn't exist.
   Generated from `icon.svg` (macOS QuickLook `qlmanage -t` as the
   rasterizer — no cairo/Homebrew in this environment). Verified the glyph's
   bounding-box half-diagonal (129px) sits well inside the maskable safe
   zone (204.8px radius) before rendering.
3. **Assembled the repo per `DEPLOY.md` §1** — renamed `SeatbackCinema.html`
   → `index.html`, moved `build_catalog.js` / `matched.csv` /
   `verdict-debug.csv` into `pipeline/`, moved `refresh-catalog.yml` into
   `.github/workflows/`. Left the non-deploy matching/scraping scripts
   (`delta_ic_match.py`, `probe_mi.js`, etc.) at root — `DEPLOY.md` doesn't
   specify a home for them (tracked in `TODO.md`).
4. **Installed GitHub CLI and created the repo.** No `gh`, no Homebrew in
   this environment — downloaded the official `gh` release binary directly
   from `cli/cli` on GitHub, extracted to `~/.local/gh-cli`. Authenticated
   via device-code flow (Neil approved twice: once for base scopes, once
   more for the `workflow` scope after the first push was rejected for
   lacking permission to write `.github/workflows/*`).
5. **Created `github.com/neilashah/seatback-cinema`** (public), pushed the
   initial commit. Scanned all `.py`/`.js` files for hardcoded secrets before
   committing — none found.
6. **Enabled GitHub Pages** (branch `main`, root) via `gh api`. Confirmed the
   first build succeeded and all three critical paths return 200
   (`/`, `/catalog.json`, `/sw.js`).
7. **Verified for real, in a browser** — something the 07-18 handoff
   explicitly flagged as never having happened. `github.com` and
   `*.github.io` are both blocked in this session's sandboxed browser pane,
   so verification ran against a local `python3 -m http.server` serving the
   same files (DEPLOY.md's own recommended local-test method; `localhost` is
   a secure context so the service worker behaves identically):
   - Real catalog rendered: 198 titles, Dark Knight showing the gated
     "Loved by All" verdict, exactly 1 title short of ratings data
     ("2025 Masters Official Film") — matching the 07-18 handoff's corrected
     prediction exactly.
   - No console errors.
   - Service worker registered and active; all three caches
     (`seatback-shell-v1`, `seatback-data-v1`, `seatback-posters-v1`)
     populated, including 197/198 posters pre-warmed.
   - **True offline test**: killed the local server, reloaded — full
     catalog, scores, and posters rendered entirely from cache. (An early
     screenshot showed blank posters; turned out to be a screenshot-timing
     artifact, not a bug — `img.complete` and `naturalWidth` were already
     correct, a second screenshot confirmed normal rendering.)
8. **Neil added the three Actions secrets** (`TMDB_KEY`, `MDBLIST_KEY`,
   `TRAKT_CLIENT_ID`) via the GitHub website.
9. **Neil installed the PWA to his phone's home screen** — icon and
   standalone launch both confirmed working.

---

## 2. Current live state

- **Repo:** [github.com/neilashah/seatback-cinema](https://github.com/neilashah/seatback-cinema) (public, `main`)
- **Live site:** [neilashah.github.io/seatback-cinema](https://neilashah.github.io/seatback-cinema/)
- **Secrets:** all three set
- **Phone install:** confirmed working
- **Refresh workflow:** configured, secrets in place, **not yet triggered
  even once** — first real run (scheduled or manual) is unverified in CI.

---

## 3. What's next

Tracked in `TODO.md`, not duplicated here. Highest-value next items from
that list:

1. Manually trigger `refresh-catalog.yml` once via the Actions tab to prove
   the full pipeline works in CI now that secrets exist.
2. Decide the gate-scope question (§6a from 07-18) — the number to decide
   with is in `TODO.md`.
3. Push the same `scoring.js` to Impure Cinema so both apps agree.

---

## 4. Environment notes worth keeping

- This machine has no Homebrew and no `gh` CLI by default. `gh` now lives at
  `~/.local/gh-cli/gh_2.96.0_macOS_arm64/bin/gh`, authenticated as
  `neilashah` with `repo` + `workflow` scopes (token stored in the macOS
  keychain via `gh`'s credential store). Git is configured to use it as a
  credential helper (`gh auth setup-git`), so plain `git push`/`pull` in this
  repo folder works without re-authenticating.
- No cairo/Inkscape/PIL available for SVG rasterization; `qlmanage -t -s
  <size> -o <dir> <file.svg>` (macOS QuickLook) worked as a zero-install
  fallback.
- `github.com` and `*.github.io` are blocked in the sandboxed browser pane
  used for verification — local `http.server` is the workaround for any
  future browser-based checks of this app.
