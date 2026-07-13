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

> **Standard run checklist (do all of these every time):**
> 1. Parse (step 1).
> 2. For **every** community — populated *and* blank — open the builder link, get the
>    **stated "N Plans" count** from the **dedicated collection page**, capture all N plans
>    (escalate to a JS browser / screenshot if a static fetch under-renders), and
>    **assert captured == stated** (step 3a). This is the floor-plan capture protocol and it is
>    mandatory on verification too, not just enrichment.
> 3. **Geocode EVERY community across ALL divisions** with `--fill-approx` (step 3b) —
>    so no division is left with blank Lat/Long; approximate fills are labeled `(approx.)`.
> 4. **Always produce the Reconciled (Live) tab** — include a `reconciliation` section in the
>    payload. **Every** confirmed live change (price/name/spec/count/…) is **mandatory** to
>    record as an override so it lands on that tab (steps 2 & 4b).
> The output is a **5-sheet** workbook every time.

### 1. Parse the workbook into a flat model
```
python scripts/spec_model.py <workbook.xlsx>
```
Prints a JSON summary: total communities, how many are blank, per-division
counts, and the blank list with which fields each is missing. The parser carries
the Division value forward across sub-communities and treats any row with a
Property Name as a new community block.

### 2. Verify EVERY populated community (not a sample)
Open the builder link for **every** already-filled community — verification is held to
the *same* completeness bar as enrichment. For each, confirm: website resolves and is the
right community; lat/long is plausible for the stated city; and — critically — **re-pull the
full floor-plan roster from the builder's dedicated collection page and reconcile the count**
(see §3a). The source sheet is frequently **incomplete** (e.g. 10 of 15 plans) or **stale**
(lists plans the builder has retired, or old prices). Do **not** assume a populated row is
complete just because it has data.

Every difference you find — a missing plan, an extra/retired plan, a changed name, a changed
price, SF, beds/baths, stories, or garages — is recorded **two** ways:
1. as a line in the **Verification Report** (what differs and the source), and
2. as a **`reconciliation` override** so the live value lands on the **Reconciled (Live)** tab.

This second step is **mandatory, not optional** (see §4b). "Report, don't fix silently" means
the **Spec List keeps the user's original** value as an audit trail — it does **not** mean a
confirmed change can be skipped. If you confirmed it live, it **must** appear on the Reconciled
tab. The only reason to leave a value original is that you could **not** confirm a live
replacement (404/blocked/QMI-only) — and then you say so in the note.

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

### 3a. MANDATORY floor-plan capture protocol — defeat the JavaScript lazy-load
> **This is wired into every verification AND every enrichment. Do it for every
> community, every time. No exceptions.**

The builder's floor-plan cards are **JavaScript-rendered and lazy-loaded**, and this breaks
naïve scraping in two specific ways you MUST defend against:

- **The community *landing* page (`…/spring-haven/`) is a trap.** A static fetch (WebFetch =
  raw HTML → markdown) sees only the **first one or two** plan cards; the rest load client-side
  and are invisible. Worse, the landing page often prints the **collection "Starting at $"
  floor on every card**, so four different plans all look like they cost the same — and
  quick-move-in (QMI) prices leak in as if they were base prices.
- **The real roster lives on the *dedicated collection* page**, usually one per product/lot
  size: `…/spring-haven-single-family-homes/`, `…/spring-haven-townhomes/`, `…/escondido-50/`,
  `…/the-parklands-50/`. These list **every** plan with its **true per-plan base `From $`**.
  The plan list is typically at the **bottom of the page** under a "Floor Plans" heading with
  an **"N Plans" count badge**.

**The required steps, per community (and per collection):**
1. **Go to the builder link.** First find the community's collections and each collection's
   **stated "N Plans" count** (the badge near the floor-plans section). Write that number down —
   it is the target you must hit.
2. **Open each in-scope collection's *dedicated page*** (not just the landing page) and scroll
   to the floor-plans list at the bottom. Capture **every** card: plan name, **From $** (Base
   Retail Price — never a QMI price), beds/baths, SF, stories, garages, lot width, product.
