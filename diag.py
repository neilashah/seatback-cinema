#!/usr/bin/env python3
"""
diag.py — Make ONE TMDB call and report exactly what happens.
Tells us in ~5 seconds whether the problem is the API key, the network,
SSL, or genuinely just slow responses.

Run:  python3 diag.py
"""
import os, sys, json, time, ssl
from urllib.parse import urlencode
from urllib.request import urlopen, Request
from urllib.error import HTTPError, URLError

key = os.environ.get("TMDB_KEY", "")
print(f"1. TMDB_KEY present: {bool(key)}  (length {len(key)})")
if not key:
    print("   -> The key isn't set in this Terminal. Re-run: export TMDB_KEY=your_key")
    sys.exit()

url = "https://api.themoviedb.org/3/search/movie?" + urlencode(
    {"api_key": key, "query": "Parasite", "year": "2019"})

print("2. Calling TMDB once (Parasite 2019)...")
t0 = time.time()
try:
    req = Request(url, headers={"User-Agent": "impure-cinema-poc"})
    with urlopen(req, timeout=15) as r:
        data = json.loads(r.read())
    dt = time.time() - t0
    n = len(data.get("results", []))
    print(f"   -> SUCCESS in {dt:.1f}s, {n} results")
    if n:
        top = data["results"][0]
        print(f"      top hit: {top.get('title')} ({(top.get('release_date') or '')[:4]}) id={top.get('id')}")
    print("\nConnectivity is fine. If the main script was slow, tell Claude the time above.")
except HTTPError as e:
    dt = time.time() - t0
    print(f"   -> HTTP ERROR {e.code} in {dt:.1f}s")
    if e.code == 401:
        print("      401 = key rejected. Double-check you copied the v3 API key correctly.")
    elif e.code == 429:
        print("      429 = rate limited. We'll slow the script down.")
    else:
        print(f"      {e.reason}")
except URLError as e:
    dt = time.time() - t0
    print(f"   -> CONNECTION FAILED in {dt:.1f}s: {e.reason}")
    print("      This is why every title took ~15s (4 retries). Likely causes:")
    print("      - No internet / behind a captive portal or VPN")
    print("      - Corporate firewall or SSL inspection blocking api.themoviedb.org")
    if isinstance(getattr(e, 'reason', None), ssl.SSLError):
        print("      - SSL certificate problem (common on fresh Mac Python installs):")
        print("        run:  /Applications/Python*/Install\\ Certificates.command")
