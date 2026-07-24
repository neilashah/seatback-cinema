#!/usr/bin/env node
/* probe_mi.js — why is MI "unmeasured" for films that clearly should have one?
   Dumps the RAW MDBList response + the exact computeVerdict internals for a few
   named titles, so we can see whether the critic side is missing, mis-keyed, or
   under a different field.

   Run from your Delta folder (scoring.js + catalog.json alongside):
     export MDBLIST_KEY=…  TMDB_KEY=…  TRAKT_CLIENT_ID=…
     node probe_mi.js                       # defaults: Dark Knight + One Battle
     node probe_mi.js "dark knight" "dune"  # or pass your own title substrings
*/
'use strict';
const fs = require('fs');
const path = require('path');
globalThis.window = globalThis;
require(path.resolve(__dirname, './scoring.js'));
const S = globalThis.Scoring;

const MDBLIST_KEY = process.env.MDBLIST_KEY, TMDB_KEY = process.env.TMDB_KEY, TRAKT = process.env.TRAKT_CLIENT_ID;
const needles = process.argv.slice(2).length ? process.argv.slice(2) : ['dark knight', 'one battle'];
const catalog = JSON.parse(fs.readFileSync(path.resolve(__dirname, 'catalog.json'), 'utf8'));

const getJSON = async (url, opts) => { try { const r = await fetch(url, opts); return r.ok ? r.json() : null; } catch { return null; } };

// the exact source keys the engine reads (from scoring.js)
const CRITIC = ['tomatoes', 'metacritic', 'rogerebert'];
const AUDIENCE = ['imdb', 'letterboxd', 'popcorn', 'metacriticuser', 'trakt'];

(async () => {
  for (const needle of needles) {
    const rec = catalog.find(v => v.title.toLowerCase().includes(needle.toLowerCase()));
    if (!rec) { console.log(`\n=== "${needle}" — not found in catalog.json ===`); continue; }
    console.log(`\n===================================================================`);
    console.log(`${rec.title}  (tmdb ${rec.tmdbId})`);
    console.log(`  catalog says:  IS=${rec.is}  misc=${JSON.stringify(rec.misc)}  sources=${JSON.stringify(rec.sources)}`);

    const details = await getJSON(`https://api.themoviedb.org/3/movie/${rec.tmdbId}?api_key=${TMDB_KEY}`);
    console.log(`  TMDB resolves: "${details && details.title}" (${details && (details.release_date||'').slice(0,4)})  imdb_id=${details && details.imdb_id}`);

    const raw = await getJSON(`https://api.mdblist.com/tmdb/movie/${rec.tmdbId}?apikey=${MDBLIST_KEY}`);
    const arr = raw && Array.isArray(raw.ratings) ? raw.ratings : [];
    console.log(`  RAW MDBList ratings (${arr.length}):`);
    for (const r of arr) console.log(`     source="${r.source}"  value=${r.value}  score=${r.score}  votes=${r.votes}`);

    const mdb = {};
    for (const r of arr) if (r && r.source) mdb[r.source] = r;

    // what the engine actually detects on each side
    const critHits = CRITIC.filter(k => mdb[k] && (mdb[k].value != null || mdb[k].score != null));
    const audHits  = AUDIENCE.filter(k => mdb[k] && (mdb[k].value != null || mdb[k].score != null));
    console.log(`  engine sees -> critic sources: [${critHits.join(', ') || 'NONE'}]   audience sources: [${audHits.join(', ') || 'none'}]`);

    let trakt = null;
    if (TRAKT && details && details.imdb_id) {
      const hdr = { headers: { 'trakt-api-version': '2', 'trakt-api-key': TRAKT } };
      const f = await getJSON(`https://api.trakt.tv/search/imdb/${details.imdb_id}?type=movie`, hdr);
      const tid = f && f[0] && f[0].movie && f[0].movie.ids && f[0].movie.ids.trakt;
      if (tid) { const rr = await getJSON(`https://api.trakt.tv/movies/${tid}/ratings`, hdr); if (rr && rr.rating != null) trakt = { rating: rr.rating, votes: rr.votes, distribution: rr.distribution }; }
    }

    const v = S.computeVerdict(mdb, details || {}, trakt);
    if (v.unmeasured) {
      console.log(`  computeVerdict -> UNMEASURED  (C=${v.C ?? 'null'} A=${v.A ?? 'null'} — a null here is the culprit)`);
    } else {
      console.log(`  computeVerdict -> C=${v.C.toFixed(2)} A=${v.A.toFixed(2)} R=${v.R.toFixed(2)} M=${v.M.toFixed(1)} class=${v.classification} -> phrase=${JSON.stringify(S.phraseForVerdict(v))}`);
    }
  }
})();
