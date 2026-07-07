---
name: fetching-kb-home-included-features
description: Use when asked to get, fetch, download, or share the "Included Features" (standard features) for a KB Home / KB Homes community — e.g. "what's included at [community] in [city]", or when given a kbhome.com community link
---

# Fetching KB Home Included Features

## Overview

Every KB Home community has a community-details page with tabs, one of which is **Included Features**. Clicking it opens a shareable PDF listing the standard features for that community. This structure is consistent across all KB communities nationwide.

**Core principle:** Build the community-details URL from the division and community name, locate the Included Features link on that page, download the PDF, and share it with your human partner.

## URL Formula

```
https://www.kbhome.com/new-homes-{division}/{community-slug}/community-details
```

Example — Seaton Hollow in the Jacksonville/St. Augustine division:

```
https://www.kbhome.com/new-homes-jacksonville-st-augustine-area/seaton-hollow/community-details
```

- `{division}` is the metro-area slug (e.g. `jacksonville-st-augustine-area`). Some divisions include an `-area` suffix, some don't.
- `{community-slug}` is the lowercased, hyphenated community name (e.g. `seaton-hollow`).

**If you don't know the exact slugs**, web-search `site:kbhome.com "<community name>" community-details` (optionally with the city/state) and use the URL from the results instead of guessing.

## Process

1. **Get the community-details URL** via the formula above, or via web search if the slug is uncertain. A 404 means a wrong slug — search, don't retry variations blindly.
2. **Try a direct fetch first** (WebFetch or curl) of the community-details page, and ask for links whose text or href matches `included features` / `.pdf`.
3. **If the fetch returns 403** — kbhome.com uses bot protection that commonly blocks non-browser clients — fall back to real browser automation:
   ```bash
   node fetch-included-features.js <community-details-url> [output.pdf]
   ```
   The script (in this skill's directory) launches headless Chromium, finds the Included Features link (following it through clicks/popups if it's JS-driven), verifies the response is a PDF, and saves it. Requires `playwright` (`npm i playwright`); set `CHROMIUM_PATH` if using a pre-installed browser.
4. **Deliver the result:** send the downloaded PDF file to your human partner and include the direct PDF URL so they can share it.

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Guessing division slugs repeatedly after a 404 | One search: `site:kbhome.com "<community>" community-details` |
| Treating a 403 as "page doesn't exist" | 403 = bot protection, not a bad URL. Switch to the browser script. |
| Reporting the page URL instead of the PDF | The deliverable is the Included Features **PDF** (file + direct URL). |
| Saving an HTML error page as `.pdf` | Verify content-type / `%PDF` magic bytes before sharing (the script does this). |
