# Seatback Cinema — Handoff (2026-07-17, 22:31 ET)

## What this session decided

**1. Detail view — cut entirely.**
Built a full detail view (hero ring, verdict line, tap-to-expand source breakdown, slide-up nav) then reconsidered: on a plane, someone's scanning a list to pick something, and the only thing the detail view added beyond the existing row + tap-to-expand breakdown was the MI phrase. Everything else (poster, score, meta, source breakdown) already exists on the row. Decision: no detail view, no back-button nav, no push/slide pattern. Row taps do nothing; tapping the score badge is still the only interaction, and it now shows the MI phrase too.

**2. MI phrase moved into the existing breakdown panel.**
Added a `bd-verdict` line at the top of the tap-to-expand breakdown (above the 5 source mini-rings): "**Tier** and/but *MI phrase*" — same and/but conjunction rule as Impure Cinema, same "Panned" + "Panned by All" collision fix (drops the redundant tier word). Titles with no MI phrase show the tier word alone; titles with no ratings at all keep "Not enough ratings yet," no verdict line.

**3. Shared scoring engine extracted — `scoring.js`.**
Impure Cinema and Seatback Cinema were independently recreating the same math: Impure Cinema had the real `computeVerdict()` engine; Seatback had flat 50/70/85 tier thresholds (an already-flagged issue) and a hand-typed `misc` string with its own separately-duplicated conjunction map. The Delta batch pipeline was *also* planned as a from-scratch Python port of the same formulas — three implementations of one formula, with nothing keeping them in sync.

Pulled into `scoring.js`, shared by both HTML files via `<script src="scoring.js">`:
- Impurity Score weighting (`BASE_WEIGHTS`, `confidence()`)
- The full Miscibility Index engine (`computeVerdict()`, all calibration constants)
- Tier-name thresholds — `scoreTierName()` (Acclaimed/Liked/Mixed/Panned cutoffs)
- MI phrase selection from a verdict — `phraseForVerdict()`
- The and/but conjunction rule + the Panned/"Panned by All" collision fix — `buildVerdictParts()`

**Stays local to each app on purpose:** tier → color mapping. Impure Cinema's magenta ramp and Seatback's Passport Plum ramp are deliberately independent palettes, now just applied to the same tier names.

Verified against known values before and after the refactor (tier thresholds at 90/75/55/30, phrase selection for miscible/critic-darling/partial, and the collision case) — all matched Impure Cinema's original hardcoded behavior exactly.

**Honest gap:** Seatback still doesn't call `Scoring.computeVerdict()` for real — its fake data hand-sets the `misc` phrase directly rather than deriving it from live per-source ratings + vote counts. `buildBreakdownVerdict()` is now written so that's a drop-in swap: once Phase 1's real `catalog.json` exists, swap the hand-set `misc` field for `Scoring.phraseForVerdict()` on a real `Scoring.computeVerdict()` result, no other code changes needed.

**Not addressed:** the Python/Delta batch pipeline still has no shared source of truth with the JS engine. Different runtime, can't share code directly — the fix there is a shared `scoring-config.json` (weights/calibration as data) that both `scoring.js` and the Python matcher read, so at least the numbers can't drift even if the formula code is a maintained port. Not built yet.

**4. Bug fix: literal `</script>` inside a JS comment.**
`scoring.js`'s own header comment quoted `<script src="scoring.js"></script>` as a usage example. When that file's contents get inlined into an HTML `<script>` block (as the preview bundles below do), the HTML parser ends the script tag at that literal substring — it doesn't know it's sitting inside a JS comment, so it doesn't matter that it's "just a comment." Fixed by rewording the comment in prose instead of quoting the tag. This matters for the canonical `scoring.js` too, not just previews, in case anyone ever inlines it.

## Open decision, unchanged from before this session
Deployment target still needs reconciling: last stated direction was GitHub + Vercel, but `DELTA-HANDOFF.md` originally specced GitHub Pages + Actions with no proxy layer.

## Docs that need correcting to match this session
- `SEATBACK-ISSUES.md` — remove "detail view doesn't exist" (no longer applicable — decided against having one); remove/reframe the flat-tier-threshold issue (tier *naming* is now shared and z-score-calibrated via `scoring.js`; only per-source color application was ever app-specific, and that's fine as designed)
- `SEATBACK-FUNCTIONAL-PLAN.md` — Phase 2 (detail view) is no longer planned; Phase 1 should note it can call `Scoring.computeVerdict()` directly once real data lands, rather than porting the formula again
- `SEATBACK-CINEMA-IDENTITY.md` §5 (score drift question) — still open, but now purely a freshness question (live vs. batch), not a correctness risk, since both apps run the same formula code

## File manifest
**Canonical / for deployment (upload together, same directory):**
- `scoring.js` — shared engine (see 3 messages back for latest, post-bugfix version)
- `ImpureCinema.html` — refactored to consume `scoring.js`
- `SeatbackCinema.html` — refactored to consume `scoring.js`, detail view removed, MI phrase in breakdown panel (**attached to this handoff**)

**Preview-only, not for the repo:**
- `ImpureCinema-preview.html` / `SeatbackCinema-preview.html` — same code with `scoring.js` inlined, so the chat's sandboxed file viewer can run them standalone. Regenerate from canonical files if they go stale; don't hand-edit them directly.