3. **If the static fetch returns fewer cards than the stated count** (or shows one shared price
   for many plans), the JS did not render for you — **escalate, do not give up and do not
   under-report.** In order: (a) try the dedicated collection page URL directly; (b) use a
   **JS-capable browser** (the Claude-in-Chrome MCP / `mcp__Claude_in_Chrome__*`, or
   computer-use) to load the page and read the fully-rendered floor-plan list; (c) **take a
   screenshot of the floor-plans section and read the plans off the image**. Whatever it takes
   to capture all N plans accurately, every single time — do it.
4. **ASSERT `captured_count == stated_count`** for each collection before you record it. If you
   truly cannot reach the count after escalating, name which plans are missing and **flag it —
   never pad with guesses**, and never let the count silently shrink.
5. Feed the captured rows into the payload (enrichments for blanks, `reconciliation` overrides
   for populated rows whose live roster differs — see §4b).

> **Proven JS-browser recipe (Claude-in-Chrome) — use this for step 3(b).** It reliably pulls the
> full base roster off DFH/Coventry, which are server-rendered SPAs whose plan grid lazy-loads:
> - The dedicated collection URL is **`/<community>-<WIDTH>/`** (hyphenated): `…/amberly-50/`,
>   `…/amberly-60/`, `…/diamond-springs-40/`, `…/briargate-45/`, `…/creekside-estates-52/` — **not**
>   `…/amberly/50/`. All collection subpaths of a community return the same HTML and filter
>   client-side, so one page per *collection width* is enough.
> - **`navigate` the SAME url twice inside one `browser_batch`, then `find`** ("floor plan card
>   showing plan name and From price and square footage"). A single navigate + immediate `find`
>   returns the *previous* collection's stale DOM; the double-navigate forces the render. `find`
>   returns each base plan with name + true **From $** + SF (exactly the stated N).
> - **Do NOT use `get_page_text` for the roster** — it returns the QMI "article" (one move-in-ready
>   home), not the base plans. Screenshot-and-read is the last-resort fallback if `find` falls short.
> - Cards usually omit beds/baths/stories/garages (only a few show baths) — **leave those blank,
>   never fabricate.** The connection drops when Chrome idles (`list_connected_browsers` → `[]`); save
>   progress to a file, ask the user to foreground Chrome, and re-navigate (the tab id changes).
> - In the raw HTML, the `application/ld+json` `["Product","SingleFamilyResidence"]` blocks are **QMI
>   inventory homes** (specific address + price), NOT base plans — never use their price as a base
>   `From $`, but their `model` URL slug reveals plan names that have current inventory.

**Keep Product Type and Unit Type separate.** Unit Type holds only beds/baths
(e.g. "4-5 Bed / 3 Bath"); Product Type holds Single Family / Townhome / Paired /
Duplex / Villa. Never put a product type in the bed/bath slot — `build_output.py`
auto-corrects this (moves stray product words out of Unit Type), but record them
in the right field to begin with.

Run independent communities as **parallel research subagents** — each one is
self-contained. Give every subagent the no-fabrication rule and the brand-alias
context explicitly. (Give each agent a small one-division list and have it do the
work itself; don't tell agents to spawn their own sub-subagents — that fragments the
return into many messages you then have to reassemble.)

#### 3a (detail). Collection scope & count reconciliation
This applies to **populated rows too**, not just blanks — a "complete"-looking community
is often missing whole collections. A single community usually splits its plans into
lot-size / product **collections** (e.g. *Amberly 40' / 50' / 60'*, *Escondido 45'/50'/60'*,
a Townhomes collection), each shown as a card/tab with its own **stated "N Plans" count**
and sometimes its own URL (`…/amberly-50/`). The failure modes that lose plans:
(a) a whole collection is missed (Amberly's sheet had 40'+50' but not the 60'),
(b) a collection's card row lazy-loads/paginates so only the first few cards are grabbed,
(c) a spreadsheet row names one lot size but the community offers several.

The protocol (see `references/research-subagent-prompt.md`, the canonical per-community
prompt) is: **enumerate every collection → decide scope from the row name → capture every
card in each in-scope collection → ASSERT `captured_count == stated_count` per collection.**
Scope rule: a width-named row (`45'`) → that collection; a product-named row (TH/Duplex) →
all of that product; a section/phase row (`Sec. 5`) → the matching width collection (note
sections aren't broken out online); a **bare community name** → **every** collection.
If you can't reach the stated count, say which plans are missing and **flag it — never pad
with guesses**. Each community returns a `coverage` string ("40' 5/5; 50' 12/12; 60' 5/5 =
22/22 OK", or "6/10 INCOMPLETE — …") that lands in the output's **Plan Coverage
(captured/stated)** column, so completeness is visible and filterable rather than assumed.
QMI inventory is a separate list — don't count it toward the plan count or let a QMI price
replace a plan's base "From $".

### 3b. Geocode EVERY community, EVERY division (standard — do this each run)
Let `scripts/geocode.py` resolve coordinates for **all communities across all
divisions** that lack a precise Lat/Long — not just the blank ones. It is
zero-dependency and needs **no API key**. Fallback ladder (stops at first hit):
1. **US Census** street match → `high` (rooftop)
2. **Nominatim** full address → `high`/`medium`
3. **Nominatim ZIP-code centroid** → `low` (≈1–2 mi)
4. **Nominatim city/state centroid** → `low` (coarsest)

Steps 3–4 exist because brand-new-construction streets aren't in Census/OSM yet —
they'd otherwise come back blank. Build a `geocode_queries.json` of `{src_row: query}`
for every community without high/medium coords (a sales-office / model-home **street
address** is best; `"Community, City, ST"` is an acceptable fallback), then run with
**`--fill-approx`** so every division gets filled:
```
python scripts/geocode.py --queries geocode_queries.json --patch-payload payload.json --fill-approx
```
`--fill-approx` writes the `low` (ZIP/city-centroid) results too, **suffixed
`(approx.)`** so an approximate location is never mistaken for a rooftop match —
honest labeling instead of a blank. (Plain `--patch-payload` without the flag keeps
the conservative leave-blank behavior; `--allow-city` writes low results unlabeled.)
`python scripts/geocode.py --selftest` verifies the parsing/policy offline.

> Egress note: some locked-down environments block the geocoding hosts
> (`geocoding.geo.census.gov`, `nominatim.openstreetmap.org`) at the policy layer,
> just like the builder sites — geocode.py then reports `NO MATCH (... 403)` and
> writes nothing. Run it where outbound HTTPS is allowed.

### 4. Record findings as a payload, then rebuild
Write a `payload.json` (shape documented at the top of `scripts/build_output.py`)
with `verifications` and `enrichments`. Only put sourced, confident values in;
describe everything you left blank in each community's `notes`. Then:
```
python scripts/build_output.py <source.xlsx> payload.json <out.xlsx>
```
This emits a clean, un-merged workbook with **five sheets** (the Reconciled tab is
standard — see 4b):
- **Spec List** — flat, one row per plan, with Status / Confidence / Source columns
- **Reconciled (Live)** — the live-data view (always produced; see 4b)
- **Communities** — one row per community + status + **Plan Coverage (captured/stated)** (from each community's `coverage` string; pass a top-level `"coverage": {"<src_row>": "..."}` map in the payload)
- **Verification Report** — results of the verify pass
- **Needs Research** — every still-incomplete community and *why* (the flag report)

### 4b. Reconciled (Live) tab — STANDARD every run
The Spec List/Verification pass deliberately **reports** discrepancies without
changing the user's existing values. The **"Reconciled (Live)"** tab is the companion
where the **live builder data wins** — and it is produced on **every** run. Always
include a `reconciliation` section in `payload.json`; `build_output.py` then emits the
tab (inserted right after Spec List), applies the live overrides, **amber-highlights**
every changed cell, and adds a **Reconciliation Note** column.

> **MANDATORY change rule (B).** Any time you confirm — from the builder's site — a live value
> that differs from the sheet (a plan **price**, plan **name**, **SF**, **beds/baths**,
> **stories**, **garages**, **count of plans**, lat/long, website, or delivery), you **must**
> write it as a `reconciliation` override so the corrected value appears on the Reconciled
> (Live) tab. This is not optional and a flagged change may **never** be left only as prose in
> the Verification Report. A change that is *flagged* is a change that *must be applied* to the
> Reconciled tab. Use `floor_plans` to replace a whole roster (e.g. stale/short list →
> live list), `price_override` for a single plan's price, `rename_plan` to fix a name, and the
> scalar keys for cell-level fixes. Every override carries a `note` explaining what changed and
> why. The **only** exception is when you could not confirm a live replacement (page
> blocked/404, or only QMI prices exist) — then keep the original and say so in the note.

Even an empty `"reconciliation": {}` produces the tab as a clean live mirror; set
`uncolor_spec_list: true` to move all color onto it. Same no-fabrication rule: a full
roster swap needs the builder's base `From $` plan cards (not quick-move-in prices);
when only partial/QMI data exists, keep the original value and note it. Shape:
```jsonc
"reconciliation": {
  "uncolor_spec_list": true,            // move all color onto the Reconciled tab
  "overrides": {
    "<src_row or property name>": {
      "floor_plans": [ { "plan": "...", "unit_type": "3 Bed / 2.5 Bath",
                         "base_price": 282990, "sf": 1763, "stories": 2,
                         "garages": 0, "lot_width": "20'", "product": "Townhome",
                         "source": "https://...", "confidence": "high" } ],  // replace roster
      "latlong": "...", "website": "...", "delivery": "...",                  // scalar cell overrides
      "price_override": { "plan": "Jordan", "value": 241990 },               // one plan's price
      "rename_plan": { "from": "Kingston", "to": "Kinston" },                 // fix a plan name
      "note": "Why it changed / what was kept original."
    }
  }
}
```

Enriched rows are tinted green; flagged rows orange. The Spec List carries an Excel
**autofilter** on every column (Division, Property Name, Product Type, Lot Width,
Stories, Garages, Floor Plan, …) and **borders**: light-blue vertical gridlines
between every column, a thin blue line between properties, and a thick blue line
between divisions (computed by comparing each community's division to the previous
one — division is repeated on every block in the flat layout, so a plain "non-empty"
test would mark every row).

### 4c. HTML report — companion to the workbook (same inputs)
The Excel workbook stays the investor deliverable; also emit the single-file HTML
report for review and sharing — it takes the exact same inputs:
```
python scripts/build_html.py <source.xlsx> payload.json <report.html>
```
Self-contained (inline CSS/JS, no external assets, light/dark), with six views:
Overview (stat tiles + per-division rollup), Spec List, Reconciled (Live),
Communities, Verification Report, Needs Research. What it adds over the xlsx:
clickable source URLs and Google-Maps lat/long links, **old → new diffs** on the
Reconciled view (struck-through original beside the live value, retired plans
shown struck-through, added plans tagged `new`), coverage badges that flag
INCOMPLETE/short counts, and instant search/filter/sort. It honors the payload's
`uncolor_spec_list` flag and never invents data — it renders exactly what the
payload sourced. `python scripts/build_html.py --selftest` checks the rendering
offline.

### 5. HOA fees — prompt the user LAST (do not re-search)
HOA dues are **almost never published on builder pages** (DFH/Coventry list them nowhere),
so chasing them is a second exhausting round of searches across dozens of communities for
little reliable payoff. So make HOA the **final step, after the workbook is fully built**:

- Do **not** kick off another search sweep for HOA. Leave HOA blank during the main
  enrichment pass (it already lands blank for researched communities).
- HOA values the **source sheet already had** (typically on the populated communities) are
  preserved as-is — don't blank them.
- Once everything else is compiled and the 5-sheet workbook is written, **prompt the user**:
  show the list of communities still missing HOA (read it from the Communities/Needs
  Research sheet, or the payload's blank-HOA entries), and ask the user to supply whatever
  HOA figures they have — pasted in any format. Make clear "leave blank" is fine.
- Patch **only the user's answers** into the payload (`enrichments[<row>].hoa` for
  researched communities, or `reconciliation.overrides[<row>].hoa` for populated ones —
  both accept a plain string like `"$120/mo"`), then re-run `build_output.py`. Tag
  user-provided HOA confidence `high` (it's owner-sourced).
- **Do NOT write third-party/aggregator estimates** — no `(estimate)` HOA values. If the
  user doesn't supply a figure, leave HOA blank. The user can later request a *separate,
  explicit* HOA search pass if they decide it's worth chasing county/CDD/MLS records.

This keeps the one unavoidable manual step collapsed into a single ask at the very end,
instead of a fruitless search pass mid-run.

### 5b. HOA *search pass* — only when the user explicitly asks for one
If the user explicitly authorizes hunting HOA down ("try and find the HOA fees"), run a dedicated
sweep — one research subagent per division, each returning `{src_row, hoa, confidence, source, note}`
— then patch the results the same way (blank rows → `enrichments[<row>].hoa`, populated → an
`reconciliation.overrides[<row>].hoa`) and rebuild. What this run learned about sourcing HOA:
- **Builder pages still list nothing.** The single most productive source is **Jome new-home
  community listing pages** (`jome.com`), which quote a monthly/annual HOA for most DFH/Coventry
  communities — tag **medium** (listing-grade, not the association's own schedule). An **official
  HOA/management-company site or county record** (e.g. `heartlandtx.net`, a named management co.)
  occasionally gives a confirmable figure → **high**. Zillow/Redfin/Realtor/HAR/CHS-MLS detail
  pages usually **403** direct fetch, so anything from them arrives via search snippets (medium/low).
- **Do not misattribute a same-named, different-builder community's fee.** A DR Horton / KB / Lennar
  "Briargate" / "Anabelle Island" / "Castlewood" with its own POA is a common trap — only use a fee
  you can tie to the DFH/Coventry community.
- **CDD (FL) / MUD or PID (TX) / metro-district (CO)** are property-tax-style charges, **not** HOA —
  capture them in the note, never in the HOA cell.
- Expect roughly **three-quarters** of a large run to yield a (mostly medium) figure; the rest are
  brand-new / pre-launch communities with nothing published. Still **never fabricate** — blank + flag.
- Color/confidence: tag each found value and (if also recoloring the Reconciled tab) fill the HOA
  cell green/medium-orange/low-red; flag pre-existing sheet `(estimate)` values that you could not
  corroborate as red rather than silently trusting them.

### Confidence color scheme (when asked to color the Reconciled/Live tab)
green = `C6EFCE` (high) · orange = `FFCC99` (medium) · red = `FFC7CE` (low / unverified / blank).
Color plan rows by the plan's confidence, and override the **Lat/Long** and **HOA** cells with their
*own* confidence (so an approximate geocode or a soft HOA shows its true reliability even on an
otherwise-green row). Set `reconciliation.uncolor_spec_list: true` to strip the Spec List so all
color lives on the live tab.

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
| Write a lat/long that's really the city center | Leave blank; geocode a street address instead (geocode.py won't write low-confidence city centroids) |
| Fill stories/garages "because they're usually 2" | Leave blank; flag |
| Pick one of two conflicting HOA numbers | Leave blank; note both in flags |
| Write Coventry plans into a "45' / Section 23" row without confirming the subset | Write plans, but flag that the lot-width/section filter is unconfirmed |
| Mark a community verified after a 403 | Mark website "blocked"; verify only what you could (e.g. lat/long plausibility) |
| Invent a plan name to fill a row | Leave the row out; flag "plans not found" |
| Trust the plan list on the community **landing** page (lazy-loads only the first cards; shows the collection floor price on every card) | Open the **dedicated collection page** (`…-single-family-homes/`, `…-townhomes/`, `…-50/`), read the **"N Plans"** badge, capture all N (browser/screenshot if the static fetch falls short), assert `captured == stated` |
| Accept a populated row as "complete" without re-counting | Re-pull the live roster and reconcile the count — populated rows are held to the same bar as blanks |
| Leave a confirmed live change only as a note in the Verification Report | It is **mandatory** to also write it as a `reconciliation` override so it lands on the Reconciled tab |

## Files
- `scripts/spec_model.py` — parser + blank detector (openpyxl only, zero extra deps)
- `scripts/build_output.py` — rebuilds the auditable **5-sheet** output from a payload (the **Reconciled (Live)** tab is standard whenever the payload has a `reconciliation` section)
- `scripts/build_html.py` — renders the same source+payload as a single-file HTML report (stat tiles, filter/search/sort, clickable sources, old→new reconciliation diffs); `--selftest` included
- `scripts/geocode.py` — no-key geocoder (US Census → Nominatim) with confidence tiers
- `scripts/brand_aliases.json` — division → builder-brand map (extend as needed)
- `references/research-subagent-prompt.md` — copy-paste prompt for a per-community researcher
- `references/geocode_queries.json` — seed `{src_row: address}` for geocode.py
