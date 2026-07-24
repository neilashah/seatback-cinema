/* =========================================================
   scoring.js — shared Impurity Score / Miscibility Index engine.

   Single source of truth for the math and phrase/conjunction rules
   used by BOTH Impure Cinema (ImpureCinema.html) and Seatback Cinema
   (SeatbackCinema.html). Load this before either app's own script
   block, via a script tag referencing this file by src.

   What lives here vs. what stays per-app:
   - HERE: weights, calibration constants, the Miscibility Index math
     (computeVerdict), tier-name thresholds, MI phrase selection, the
     and/but conjunction rule, and the "Panned"+"Panned by All"
     collision rule.
   - PER-APP: tier -> color mapping (Impure Cinema's magenta ramp vs.
     Seatback's Passport Plum ramp are deliberately independent
     palettes) and all markup/rendering.

   Exposes a single global: window.Scoring
   ========================================================= */
(function (global) {
  'use strict';

  /* ---------- Impurity Score weighting (quality-weighted average) ---------- */
  const BASE_WEIGHTS = { imdb: 1.0, rt: 1.1, mc: 1.4, letterboxd: 1.05, tmdb: 0.7 };
  const CONFIDENCE_CAP = 50000;
  function confidence(votes) {
    return Math.min(1, Math.log10((votes || 0) + 1) / Math.log10(CONFIDENCE_CAP));
  }

  /* ---------- Miscibility Index (critic/audience concordance) ---------- */
  const MISC_CAL = {
    imdb:       { mu: 63, sigma: 10 },
    letterboxd: { mu: 64, sigma: 11 },
    tmdb:       { mu: 66, sigma: 9 },
    popcorn:    { mu: 60, sigma: 18 },
    mcuser:     { mu: 64, sigma: 12 },
    trakt:      { mu: 72, sigma: 8 },
    tomatoes:   { mu: 61, sigma: 26 },
    metacritic: { mu: 56, sigma: 17 },
    rogerebert: { mu: 62, sigma: 22 },
  };
  const MISC_W_CRITIC   = { metacritic: 1.4, tomatoes: 1.1, rogerebert: 0.6 };
  const MISC_W_AUDIENCE = { letterboxd: 1.05, imdb: 1.0, popcorn: 0.9, mcuser: 0.8, trakt: 0.8, tmdb: 0.7 };
  const MISC_CONF_CAP = 50000;
  const MISC_DISPERSION_THRESHOLD = 0.55;
  const MISC_P_BASE = 0.08, MISC_P_SAT = 0.32, MISC_P_THRESHOLD = 0.6;
  const MISC_CONTESTED_GATE = 55;
  const MISC_TAU = 0.85;
  const MISC_M_MISCIBLE = 70, MISC_M_SPLIT = 40;
  const MISC_RELIABILITY_FLOOR = 0.35;
  // Agreement gate: when BOTH sides are clearly the same direction and strength
  // (both z >= +1, or both <= -1), that IS agreement by definition — "Loved by
  // All" / "Panned by All" mean exactly this. M measures only the *distance*
  // between C and A, so a film both sides love can still fall outside the
  // miscible window purely because one side is more enthusiastic than the other
  // (The Dark Knight: C=+1.56, A=+2.31 -> M=53 -> "partial", no phrase). The
  // gate classifies those as miscible regardless of M. It does NOT fire when the
  // audience is genuinely divided/polarized — a split audience whose mean is
  // high is not "Loved by All".
  const MISC_AGREE_Z = 1.0;

  function miscZ(x, source) {
    const c = MISC_CAL[source];
    return Math.max(-3, Math.min(3, (x - c.mu) / c.sigma));
  }
  function miscConf(votes) {
    return votes == null ? 0.5 : Math.min(1, Math.log10(votes + 1) / Math.log10(MISC_CONF_CAP));
  }
  // Two-sided polarization: needs mass in BOTH the low (1-3) and high (9-10)
  // tails of Trakt's rating distribution. A one-sided version was tried and
  // rejected — it scored unanimous acclaim as "polarizing" as an actual
  // review-bombing case, since a pile of 9s/10s alone is agreement, not division.
  function miscPolarization(distribution) {
    if (!distribution) return null;
    const total = Object.values(distribution).reduce((a, b) => a + b, 0);
    if (!total) return null;
    const low = ((distribution[1]||0) + (distribution[2]||0) + (distribution[3]||0)) / total;
    const high = ((distribution[9]||0) + (distribution[10]||0)) / total;
    const balanced = 2 * Math.min(low, high);
    return Math.max(0, Math.min(1, (balanced - MISC_P_BASE) / (MISC_P_SAT - MISC_P_BASE)));
  }

  function computeVerdict(mdb, details, trakt) {
    const criticZ = [];
    if (mdb.tomatoes && mdb.tomatoes.value != null) criticZ.push({ z: miscZ(mdb.tomatoes.value, 'tomatoes'), weight: MISC_W_CRITIC.tomatoes });
    if (mdb.metacritic && mdb.metacritic.value != null) criticZ.push({ z: miscZ(mdb.metacritic.value, 'metacritic'), weight: MISC_W_CRITIC.metacritic });
    if (mdb.rogerebert && (mdb.rogerebert.score != null || mdb.rogerebert.value != null)) {
      const pct = mdb.rogerebert.score != null ? mdb.rogerebert.score : mdb.rogerebert.value * 25;
      criticZ.push({ z: miscZ(pct, 'rogerebert'), weight: MISC_W_CRITIC.rogerebert });
    }

    const audienceZ = [];
    if (mdb.imdb && mdb.imdb.value != null) audienceZ.push({ z: miscZ(mdb.imdb.value * 10, 'imdb'), weight: MISC_W_AUDIENCE.imdb, c: miscConf(mdb.imdb.votes) });
    if (mdb.letterboxd && mdb.letterboxd.value != null) audienceZ.push({ z: miscZ(mdb.letterboxd.value * 20, 'letterboxd'), weight: MISC_W_AUDIENCE.letterboxd, c: miscConf(mdb.letterboxd.votes) });
    if (mdb.popcorn && mdb.popcorn.value != null) audienceZ.push({ z: miscZ(mdb.popcorn.value, 'popcorn'), weight: MISC_W_AUDIENCE.popcorn, c: miscConf(mdb.popcorn.votes) });
    if (mdb.metacriticuser && (mdb.metacriticuser.score != null || mdb.metacriticuser.value != null)) {
      const pct = mdb.metacriticuser.score != null ? mdb.metacriticuser.score : mdb.metacriticuser.value * 10;
      audienceZ.push({ z: miscZ(pct, 'mcuser'), weight: MISC_W_AUDIENCE.mcuser, c: miscConf(mdb.metacriticuser.votes) });
    }
    if (trakt && trakt.rating != null) audienceZ.push({ z: miscZ(trakt.rating * 10, 'trakt'), weight: MISC_W_AUDIENCE.trakt, c: miscConf(trakt.votes) });
    if (details.vote_average) audienceZ.push({ z: miscZ(details.vote_average * 10, 'tmdb'), weight: MISC_W_AUDIENCE.tmdb, c: miscConf(details.vote_count) });

    const sumWC = criticZ.reduce((a, s) => a + s.weight, 0);
    const C = sumWC ? criticZ.reduce((a, s) => a + s.weight * s.z, 0) / sumWC : null;

    const sumWcA = audienceZ.reduce((a, s) => a + s.weight * s.c, 0);
    const A = sumWcA ? audienceZ.reduce((a, s) => a + s.weight * s.c * s.z, 0) / sumWcA : null;

    if (C == null || A == null) return { unmeasured: true };

    const R_C = sumWC / Object.values(MISC_W_CRITIC).reduce((a, b) => a + b, 0);
    const R_A = sumWcA / Object.values(MISC_W_AUDIENCE).reduce((a, b) => a + b, 0);
    const R = Math.sqrt(R_C * R_A);
    if (R < MISC_RELIABILITY_FLOOR) return { unmeasured: true };

    let dispersion = null;
    if (audienceZ.length >= 2) {
      const varA = audienceZ.reduce((a, s) => a + s.weight * s.c * (s.z - A) ** 2, 0) / sumWcA;
      dispersion = Math.sqrt(varA);
    }
    const P = trakt ? miscPolarization(trakt.distribution) : null;

    const D = R * (A - C);
    const M = 100 * Math.exp(-((D / MISC_TAU) ** 2));

    const divisive = (dispersion != null && dispersion >= MISC_DISPERSION_THRESHOLD) || (P != null && P >= MISC_P_THRESHOLD);
    const contested = M < MISC_CONTESTED_GATE && divisive;
    const audienceDivided = divisive;

    let classification;
    if (M >= MISC_M_MISCIBLE) classification = 'miscible';
    else if (M >= MISC_M_SPLIT) classification = 'partial';
    else classification = D < 0 ? 'critic-darling' : 'crowd-pleaser';

    // Agreement gate (see MISC_AGREE_Z): both sides clearly agree in direction
    // and strength -> miscible, whatever the C/A distance. Suppressed when the
    // audience is divisive, since that's a real split, not consensus.
    const bothLove  = C >=  MISC_AGREE_Z && A >=  MISC_AGREE_Z;
    const bothPan   = C <= -MISC_AGREE_Z && A <= -MISC_AGREE_Z;
    const agreementGated = (bothLove || bothPan) && !divisive && classification !== 'miscible';
    if (agreementGated) classification = 'miscible';

    return { unmeasured: false, C, A, R, D, M, dispersion, P, contested, audienceDivided, classification, agreementGated };
  }

  /* ---------- Score tier thresholds (name only — color is per-app) ---------- */
  const SCORE_TIERS = [
    { min: 85, name: 'Acclaimed' },
    { min: 70, name: 'Liked' },
    { min: 50, name: 'Mixed' },
    { min: 0,  name: 'Panned' }
  ];
  function scoreTierName(pct) {
    return (SCORE_TIERS.find(t => pct >= t.min) || SCORE_TIERS[SCORE_TIERS.length - 1]).name;
  }

  /* ---------- MI phrase selection + and/but conjunction + collision rule ----------
     MI phrase semantics describe convergence behavior, not quality — "Loved
     by All" isn't a restatement of the tier, it's a statement about
     critic/audience agreement. Conjunction rule: miscible outcomes (agreement,
     whatever the direction) read "and"; critic-darling/crowd-pleaser
     (the divergence classifications) read "but" — the conjunction restates
     the classification's own meaning. */
  const MISC_CONJ = {
    "Loved by All": "and", "Panned by All": "and", "In Agreement": "and",
    "Critics' Film": "but", "Audience's Film": "but"
  };

  // Derive the MI phrase from a computeVerdict() result. Partial and
  // Unmeasured verdicts intentionally return null — the ambiguous middle
  // stays silent rather than forcing a phrase.
  function phraseForVerdict(verdict) {
    if (!verdict || verdict.unmeasured || verdict.classification === 'partial') return null;
    if (verdict.classification === 'miscible') {
      if (verdict.C >= 1 && verdict.A >= 1) return 'Loved by All';
      if (verdict.C <= -1 && verdict.A <= -1) return 'Panned by All';
      return 'In Agreement';
    }
    if (verdict.classification === 'critic-darling') return "Critics' Film";
    if (verdict.classification === 'crowd-pleaser') return "Audience's Film";
    return null;
  }

  // Builds the structural pieces of "<Tier> and/but <MI phrase>" without
  // choosing any color — each app applies its own tier color to whichever
  // segments this says should be tier-colored.
  //   { onlyTier: true,  tierWord }                              -> tier alone (no MI phrase)
  //   { collapsed: true, miscWord }                               -> "Panned by All" collision case
  //   { tierWord, conjWord, miscWord, miscTierColored }           -> normal case
  function buildVerdictParts(tierName, miscPhrase) {
    if (!tierName) return null;
    if (!miscPhrase) {
      return { onlyTier: true, collapsed: false, tierWord: tierName };
    }
    if (tierName === 'Panned' && miscPhrase === 'Panned by All') {
      return { onlyTier: false, collapsed: true, miscWord: miscPhrase };
    }
    const conj = MISC_CONJ[miscPhrase] || 'and';
    return {
      onlyTier: false, collapsed: false,
      tierWord: tierName, conjWord: conj, miscWord: miscPhrase,
      miscTierColored: conj === 'and'
    };
  }

  global.Scoring = {
    // Impurity Score
    BASE_WEIGHTS, CONFIDENCE_CAP, confidence,
    // Miscibility Index
    MISC_CAL, MISC_W_CRITIC, MISC_W_AUDIENCE, MISC_CONF_CAP,
    MISC_DISPERSION_THRESHOLD, MISC_P_BASE, MISC_P_SAT, MISC_P_THRESHOLD,
    MISC_CONTESTED_GATE, MISC_TAU, MISC_M_MISCIBLE, MISC_M_SPLIT, MISC_RELIABILITY_FLOOR,
    MISC_AGREE_Z,
    miscZ, miscConf, miscPolarization, computeVerdict,
    // Tiers + phrasing
    SCORE_TIERS, scoreTierName,
    MISC_CONJ, phraseForVerdict, buildVerdictParts
  };
})(window);
