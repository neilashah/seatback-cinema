#!/usr/bin/env node
/* =============================================================================
   build_catalog.js — Seatback Cinema batch scorer (Phase 1)

   Reads matched.csv (title -> TMDB id, from delta_ic_match.py), calls
   TMDB + MDBList + Trakt for every title, runs the SHARED scoring.js engine
   (Impurity Score + Miscibility Index), and writes ONE static catalog.json
   in exactly the record shape SeatbackCinema.html already consumes:

     { title, year, runtime, genre, is, misc, newThisMonth,
       sources: { imdb, rt, mc, letterboxd, tmdb }, poster }

   Why Node (not a Python port): it imports scoring.js DIRECTLY, so the batch
   pipeline and the app run the *same* formula code — no second implementation
   to drift. This closes the "no shared source of truth" gap the handoff flagged.

   -----------------------------------------------------------------------------
   REQUIREMENTS
     - Node 18+ (uses built-in global fetch — no npm install, matching the
       project's stdlib-only ethos).
     - scoring.js and matched.csv in the same folder (copy scoring.js from the
       repo next to this script).

   RUN
     export TMDB_KEY=your_tmdb_v3_key        # same key delta_ic_match.py used
     export MDBLIST_KEY=your_mdblist_key
     export TRAKT_CLIENT_ID=your_trakt_client_id
     node build_catalog.js                   # full run (~198 titles, few min)
     node build_catalog.js --limit 5         # quick smoke test on 5 titles
     node build_catalog.js --out catalog.json --in matched.csv --delay 350

   -----------------------------------------------------------------------------
   VERIFY ON FIRST RUN (these are the ISSUES.md "live verification" items — this
   run is also their verification pass; watch the per-title log for surprises):
     1. MDBLIST_BASE below matches your known-good Impure Cinema proxy call.
     2. Trakt two-step lookup (search/imdb -> movies/{id}/ratings, same path as
        Impure Cinema) returns a distribution object keyed "1".."10".
     3. metacriticuser / rogerebert scale conversions land in 0-100 (handled in
        scoring.js; the log prints any title whose MI came back "unmeasured").
   ============================================================================= */

'use strict';

const fs = require('fs');
const path = require('path');

// --- load the shared engine (browser IIFE assigns to `window`; shim it) -------
globalThis.window = globalThis;              // scoring.js does `global.Scoring = …` onto this
require(path.resolve(__dirname, process.env.SCORING_PATH || './scoring.js'));
const Scoring = globalThis.Scoring;
if (!Scoring || !Scoring.computeVerdict) {
  console.error('ERROR: scoring.js did not load. Put a copy of scoring.js next to this script.');
  process.exit(1);
}

// --- config / args -----------------------------------------------------------
const args = process.argv.slice(2);
const getArg = (flag, def) => {
  const i = args.indexOf(flag);
  return i !== -1 && args[i + 1] ? args[i + 1] : def;
};
const IN_CSV   = getArg('--in', 'matched.csv');
const OUT_JSON = getArg('--out', 'catalog.json');
const LIMIT    = parseInt(getArg('--limit', '0'), 10) || 0;   // 0 = all
const DELAY_MS = parseInt(getArg('--delay', '350'), 10);      // pause between titles

const TMDB_KEY        = process.env.TMDB_KEY;
const MDBLIST_KEY     = process.env.MDBLIST_KEY;
const TRAKT_CLIENT_ID = process.env.TRAKT_CLIENT_ID;
if (!TMDB_KEY)    { console.error('ERROR: set TMDB_KEY');    process.exit(1); }
if (!MDBLIST_KEY) { console.error('ERROR: set MDBLIST_KEY'); process.exit(1); }
if (!TRAKT_CLIENT_ID) console.warn('WARN: no TRAKT_CLIENT_ID — polarization signal will be absent (MI still computes).');

// VERIFY #1: confirm this matches your working Impure Cinema MDBList call.
const MDBLIST_BASE = 'https://api.mdblist.com';
const TMDB_IMG     = 'https://image.tmdb.org/t/p/w342';

// --- tiny helpers ------------------------------------------------------------
const sleep = ms => new Promise(r => setTimeout(r, ms));

