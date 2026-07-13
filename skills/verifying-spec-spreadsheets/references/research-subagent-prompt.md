# Per-community research subagent prompt (template)

Dispatch one subagent per community (they're independent — run in parallel). Fill in
the `{{...}}` slots. The no-fabrication framing and the **count-reconciliation** step
are load-bearing — keep them.

> Dispatch tip: give each subagent a SMALL list (one division) and have it process the
> communities itself. Do NOT instruct a subagent to spawn its own sub-subagents — that
> fragments the return into many messages. If you must batch, keep it one agent = one list.

---

You capture EVERY floor plan in EVERY in-scope lot-size collection for each community
below — this applies whether you are **verifying** an already-filled community or
**enriching** a blank one. Go to the builder link, find how many floor plans the builder
lists for the community (the "N Plans" count), then find and capture every one of those
plans. Accuracy is critical: do NOT guess or fabricate. Only report values you can confirm
from a real web source, and cite the exact URL for each. "NOT FOUND" / "could not confirm"
is a valid, useful answer — leave such fields blank and flag them.

CONTEXT: This is a Dream Finders Homes (DFH) investor list. DFH builds under other brand
names in some divisions — in TX (Austin, Houston, Dallas, San Antonio) it builds as
**Coventry Homes** (coventryhomes.com); Orlando may use Craft Homes. For a
`{{DIVISION}}` community, search **{{BRAND_TO_SEARCH_FIRST}}** first. If a builder page
returns HTTP 403/blocked, fall back to WebSearch snippets + accessible third parties
(local news, HAR/MLS, newhomesource, the POA site) and CAP confidence at `medium`.

## The completeness protocol — do ALL of it

1. **Enumerate every collection.** DFH/Coventry organize plans into lot-size / product
   *collections*, shown as cards or tabs — each with a NAME (e.g. "Amberly 40'/50'/60'",
   "Escondido 45'/50'/60'", "Townhomes"), a **stated plan count** ("N Plans" badge), and
   a "Starting at $". Collections are sometimes separate URLs (`…/escondido-45/`,
   `…/escondido-50/`). Record every collection: name, lot_width, product, stated_count,
   starting_price.
2. **Decide scope from the row name:** a specific width (`45'`) → that collection; a
   product (TH/Duplex/Paired/Villa/SFD) → all plans of that product; a section/phase
   (`Sec. 5`, `Ph. 3`) → the matching width collection, and NOTE sections aren't broken
   out online; a **bare community name** → **EVERY** collection (all sizes & products).
3. **Capture every plan card** in each in-scope collection: plan, "From $" price (the
   Base Retail Price), beds/baths (verbatim; ranges OK), SF, stories, garages, lot width,
   product. The plan list is usually at the **bottom of the page** under a "Floor Plans"
   heading.
   - **The community LANDING page is a trap.** Its floor-plan cards are JavaScript /
     lazy-loaded, so a plain text fetch sees only the **first one or two**, and it prints the
     collection "Starting at $" floor on **every** card (so different plans look identically
     priced, and QMI prices leak in). **Always open the dedicated collection page**
     (`…/<community>-single-family-homes/`, `…/<community>-townhomes/`, `…/escondido-50/`) —
     it lists every plan with its **true per-plan From $**.
   - **If your fetch returns fewer cards than the stated "N Plans" count, the JS did not
     render — ESCALATE, do not under-report.** In order: (a) open the dedicated collection
     URL directly; (b) load the page in a **JS-capable browser** (Claude-in-Chrome MCP
     `mcp__Claude_in_Chrome__*`, or computer-use); (c) **take a screenshot of the floor-plans
     section and read the plans off the image**. Do whatever it takes to capture all N plans
     accurately, every single time.
4. **ASSERT coverage.** For every collection `captured_count` MUST equal the page's
   `stated_count` — do not stop until they match (or you've exhausted browser+screenshot and
   can name exactly which plans are missing). Report both. Do NOT pad with guesses, and never
   let the count silently shrink. This count-match is the whole point.
4b. **FLAG every change (verification rows).** When the community already has rows in the
   sheet, compare each live value to the sheet: plan **added/removed**, **renamed**, or a
   changed **price / SF / beds-baths / stories / garages**. List every difference in `notes`
   AND return the corrected live values in `floor_plans` (with `coverage` reflecting the live
   count). A flagged change is **mandatory to apply** downstream — the caller will turn your
   returned roster into a `reconciliation` override. Only keep an old value if you could not
   confirm a live replacement (blocked/404/QMI-only) — then say so.
5. **Lat/long** only if community-precise on the page; else give a sales-office/model
   **street address** to geocode.

WHERE THE GOOD DATA LIVES: the **"FLOOR PLANS — AVAILABLE IN <community>"** card row (or
each collection's page). The *From $* figure is the Base Retail Price. Prefer these over
aggregators/MLS. Quick-move-in (QMI) listings are a SEPARATE list — never let a QMI price
stand in for a plan's base "From $", and don't count QMI inventory toward the plan count.

## Output — return ONLY this JSON array (one object per community)

```json
[{
  "src_row": 0, "property_name": "...", "website": "<url|null>",
  "latlong": "<lat, long|null>", "latlong_confidence": "high|medium|low|null",
  "geocode_address": "<street address if latlong null>",
  "collections": [{"name":"Amberly 50'","lot_width":"50'","product":"Single Family","stated_count":12,"captured_count":12,"starting_price":340990}],
  "floor_plans": [{"plan":"","unit_type":"3 Bed / 2 Bath","sf":0,"base_price":0,"stories":0,"garages":0,"lot_width":"","product":"","source":"","confidence":"high"}],
  "coverage": "40' 5/5; 50' 12/12; 60' 5/5 = 22/22 OK",
  "amenities": "<|null>", "hoa": "<|null>", "delivery": "<status|null>",
  "notes": "what was left blank/why; any collection where captured<stated; section/phase caveats",
  "sources": ["url"]
}]
```

Numbers as integers (no `$`, no commas; SF ranges → lower number). `unit_type` is
beds/baths ONLY (product type goes in `product`). Every `floor_plans` entry carries its
`lot_width` so collections stay distinguishable. Do not invent plan names, prices, SF,
stories, or garages. The `coverage` string flows straight into the output's **Plan
Coverage (captured/stated)** column, so make it precise.
