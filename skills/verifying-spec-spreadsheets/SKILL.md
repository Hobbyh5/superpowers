---
name: verifying-spec-spreadsheets
description: Use when verifying and enriching a homebuilder "spec list" / forward-sale / investor spreadsheet (e.g. a Dream Finders Homes BTR spec list) — parse its community blocks, check existing rows against the builder's site, web-search for blank divisions/communities, and write only verified data back while leaving unverifiable fields blank and flagged.
---

# Verifying & Enriching Spec-List Spreadsheets

## Overview

Homebuilder "forward sale" / BTR spec lists are hierarchical spreadsheets: each
community is a header row (Division, Property Name, Lat/Long, Website, Delivery)
followed by one row per floor plan (price, plan, beds/baths, SF, stories,
garages), with merged cells gluing the header fields across the detail rows.
Investors get these half-filled — dozens of communities have only a name.

The job is two things, and they have **different risk profiles**:

1. **Verify** the populated communities against the authoritative source.
2. **Enrich** the blank ones with researched data.

**Core principle: a wrong number is worse than a blank cell.** This is an
investor-facing document. Never write a value you cannot source. When in doubt,
leave it blank and put it on the flag report.

## The one rule that matters

> Every value you write must have a real source URL and a confidence tag.
> Anything inferred, guessed, conflicting, or city-level-only is **left blank**
> and **flagged**, never written into a data cell.

Concretely, **leave blank + flag** when:
- The value is *inferred* ("probably 2-story", "standard 2-car garage").
- Sources *conflict* (one says HOA $1,150/yr, another says "no HOA").
- Only a *city-level* lat/long is available — that is NOT the community's
  coordinates. Record it in notes for a human to refine; do not put it in the
  Lat/Long cell.
- The page exists but its *plan names/specs* weren't found.

## Workflow

### 1. Parse the workbook into a flat model
```
python scripts/spec_model.py <workbook.xlsx>
```
Prints a JSON summary: total communities, how many are blank, per-division
counts, and the blank list with which fields each is missing. The parser carries
the Division value forward across sub-communities and treats any row with a
Property Name as a new community block.

### 2. Verify a sample of populated communities
For each, confirm: website resolves and is the right community; lat/long is
plausible for the stated city; plan names/SF/prices match. Report
discrepancies — do not "fix" the sheet silently.

### 3. Research each blank community — **mind the brand aliases**
DFH (and most national builders) build under **different brand names** in
different divisions. Search the *local brand first*. Known DFH aliases:

| Division | Brand to search |
|---|---|
| Austin, Houston, Dallas, San Antonio (TX) | **Coventry Homes** (coventryhomes.com) |
| Most other divisions | Dream Finders Homes (dreamfindershomes.com) |

(Texas also sees MainVue / Megatel under the DFH umbrella — check if Coventry
has no page.) Keep `scripts/brand_aliases.json` updated as you learn more.

For each community gather, **each with its own source URL**: official community
page, community-precise lat/long, floor plans (name, beds/baths, SF, price,
stories, garages, lot width, product type), amenities, HOA, delivery status.

**Pull plan data from the right place.** The builder community page has a
**"FLOOR PLANS — AVAILABLE IN <community>"** card row — plan name, *From $price*,
beds/baths, SF. That is the authoritative pricing/spec source; target it in
searches ("Available in <community> From $… beds baths sqft") and prefer it over
aggregators. The *From $* figure is the Base Retail Price.

**Keep Product Type and Unit Type separate.** Unit Type holds only beds/baths
(e.g. "4-5 Bed / 3 Bath"); Product Type holds Single Family / Townhome / Paired /
Duplex / Villa. Never put a product type in the bed/bath slot — `build_output.py`
auto-corrects this (moves stray product words out of Unit Type), but record them
in the right field to begin with.

Run independent communities as **parallel research subagents** — each one is
self-contained. Give every subagent the no-fabrication rule and the brand-alias
context explicitly.

### 4. Record findings as a payload, then rebuild
Write a `payload.json` (shape documented at the top of `scripts/build_output.py`)
with `verifications` and `enrichments`. Only put sourced, confident values in;
describe everything you left blank in each community's `notes`. Then:
```
python scripts/build_output.py <source.xlsx> payload.json <out.xlsx>
```
This emits a clean, un-merged workbook with four sheets:
- **Spec List** — flat, one row per plan, with Status / Confidence / Source columns
- **Communities** — one row per community + status
- **Verification Report** — results of the verify pass
- **Needs Research** — every still-incomplete community and *why* (the flag report)

Enriched rows are tinted green; flagged rows orange. The Spec List carries an Excel
**autofilter** on every column (Division, Property Name, Product Type, Lot Width,
Stories, Garages, Floor Plan, …) and **separator borders**: a thin blue line
between properties and a thick blue line between divisions (computed by comparing
each community's division to the previous one — division is repeated on every block
in the flat layout, so a plain "non-empty" test would mark every row).

## Environment caveat: builder sites are often bot-blocked

`dreamfindershomes.com` and `coventryhomes.com` return **HTTP 403** to automated
fetches (Cloudflare bot protection), and some sandboxed environments block them
at the **egress-policy** layer (403 on CONNECT). When that happens:
- **Do not** disable TLS, unset the proxy, or route around a policy denial —
  report the blocked host (see `/root/.ccr/README.md` in CC-on-web).
- Fall back to WebSearch result *snippets* (which quote the builder pages) plus
  accessible third-party sources (local news, MLS/HAR, newhomesource, the
  community's own POA site).
- Because you couldn't read the primary page directly, **cap confidence at
  `medium`** and flag liberally. Snippet-sourced data is a lead, not a fact.

## Red flags — stop and reconsider

| You're about to... | Instead |
|---|---|
| Write a lat/long that's really the city center | Leave blank; note the city coord for a human |
| Fill stories/garages "because they're usually 2" | Leave blank; flag |
| Pick one of two conflicting HOA numbers | Leave blank; note both in flags |
| Write Coventry plans into a "45' / Section 23" row without confirming the subset | Write plans, but flag that the lot-width/section filter is unconfirmed |
| Mark a community verified after a 403 | Mark website "blocked"; verify only what you could (e.g. lat/long plausibility) |
| Invent a plan name to fill a row | Leave the row out; flag "plans not found" |

## Files
- `scripts/spec_model.py` — parser + blank detector (openpyxl only, zero extra deps)
- `scripts/build_output.py` — rebuilds the auditable 4-sheet output from a payload
- `scripts/brand_aliases.json` — division → builder-brand map (extend as needed)
- `references/research-subagent-prompt.md` — copy-paste prompt for a per-community researcher
