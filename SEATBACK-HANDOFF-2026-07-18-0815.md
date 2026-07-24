# Seatback Cinema — Handoff 2026-07-18 08:15

**Supersedes:** `SEATBACK-HANDOFF-2026-07-17-2231.md`

**Status:** Everything needed to go live is built and tested. What remains is
execution on Neil's machine: one catalog rebuild, repo assembly, and the
GitHub Pages setup. No design or engineering work is outstanding except two
flagged decisions (§6).

---

## 1. What this session did

Took the app from "UI done, no real data, no deployment" to "fully built,
pending deploy." Four phases, in order:

1. **Batch scoring** — wrote `build_catalog.js`, the Node script that scores
   every matched title into a static `catalog.json`.
2. **Fixed a real scoring bug** — surfaced by real data: films both critics and
   audiences love were getting no MI phrase. Fixed in shared `scoring.js`.
3. **Wired the catalog into the app** — replaced the fake `MOVIES` array,
   added null-safety, made filters derive from real data.
4. **PWA + deployment** — manifest, service worker, app icons, GitHub Actions
   refresh workflow, deploy guide.

---

## 2. Files produced

| File | Where it goes | What it is |
|---|---|---|
| `build_catalog.js` | `pipeline/` | Node batch scorer. Reads `matched.csv`, calls TMDB/MDBList/Trakt, imports `scoring.js` directly, writes `catalog.json` + `verdict-debug.csv`. |
| `scoring.js` | repo root | **Modified** — agreement gate added (§4). Shared with Impure Cinema. |
| `SeatbackCinema.html` | repo root, **renamed `index.html`** | Wired to `catalog.json`; PWA tags; null-guarded. |
| `sw.js` | repo root | Service worker: shell cache-first, catalog stale-while-revalidate, posters cache-first + pre-warmed. |
| `manifest.webmanifest` | repo root | Standalone, portrait, `#0B0B0D`. |
| `icon-192/512.png`, `icon-maskable-512.png`, `apple-touch-icon.png`, `icon.svg` | repo root | App-icon tile treatment of the locked mark. Closes the IDENTITY §5 open item. |
| `refresh-catalog.yml` | `.github/workflows/` | Twice-monthly automated rescore with a publish-validation gate. |
| `DEPLOY.md` | repo root | Full deployment walkthrough + checklist. |
| `probe_mi.js` | `pipeline/` (optional) | Diagnostic: dumps raw MDBList/Trakt data and `computeVerdict` internals for named titles. Keep it — it's how the MI bug was found. |

---

## 3. Live API verification — all three now confirmed working

`SEATBACK-ISSUES.md` listed three things as "needs live verification." A full
198-title run returned **0 failures**, which verifies all of them:

- **MDBList path** — `api.mdblist.com/tmdb/movie/{id}?apikey=` is correct and
  matches Impure Cinema's known-good call (checked against `ImpureCinema.html`
  line 846). No change was needed.
- **Trakt two-step lookup** — works. **Changed** to resolve via IMDb id
  (`search/imdb/{imdb_id}`) rather than TMDB id, to match Impure Cinema's path
  exactly. TMDB's details response supplies `imdb_id` for free.
- **Source scale conversions** — `metacriticuser` (0–10) and `rogerebert`
  (0–4) land correctly.

These three items can be closed in `SEATBACK-ISSUES.md`.

---

## 4. The MI agreement gate — scoring engine change

**This is the most important change of the session. It affects Impure Cinema
too.**

### Symptom

Neil flagged that The Dark Knight and One Battle After Another — both
overwhelmingly well-reviewed — were showing no MI phrase. 53 of 198 titles had
`is` but no `misc`; roughly 30 of those had full critic coverage.

### Diagnosis (via `probe_mi.js`)

Not a data or plumbing fault. The data is pristine and both `C` and `A`
compute:

| Film | C | A | gap | M | classification |
|---|---|---|---|---|---|
| The Dark Knight | +1.56σ | +2.31σ | 0.75σ | 53 | `partial` |
| One Battle After Another | +1.82σ | +1.19σ | 0.63σ | 68 | `partial` |

The Miscibility Index measures the **distance** between critic and audience
z-scores, not the **direction**. With `MISC_TAU = 0.85`, the miscible band
(M ≥ 70) tolerates a gap of only ~0.60σ. Both films exceed it slightly, land
in `partial`, and `phraseForVerdict()` returns null for `partial` by design.

**In plain terms: the model read "audiences are even more enthusiastic than
critics" as ambiguity, when both sides clearly love the film.**

### Fix

New constant `MISC_AGREE_Z = 1.0` in `scoring.js`. When both `C` and `A` are
≥ +1σ (or both ≤ −1σ) **and the audience is not divisive**, classification is
forced to `miscible` regardless of M. The verdict object now carries
`agreementGated: true` for traceability.

Rationale: "Loved by All" / "Panned by All" *mean* exactly "both sides agree,
strongly." The gate makes the code match the definition. `TAU` and the M math
are untouched, so genuinely mixed cases behave exactly as before.

### Regression tested

