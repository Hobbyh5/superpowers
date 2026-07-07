#!/usr/bin/env node
// Download the "Included Features" PDF from a KB Home community-details page.
//
// Usage:
//   node fetch-included-features.js <community-details-url> [output.pdf]
//
// Requires: npm i playwright
// If Playwright's browsers aren't downloaded, point CHROMIUM_PATH at an
// existing Chromium binary (e.g. a system install or /opt/pw-browsers/chromium).

const fs = require('fs');
const { chromium } = require('playwright');

const url = process.argv[2];
const outPath = process.argv[3] || 'included-features.pdf';

if (!url || !/^https:\/\/(www\.)?kbhome\.com\//.test(url)) {
  console.error('Usage: node fetch-included-features.js <kbhome.com community-details URL> [output.pdf]');
  process.exit(2);
}

const LINK_RE = /included\s*features/i;

async function savePdf(context, pdfUrl) {
  const resp = await context.request.get(pdfUrl);
  if (!resp.ok()) throw new Error(`GET ${pdfUrl} -> HTTP ${resp.status()}`);
  const body = await resp.body();
  const looksLikePdf =
    (resp.headers()['content-type'] || '').includes('pdf') ||
    body.slice(0, 5).toString() === '%PDF-';
  if (!looksLikePdf) throw new Error(`${pdfUrl} did not return a PDF (content-type: ${resp.headers()['content-type']})`);
  fs.writeFileSync(outPath, body);
  console.log(`PDF URL: ${pdfUrl}`);
  console.log(`Saved:   ${outPath} (${body.length} bytes)`);
}

(async () => {
  const browser = await chromium.launch({
    headless: true,
    executablePath: process.env.CHROMIUM_PATH || undefined,
  });
  const context = await browser.newContext({
    userAgent:
      'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
    viewport: { width: 1366, height: 900 },
  });
  const page = await context.newPage();

  try {
    await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 60000 });
    // Tab content is rendered client-side; give scripts a moment to attach links.
    await page.waitForLoadState('networkidle', { timeout: 15000 }).catch(() => {});

    // Preferred path: the link carries an href to the PDF directly.
    const links = await page.$$eval('a[href]', (as) =>
      as.map((a) => ({ text: (a.textContent || '').trim(), href: a.href }))
    );
    const direct = links.find(
      (l) => /included\s*features/i.test(l.text) || /included[-_]?features/i.test(l.href)
    );
    if (direct && direct.href) {
      await savePdf(context, direct.href);
      return;
    }

    // Fallback: the element is JS-driven — click it and catch the popup or download.
    const el = page.locator('a, button, [role="link"], [role="button"]', { hasText: LINK_RE }).first();
    if ((await el.count()) === 0) {
      throw new Error('No "Included Features" link found on the page. Is this a community-details URL?');
    }
    const popupP = page.waitForEvent('popup', { timeout: 15000 }).catch(() => null);
    const downloadP = page.waitForEvent('download', { timeout: 15000 }).catch(() => null);
    await el.click();
    const [popup, download] = await Promise.all([popupP, downloadP]);

    if (download) {
      await download.saveAs(outPath);
      console.log(`PDF URL: ${download.url()}`);
      console.log(`Saved:   ${outPath}`);
    } else if (popup) {
      await popup.waitForLoadState('domcontentloaded').catch(() => {});
      await savePdf(context, popup.url());
    } else {
      throw new Error('Clicking "Included Features" produced no popup or download.');
    }
  } finally {
    await browser.close();
  }
})().catch((err) => {
  console.error(`Failed: ${err.message}`);
  process.exit(1);
});
