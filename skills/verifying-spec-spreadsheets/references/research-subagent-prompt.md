# Per-community research subagent prompt (template)

Dispatch one subagent per blank community (they're independent — run in parallel).
Fill in the `{{...}}` slots. The no-fabrication framing is load-bearing — keep it.

---

You are filling in MISSING data in an investor spreadsheet for a homebuilder
community. Accuracy is critical: do NOT guess or fabricate. Only report values
you can confirm from a real web source, and cite the exact URL for each. If you
cannot find a community page, say so clearly and leave fields blank — "NOT FOUND"
is a valid and useful answer.

CONTEXT: This is a Dream Finders Homes (DFH) investor list. DFH builds under
other brand names in some divisions — in TX (Austin, Houston, Dallas, San
Antonio) it builds as **Coventry Homes** (coventryhomes.com). For a `{{DIVISION}}`
community, search **{{BRAND_TO_SEARCH_FIRST}}** first, then a general web search,
then the master-planned community's own site.

NOTE: builder sites (dreamfindershomes.com / coventryhomes.com) may return HTTP
403 to automated fetches. If so, use WebSearch result snippets (which quote those
pages) plus accessible third-party sources (local news, HAR/MLS, newhomesource,
the community POA site). Mark such data as lower confidence.

Community to research: **{{PROPERTY_NAME}}**, {{DIVISION}} division ({{CITY_HINT}}).
Note any lot-width / section qualifier in the name (e.g. "45' - Section 23") and
try to confirm whether the plans you find belong to that specific subset.

Return a structured report:
- BUILDER_BRAND: + why
- COMMUNITY_URL: url or "NOT FOUND"
- CITY_STATE:
- LATLONG: community-precise decimal lat,long + how derived + confidence
  (high/med/low); if only city-level is available, say so and give the city
  coord separately — do NOT present it as the community's coordinates
- PLANS: list (name | beds/baths | SF | price | stories | garages | lot width |
  product) — omit any field you cannot confirm rather than guessing
- AMENITIES: or "unconfirmed"
- HOA: or "unconfirmed" (note if sources conflict)
- DELIVERY_STATUS:
- SOURCE_URLS: every URL you fetched

Do not invent plan names, prices, story counts, or garage counts. Leave them out.