async function getJSON(url, opts = {}, tries = 3) {
  for (let attempt = 1; attempt <= tries; attempt++) {
    try {
      const res = await fetch(url, opts);
      if (res.status === 429) { await sleep(1500 * attempt); continue; }   // backoff
      if (!res.ok) return null;
      return await res.json();
    } catch (e) {
      if (attempt === tries) return null;
      await sleep(600 * attempt);
    }
  }
  return null;
}

// Minimal RFC-4180-ish CSV parser (matched_title / note can contain commas).
function parseCSV(text) {
  const rows = [];
  let row = [], field = '', inQuotes = false;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (inQuotes) {
      if (c === '"') { if (text[i + 1] === '"') { field += '"'; i++; } else inQuotes = false; }
      else field += c;
    } else if (c === '"') inQuotes = true;
    else if (c === ',') { row.push(field); field = ''; }
    else if (c === '\r') { /* skip */ }
    else if (c === '\n') { row.push(field); rows.push(row); row = []; field = ''; }
    else field += c;
  }
  if (field.length || row.length) { row.push(field); rows.push(row); }
  return rows.filter(r => r.length && r.some(v => v !== ''));
}

// --- per-source fetchers -----------------------------------------------------
async function fetchTmdb(id) {
  return getJSON(`https://api.themoviedb.org/3/movie/${id}?api_key=${TMDB_KEY}`);
}

// MDBList -> parseMdblist shape: { ratings:[{source,value,votes,score},…] } keyed by source
async function fetchMdblist(id) {
  const data = await getJSON(`${MDBLIST_BASE}/tmdb/movie/${id}?apikey=${MDBLIST_KEY}`);
  const out = {};
  const arr = data && Array.isArray(data.ratings) ? data.ratings : [];
  for (const r of arr) if (r && r.source) out[r.source] = r;
  return out;
}

// Trakt (matches Impure Cinema's known-good path): resolve via IMDb id ->
// trakt id -> ratings{rating,votes,distribution}. TMDB's details response
// carries imdb_id; fall back to a TMDB-id search only if it's missing.
async function fetchTrakt(imdbId, tmdbId) {
  if (!TRAKT_CLIENT_ID) return null;
  const headers = { 'trakt-api-version': '2', 'trakt-api-key': TRAKT_CLIENT_ID };
  const q = imdbId
    ? `https://api.trakt.tv/search/imdb/${encodeURIComponent(imdbId)}?type=movie`
    : `https://api.trakt.tv/search/tmdb/${tmdbId}?type=movie`;
  const found = await getJSON(q, { headers });
  const traktId = found && found[0] && found[0].movie && found[0].movie.ids && found[0].movie.ids.trakt;
  if (!traktId) return null;
  const r = await getJSON(`https://api.trakt.tv/movies/${traktId}/ratings`, { headers });
  if (!r || r.rating == null) return null;
  return { rating: r.rating, votes: r.votes, distribution: r.distribution };
}

// --- Impurity Score: replicated EXACTLY from ImpureCinema.html (lines 957-969),
//     using scoring.js's own BASE_WEIGHTS + confidence(). --------------------
function computeImpurity(mdb, details) {
  const W = Scoring.BASE_WEIGHTS, conf = Scoring.confidence;
  const imdbPct = mdb.imdb && mdb.imdb.value != null ? mdb.imdb.value * 10 : null;
  const rtPct   = mdb.tomatoes && mdb.tomatoes.value != null ? mdb.tomatoes.value : null;
  const metaPct = mdb.metacritic && mdb.metacritic.value != null ? mdb.metacritic.value : null;
  const lbPct   = mdb.letterboxd && mdb.letterboxd.value != null ? mdb.letterboxd.value * 20 : null;
  const tmdbPct = details && details.vote_average ? Math.round(details.vote_average * 10) : null;

  const sources = [
    { pct: imdbPct, weight: W.imdb * conf(mdb.imdb && mdb.imdb.votes || 0) },
    { pct: rtPct,   weight: W.rt },
    { pct: metaPct, weight: W.mc },
    { pct: lbPct,   weight: W.letterboxd * conf(mdb.letterboxd && mdb.letterboxd.votes || 0) },
    { pct: tmdbPct, weight: W.tmdb * conf(details && details.vote_count || 0) },
  ].filter(s => s.pct !== null && s.weight > 0);

  if (!sources.length) return null;
  const wsum = sources.reduce((a, s) => a + s.weight, 0);
  return Math.round(sources.reduce((a, s) => a + s.pct * s.weight, 0) / wsum);
}