| Case | Result |
|---|---|
| Dark Knight / One Battle | → gated → "Loved by All" ✅ |
| Critics high, audience cool | → "Critics' Film" (unchanged) ✅ |
| Audience high, critics cold | → "Audience's Film" (unchanged) ✅ |
| Both pan it | → gated → "Panned by All" ✅ |
| Both love it, **review-bombed audience** | → gate **suppressed**, stays silent ✅ |

The suppression case is the important safety property: a split audience with a
high mean is not "Loved by All."

---

## 5. Decisions made this session

**Thin-data rule tightened, but it changed nothing.** Neil chose "TMDB-only →
Not enough ratings yet." Implemented — but it flipped **zero** titles, because
the obscure tail turns out to have IMDb/Letterboxd audience ratings via
MDBList. They score legitimately on the audience side; they simply have no
critic aggregate, so MI can't compute. The tail is richer than
`SEATBACK-ISSUES.md` predicted. Only **1** title is genuinely empty.

**Node, not a Python port.** `build_catalog.js` imports `scoring.js` directly
via a `globalThis.window = globalThis` shim, so the batch pipeline and the app
run the *same formula code*. This closes the "no shared source of truth" gap
the previous handoff flagged as unaddressed, and makes the planned
`scoring-config.json` unnecessary.

**Filters derive from the catalog, not hardcoded.** The hardcoded chips were
missing "In Agreement" and "Panned by All" entirely. Chips, tier list, and
runtime slider bounds are now computed from whatever the catalog contains, so
a catalog refresh never needs a code change.

**Scores automated, membership manual.** The workflow rescores existing titles
twice monthly, but does *not* change which films are in the catalog — that
needs the Letterboxd scrape + TMDB matcher, which has a manual review step
(2 of 198 needed hand-matching). Automating it would let a bad match go live
unreviewed.

---

## 6. Open decisions — need Neil

**(a) Gate scope.** The gate currently overrides *any* M value, including the
strong-divergence band. A film at C = +1.11, A = +2.34 (M = 24) gets gated to
"Loved by All." Defensible — both sides love it — but arguably a gap that wide
is a real "Audience's Film" signal. The alternative is restricting the gate to
M ≥ 40 (the `partial` band only). **`verdict-debug.csv` from the next run will
show how many films actually sit there.** Decide with that number, not from
anecdotes.

**(b) Cron timing.** `0 9 1,15 * *` (09:00 UTC, 1st and 15th) is a placeholder.
Actions cron is always UTC and ignores DST. If Delta's rotation lands on a
particular day, match it.

---

## 7. What's left — Neil's execution path

**Step 1 is required before anything else.** The two catalog runs completed so
far were both with the **pre-gate** `scoring.js`, so the current
`catalog.json` still has `misc: null` for The Dark Knight and ~30 others.

1. **Rebuild the catalog with the gate version.**
   ```
   node build_catalog.js
   ```
   Expect Dark Knight and One Battle to log `(gated) · Loved by All`, and the
   summary to show a non-zero `agreement-gated` count. Keep
   `verdict-debug.csv` — it answers open decision (a).

2. **Assemble the repo** per `DEPLOY.md` §1. Rename
   `SeatbackCinema.html` → `index.html` (required — `sw.js` precaches that
   exact name).

3. **Enable Pages** — Settings → Pages → main / root.

4. **Add three secrets** — `TMDB_KEY`, `MDBLIST_KEY`, `TRAKT_CLIENT_ID`.

5. **Verify:** load the live URL, then DevTools → Network → Offline → reload.
   Full catalog should still render. Then install to a phone home screen and
   check the icon and standalone launch.

6. **Push the gate `scoring.js` to Impure Cinema too** — same file, both
   deployments, or the two apps will disagree about the same film.

---

## 8. Docs that are now stale

- `SEATBACK-ISSUES.md` — close the three live-verification items (§3); the
  thin-tail prediction (~8–10 empty titles) was wrong, it's 1.
- `SEATBACK-FUNCTIONAL-PLAN.md` — Phase 1 and the PWA phase are done.
- `SEATBACK-CINEMA-IDENTITY.md` §5 — the app-icon treatment open item is
  closed; `icon.svg` is the source.
- `SPEC.md` / Impure Cinema docs — must record the agreement gate, since
  `scoring.js` is shared.

---

## 9. Known small items, deliberately not done

- **Dead CSS vars.** `:root` still has `--plum-panned:#4A3468` and
  `--plum-mixed:#6B4C96` — pre-darkening values. `tierColor()` in JS uses the
  correct current ones, so nothing renders wrong. Worth deleting.
- **Poster placeholder** is a plain bordered rectangle. Could carry the
  Seatback mark.
- **`CACHE_VERSION` in `sw.js`** must be bumped on any deploy that changes the
  shell (`index.html`, `scoring.js`, icons). `catalog.json` is exempt —
  stale-while-revalidate handles it.

---

## 10. Testing caveat worth knowing

All browser QA (render, offline, null-handling, chips, filters) was run
against a **synthetic 12-title catalog** built to mirror the edge cases in
Neil's real data — thin titles, partial sources, gated verdicts, null
runtimes. The real `catalog.json` has never been rendered in a browser.
Nothing suggests it will differ, but the first local `python3 -m http.server`
run against real data is a genuine first look.
