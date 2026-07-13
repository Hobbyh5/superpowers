"""
geocode.py — Resolve community lat/long automatically, with confidence tagging.

Zero dependencies (stdlib urllib only) and NO API KEY:
  1. US Census Geocoder  — free, US street addresses, rooftop/parcel precision.
  2. Nominatim (OpenStreetMap) — fallback for place/POI/city queries (worldwide).

Confidence is honest about precision so we don't manufacture accuracy:
  - high   : matched a street address / building (community-precise)
  - medium : matched a neighbourhood / place / POI
  - low    : matched only a city/zip/administrative centroid (NOT the community)

By policy (matching the rest of this skill) only high/medium results are written
into the Lat/Long cell; low (city-level) results are reported but LEFT BLANK and
flagged, unless you pass --allow-city.

Usage:
  # Geocode a queries file -> results file
  python geocode.py --queries geocode_queries.json --out geocode_results.json

  # Geocode and patch latlong straight into an enrichment payload
  python geocode.py --queries geocode_queries.json --patch-payload payload.json

  # Prove the parsing works with no network (uses bundled sample responses)
  python geocode.py --selftest

queries file shape: { "<src_row>": "12048 Moonlight Path Dr, Conroe, TX 77304", ... }
A query should be the most precise string available — a sales-office / model-home
street address geocodes best; "Community Name, City, ST" is an acceptable fallback.
"""
from __future__ import annotations

import json
import re
import sys
import time
import urllib.parse
import urllib.request

USER_AGENT = "superpowers-verifying-spec-spreadsheets/1.0 (+geocode.py; contact: set-your-email)"
CENSUS_URL = "https://geocoding.geo.census.gov/geocoder/locations/onelineaddress"
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
NOMINATIM_MIN_INTERVAL = 1.1  # seconds; OSM usage policy is <= 1 req/sec

# Nominatim feature classes that count as community-precise vs city-level.
_HIGH_TYPES = {"house", "building", "residential"}
_MED_CLASSES = {"place", "leisure", "amenity", "highway", "landuse"}
_MED_TYPES = {"neighbourhood", "suburb", "quarter", "hamlet", "locality", "village"}
_LOW_TYPES = {"city", "town", "administrative", "postcode", "county", "state"}


class _Clock:
    """Monotonic last-call tracker for rate limiting (avoids global Date use)."""
    def __init__(self):
        self.last = 0.0

    def wait(self, interval):
        now = time.monotonic()
        delta = interval - (now - self.last)
        if delta > 0:
            time.sleep(delta)
        self.last = time.monotonic()


_nominatim_clock = _Clock()


