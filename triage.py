#!/usr/bin/env python3
"""
triage.py — Claude's manual, knowledge-based triage of the 195 scraped
titles, as a stand-in for the live TMDB run (which needs Neil's key).

This is a HUMAN ESTIMATE of how each title will behave against the matcher,
not a live API result. It exists to size the override table and show WHERE
the pain is. Every title not listed below is assumed 'auto' (an unambiguous
catalog film TMDB's top result nails without a year).

Buckets:
  review : exact title, but a remake/original or same-name collision — a
           YEAR resolves it. These are safe once you scrape the detail view.
  thin   : will resolve on TMDB, but it's a doc/short/sports/gala film that
           likely has no RT/MC/critic data — IC score will render mostly empty.
  hard   : very new (2025-26 festival), obscure, foreign, or stylized title
           ("ONE IN A MILL10N") that may fuzzy-match wrong or miss entirely —
           the real override candidates.
"""

REVIEW = {  # year disambiguates
    "Alice in Wonderland", "Anaconda", "Beauty and the Beast", "Christy",
    "Cinderella", "Close", "The Great Gatsby", "Hercules",
    "Kiss of the Spider Woman", "The Lion King", "The Little Mermaid",
    "Mercy", "Mulan", "Murder on the Orient Express", "Point Break",
    "Pocahontas", "The Running Man", "Sleeping Beauty", "Wuthering Heights",
    "Wild", "Milk", "GOAT", "Bambi", "One Hundred and One Dalmatians",
    "The Hunchback of Notre Dame", "Protector",
}

THIN = {  # resolves but IC ratings likely sparse/absent
    "2025 Masters Official Film", "The 2019 Masters: A Sunday Unlike Any Other",
    "Far Far Away Idol", "Puss in Boots: The Three Diablos", "Shrek 3-D",
    "Shrek the Musical", "Music Box: Wizkid: Long Live Lagos", "H Is for Hawk",
    "The Alabama Solution", "Why We Dream", "We Shall Not Be Moved",
    "It's Never Over, Jeff Buckley",
}

HARD = {  # very new / obscure / foreign / stylized — override candidates
    "1st Kiss", "A Poet", "Colours of Time", "Solo Mio", "Mother Tongue",
    "Looking for Her", "Love on Trial", "My First of May", "My Tennis Maestro",
    "We Girls", "Miss Boots", "Mannu Kya? Karegga", "The Shadow's Edge",
    "ONE IN A MILL10N", "The Stage", "Play Dirty", "Sarah's Oil",
    "The Heist of the Century", "The Richest Woman in the World",
    "Dead Man's Wire", "Midwinter Break", "The Other Way Around",
    "My Father's Shadow", "Solo Mio", "Love Is All You Need",
}

def main():
    with open("titles.tsv", encoding="utf-8") as f:
        titles = [ln.split("\t")[0].strip() for ln in f if ln.strip()]

    buckets = {"auto": [], "review": [], "thin": [], "hard": []}
    for t in titles:
        if t in HARD:      buckets["hard"].append(t)
        elif t in THIN:    buckets["thin"].append(t)
        elif t in REVIEW:  buckets["review"].append(t)
        else:              buckets["auto"].append(t)

    total = len(titles)
    print(f"total titles: {total}\n")
    for b in ("auto", "review", "thin", "hard"):
        n = len(buckets[b])
        print(f"{b:7} {n:3}  {n/total*100:5.1f}%")
    print("\n--- review (year fixes these) ---")
    print(", ".join(sorted(buckets["review"])))
    print("\n--- thin data (IC score will be sparse) ---")
    print(", ".join(sorted(buckets["thin"])))
    print("\n--- hard (likely overrides) ---")
    print(", ".join(sorted(buckets["hard"])))

if __name__ == "__main__":
    main()