// Native-scale source object the row/strip renders (nulls for missing).
function sourceBlock(mdb, details) {
  return {
    imdb:       mdb.imdb       && mdb.imdb.value       != null ? mdb.imdb.value       : null, // 0-10
    rt:         mdb.tomatoes   && mdb.tomatoes.value   != null ? mdb.tomatoes.value   : null, // 0-100
    mc:         mdb.metacritic && mdb.metacritic.value != null ? mdb.metacritic.value : null, // 0-100
    letterboxd: mdb.letterboxd && mdb.letterboxd.value != null ? mdb.letterboxd.value : null, // 0-5
    tmdb:       details && details.vote_average != null ? details.vote_average : null,        // 0-10
  };
}

// --- optional "new this month" hook -----------------------------------------
// The Delta "New on Delta" shelf is a SEPARATE scrape (not in matched.csv), so
// this defaults to false. Drop a new_this_month.txt (one tmdb_id per line) next
// to this script to flag them, or wire the Delta-shelf signal in later.
function loadNewSet() {
  const p = path.resolve(__dirname, 'new_this_month.txt');
  if (!fs.existsSync(p)) return new Set();
  return new Set(fs.readFileSync(p, 'utf8').split(/\s+/).map(s => s.trim()).filter(Boolean));
}

// --- main --------------------------------------------------------------------
(async function main() {
  const csvPath = path.resolve(__dirname, IN_CSV);
  if (!fs.existsSync(csvPath)) { console.error(`ERROR: ${IN_CSV} not found next to this script.`); process.exit(1); }

  const rows = parseCSV(fs.readFileSync(csvPath, 'utf8'));
  const header = rows.shift().map(h => h.trim());
  const col = name => header.indexOf(name);
  const iTmdb = col('tmdb_id'), iRaw = col('raw_title'), iConf = col('confidence');
  if (iTmdb === -1) { console.error('ERROR: matched.csv has no tmdb_id column.'); process.exit(1); }

  const newSet = loadNewSet();
  let queue = rows
    .map(r => ({ tmdbId: (r[iTmdb] || '').trim(), raw: (r[iRaw] || '').trim(), conf: (r[iConf] || '').trim() }))
    .filter(x => x.tmdbId && x.tmdbId !== 'miss' && /^\d+$/.test(x.tmdbId));
  if (LIMIT) queue = queue.slice(0, LIMIT);

  console.log(`Scoring ${queue.length} titles (delay ${DELAY_MS}ms)…\n`);

  const catalog = [];
  const stats = { scored: 0, thin: 0, unmeasuredMI: 0, failed: 0, gated: 0, partial: 0 };
  const debugRows = ['title,is,C,A,D,M,R,dispersion,P,audienceDivided,agreementGated,classification,phrase,flags'];

  for (let i = 0; i < queue.length; i++) {
    const { tmdbId, raw } = queue[i];
    const tag = `[${i + 1}/${queue.length}] ${raw || tmdbId}`;
    try {
      const details = await fetchTmdb(tmdbId);
      if (!details || !details.title) { console.log(`${tag} — FAILED (no TMDB details)`); stats.failed++; await sleep(DELAY_MS); continue; }

      const mdb   = await fetchMdblist(tmdbId);
      const trakt = await fetchTrakt(details.imdb_id, tmdbId);

      // Thin-data rule: a title needs at least one NON-TMDB rating source to
      // score. TMDB's own audience vote alone is too weak to stand as an IS, so
      // TMDB-only titles are marked "insufficient" (is/sources/misc all null),
      // same treatment as titles with no ratings at all.
      const hasNonTmdb =
        (mdb.imdb       && mdb.imdb.value       != null) ||
        (mdb.tomatoes   && mdb.tomatoes.value   != null) ||
        (mdb.metacritic && mdb.metacritic.value != null) ||
        (mdb.letterboxd && mdb.letterboxd.value != null);
      const rawIs = computeImpurity(mdb, details);      // null if nothing weights > 0
      const thin  = !hasNonTmdb || rawIs === null;      // TMDB-only, or nothing scoreable

      const verdict = Scoring.computeVerdict(mdb, details, trakt);
      const is   = thin ? null : rawIs;
      const misc = thin ? null : Scoring.phraseForVerdict(verdict);   // string | null — the drop-in
      if (!thin && verdict && verdict.unmeasured) stats.unmeasuredMI++;
      if (!thin && verdict && verdict.agreementGated) stats.gated++;
      if (!thin && verdict && !verdict.unmeasured && verdict.classification === 'partial') stats.partial++;
      if (thin) stats.thin++; else stats.scored++;

      catalog.push({
        title: details.title,
        year: details.release_date ? parseInt(details.release_date.slice(0, 4), 10) : null,
        runtime: details.runtime || null,
        genre: details.genres && details.genres[0] ? details.genres[0].name : 'Other',
        is,                                              // 0-100 | null
        misc,                                            // approved MI phrase | null
        newThisMonth: newSet.has(tmdbId),
        sources: thin ? null : sourceBlock(mdb, details),
        poster: details.poster_path ? `${TMDB_IMG}${details.poster_path}` : null,
        tmdbId,                                          // traceability (UI ignores extra keys)
      });

      // One-time calibration sidecar: per-film MI internals, for tuning the
      // agreement gate / TAU against the real distribution instead of anecdotes.
      debugRows.push([
        JSON.stringify(details.title),
        thin ? '' : (is ?? ''),
        verdict && !verdict.unmeasured ? verdict.C.toFixed(3) : '',
        verdict && !verdict.unmeasured ? verdict.A.toFixed(3) : '',
        verdict && !verdict.unmeasured ? verdict.D.toFixed(3) : '',
        verdict && !verdict.unmeasured ? verdict.M.toFixed(1) : '',
        verdict && !verdict.unmeasured ? verdict.R.toFixed(3) : '',
        verdict && !verdict.unmeasured && verdict.dispersion != null ? verdict.dispersion.toFixed(3) : '',
        verdict && !verdict.unmeasured && verdict.P != null ? verdict.P.toFixed(3) : '',
        verdict && !verdict.unmeasured ? (verdict.audienceDivided ? 'yes' : 'no') : '',
        verdict && !verdict.unmeasured ? (verdict.agreementGated ? 'yes' : 'no') : '',
        verdict && verdict.unmeasured ? 'unmeasured' : (verdict ? verdict.classification : ''),
        JSON.stringify(misc || ''),
        thin ? 'thin' : '',
      ].join(','));

      console.log(`${tag} — IS ${is === null ? '—' : is}${misc ? ` · ${misc}` : (verdict && verdict.unmeasured ? ' · MI unmeasured' : '')}${verdict && verdict.agreementGated ? ' (gated)' : ''}${thin ? ' · THIN' : ''}`);
    } catch (e) {
      console.log(`${tag} — ERROR ${e.message}`); stats.failed++;
    }
    await sleep(DELAY_MS);
  }

  // Sort by IS desc, thin titles last — a sensible default catalog order.
  catalog.sort((a, b) => (b.is ?? -1) - (a.is ?? -1) || a.title.localeCompare(b.title));

  fs.writeFileSync(path.resolve(__dirname, OUT_JSON), JSON.stringify(catalog));
  fs.writeFileSync(path.resolve(__dirname, 'verdict-debug.csv'), debugRows.join('\n') + '\n');
  console.log(`\nWrote ${OUT_JSON} — ${catalog.length} titles.  (+ verdict-debug.csv)`);
  console.log(`  scored: ${stats.scored} · thin(no ratings): ${stats.thin} · MI unmeasured: ${stats.unmeasuredMI} · failed: ${stats.failed}`);
  console.log(`  agreement-gated: ${stats.gated} · still partial (no phrase): ${stats.partial}`);
  if (stats.failed > 0) console.log('  (failed titles were skipped — rerun or add to an override table.)');
})();