def _get(url, params, timeout=25):
    qs = urllib.parse.urlencode(params)
    req = urllib.request.Request(f"{url}?{qs}", headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _fmt(lat, lon):
    return f"{float(lat):.6f}, {float(lon):.6f}"


def parse_census(data):
    """Return (latlong, matched, confidence) or None from a Census response dict."""
    matches = (data.get("result", {}) or {}).get("addressMatches", []) or []
    if not matches:
        return None
    m = matches[0]
    coords = m.get("coordinates", {})
    if "y" not in coords or "x" not in coords:
        return None
    return (_fmt(coords["y"], coords["x"]), m.get("matchedAddress", ""), "high")


def parse_nominatim(results):
    """Return (latlong, matched, confidence) or None from a Nominatim result list."""
    if not results:
        return None
    r = results[0]
    typ = (r.get("type") or "").lower()
    cls = (r.get("class") or "").lower()
    addrtype = (r.get("addresstype") or "").lower()
    if typ in _HIGH_TYPES or addrtype in {"building", "house"}:
        conf = "high"
    elif typ in _LOW_TYPES or addrtype in {"city", "town", "state", "postcode", "county"}:
        conf = "low"
    elif cls in _MED_CLASSES or typ in _MED_TYPES:
        conf = "medium"
    else:
        conf = "low"
    return (_fmt(r["lat"], r["lon"]), r.get("display_name", ""), conf)


_ZIP_RE = re.compile(r"\b(\d{5})(?:-\d{4})?\b")


def _extract_zip(q):
    # Take the LAST 5-digit token: ZIP sits at the end of a US address, whereas a
    # leading 5-digit run is the house number (e.g. "46409 Saddleback Dr ... 80102").
    matches = _ZIP_RE.findall(q or "")
    return matches[-1] if matches else None


def _extract_city_state(q):
    """Best-effort '..., City, ST ...' -> ('City', 'ST'). Returns (None, None) on miss."""
    parts = [p.strip() for p in (q or "").split(",")]
    for i, p in enumerate(parts):
        toks = p.split()
        if toks and len(toks[0]) == 2 and toks[0].isalpha() and toks[0].isupper():
            return (parts[i - 1] if i > 0 else None), toks[0]
    return None, None


def geocode_one(query):
    """Geocode a single query. Returns dict with latlong/confidence/matched/source/error.

    Fallback ladder (stops at first hit):
      1. US Census street match (rooftop)            -> high
      2. Nominatim full-address match                -> high/medium
      3. Nominatim ZIP-code centroid (approximate)   -> low  (tier=zip)
      4. Nominatim city/state centroid (approximate) -> low  (tier=city)
    Steps 3-4 exist so a brand-new-construction address that no street database
    knows yet still yields an approximate, clearly-labelled community location
    instead of nothing. They stay confidence 'low' so the leave-blank policy still
    skips them unless the caller opts in (--allow-city / allow_city)."""
    out = {"query": query, "latlong": None, "confidence": None,
           "matched": None, "source": None, "error": None, "tier": None}
    # 1) Census (best for US street addresses)
    try:
        data = _get(CENSUS_URL, {"address": query, "benchmark": "Public_AR_Current",
                                 "format": "json"})
        parsed = parse_census(data)
        if parsed:
            out.update(latlong=parsed[0], matched=parsed[1], confidence=parsed[2],
                       source="US Census Geocoder")
            return out
    except Exception as e:  # noqa: BLE001 - network/parse, fall through to OSM
        out["error"] = f"census: {e}"
    # 2) Nominatim (place/POI/city fallback)
    try:
        _nominatim_clock.wait(NOMINATIM_MIN_INTERVAL)
        results = _get(NOMINATIM_URL, {"q": query, "format": "json", "limit": 1,
                                       "addressdetails": 0})
        parsed = parse_nominatim(results)
        if parsed:
            out.update(latlong=parsed[0], matched=parsed[1], confidence=parsed[2],
                       source="OpenStreetMap/Nominatim", error=None)
            return out
        out["error"] = (out["error"] or "") + " | nominatim: no match"
    except Exception as e:  # noqa: BLE001
        out["error"] = (out["error"] or "") + f" | nominatim: {e}"
    # 3) ZIP-code centroid (approximate — for new streets absent from street DBs)
    zc = _extract_zip(query)
    if zc:
        try:
            _nominatim_clock.wait(NOMINATIM_MIN_INTERVAL)
            results = _get(NOMINATIM_URL, {"postalcode": zc, "country": "USA",
                                           "format": "json", "limit": 1})
            if results:
                out.update(latlong=_fmt(results[0]["lat"], results[0]["lon"]),
                           matched=f"ZIP {zc} centroid", confidence="low", tier="zip",
                           source="OpenStreetMap/Nominatim (ZIP centroid)", error=None)
                return out
        except Exception as e:  # noqa: BLE001
            out["error"] = (out["error"] or "") + f" | zip: {e}"
    # 4) city/state centroid (last resort, coarsest)
    city, st = _extract_city_state(query)
    if city and st:
        try:
            _nominatim_clock.wait(NOMINATIM_MIN_INTERVAL)
            results = _get(NOMINATIM_URL, {"city": city, "state": st, "country": "USA",
                                           "format": "json", "limit": 1})
            if results:
                out.update(latlong=_fmt(results[0]["lat"], results[0]["lon"]),
                           matched=f"{city}, {st} centroid", confidence="low", tier="city",
                           source="OpenStreetMap/Nominatim (city centroid)", error=None)
                return out
        except Exception as e:  # noqa: BLE001
            out["error"] = (out["error"] or "") + f" | city: {e}"
    return out


def geocode_queries(queries):
    return {row: geocode_one(q) for row, q in queries.items()}


def patch_payload(payload, results, allow_city=False, label_approx=False):
    """Write geocoded latlongs into payload enrichments.

    high/medium results are always written. low (ZIP/city centroid) results are
    written only when ``allow_city`` or ``label_approx`` is set; with ``label_approx``
    the value is suffixed " (approx.)" so an approximate centroid is never mistaken
    for a rooftop match. ``--fill-approx`` on the CLI sets both, which is the standard
    way to fill EVERY division (new-construction streets that no street DB knows yet
    still get an approximate, labeled location instead of a blank).
    """
    enr = payload.setdefault("enrichments", {})
    written = skipped = 0
    for row, res in results.items():
        ll, conf = res.get("latlong"), res.get("confidence")
        if not ll:
            continue
        approx = conf == "low"
        if approx and not (allow_city or label_approx):
            skipped += 1
            continue
        value = ll + " (approx.)" if (approx and label_approx) else ll
        entry = enr.setdefault(str(row), {})
        entry["latlong"] = {"value": value, "source": res.get("source"), "confidence": conf}
        # Trim the "LAT/LONG BLANK" caveat now that we have a value.
        note = entry.get("notes") or ""
        if "LAT/LONG BLANK" in note:
            entry["notes"] = note + f"  [geocoded {conf}: {res.get('matched','')}]"
        written += 1
    return written, skipped


# --------------------------------------------------------------------------- #
def _selftest():
    census_sample = {"result": {"addressMatches": [{
        "matchedAddress": "12048 MOONLIGHT PATH DR, CONROE, TX, 77304",
        "coordinates": {"x": -95.5123, "y": 30.2987}}]}}
    assert parse_census(census_sample) == ("30.298700, -95.512300",
                                           "12048 MOONLIGHT PATH DR, CONROE, TX, 77304",
                                           "high"), "census parse failed"
    assert parse_census({"result": {"addressMatches": []}}) is None
    nom_house = [{"lat": "30.21", "lon": "-95.84", "type": "house",
                  "class": "place", "addresstype": "building",
                  "display_name": "Cypress Green, Hockley, TX"}]
    assert parse_nominatim(nom_house)[2] == "high"
    nom_city = [{"lat": "30.02", "lon": "-95.84", "type": "city",
                 "class": "place", "addresstype": "city",
                 "display_name": "Hockley, TX"}]
    assert parse_nominatim(nom_city)[2] == "low"
    nom_hood = [{"lat": "30.05", "lon": "-95.80", "type": "neighbourhood",
                 "class": "place", "addresstype": "neighbourhood",
                 "display_name": "Some Subdivision"}]
    assert parse_nominatim(nom_hood)[2] == "medium"
    # patch policy: low skipped by default, kept with allow_city
    pl = {"enrichments": {"5": {"notes": "LAT/LONG BLANK (city only)"}}}
    w, s = patch_payload(pl, {"5": {"latlong": "1.0, 2.0", "confidence": "low",
                                    "source": "x", "matched": "y"}})
    assert (w, s) == (0, 1) and "latlong" not in pl["enrichments"]["5"]
    w, s = patch_payload(pl, {"5": {"latlong": "1.0, 2.0", "confidence": "high",
                                    "source": "x", "matched": "y"}})
    assert w == 1 and pl["enrichments"]["5"]["latlong"]["value"] == "1.0, 2.0"
    print("selftest OK (parsing + confidence + patch policy)")


def main(argv):
    import argparse
    ap = argparse.ArgumentParser(description="Geocode communities (Census -> OSM).")
    ap.add_argument("--queries", help="JSON: {src_row: query string}")
    ap.add_argument("--out", help="write full geocode results JSON here")
    ap.add_argument("--patch-payload", help="enrichment payload JSON to patch in place")
    ap.add_argument("--allow-city", action="store_true",
                    help="also write low (city-level) results into Lat/Long (unlabeled)")
    ap.add_argument("--fill-approx", action="store_true",
                    help="write ZIP/city centroids labeled '(approx.)' — the standard way "
                         "to fill Lat/Long for EVERY division each run")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args(argv)

    if args.selftest:
        _selftest()
        return
    if not args.queries:
        ap.error("--queries is required (or use --selftest)")

    queries = json.load(open(args.queries))
    results = geocode_queries(queries)
    n_ok = sum(1 for r in results.values() if r["latlong"])
    by_conf = {}
    for r in results.values():
        by_conf[r["confidence"]] = by_conf.get(r["confidence"], 0) + 1
    print(f"geocoded {n_ok}/{len(queries)} | by confidence: {by_conf}")
    for row, r in results.items():
        if not r["latlong"]:
            print(f"  row {row}: NO MATCH ({r.get('error')})")

    if args.out:
        json.dump(results, open(args.out, "w"), indent=1)
        print(f"wrote {args.out}")
    if args.patch_payload:
        payload = json.load(open(args.patch_payload))
        w, s = patch_payload(payload, results, allow_city=args.allow_city,
                             label_approx=args.fill_approx)
        json.dump(payload, open(args.patch_payload, "w"), indent=1)
        note = "" if (args.allow_city or args.fill_approx) else " (use --fill-approx to include them, labeled)"
        print(f"patched {args.patch_payload}: wrote {w} latlongs, "
              f"skipped {s} approximate{note}")


if __name__ == "__main__":
    main(sys.argv[1:])
