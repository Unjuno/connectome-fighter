import { chromium } from 'playwright';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';

const out = process.argv[2];
const timeout = Number(process.argv[3] || 1200) * 1000;
assert(process.env.CI === 'true' && !process.env.VERCEL, 'CI-only browser probe');
assert(timeout >= 60000 && timeout <= 1200000);
const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
await context.tracing.start({ screenshots: true, snapshots: true, sources: true });
const page = await context.newPage();
const errors = [];
const runtimeRequests = new Set();
const observedStatusCounts = {};
page.on('pageerror', error => errors.push(String(error)));
page.on('request', request => {
  const url = new URL(request.url());
  if (url.origin === 'http://127.0.0.1:18000') runtimeRequests.add(url.pathname);
  if (url.hostname.endsWith('vercel.app')) errors.push('unexpected production request: ' + url.origin);
});
let result = { status: 'FAIL', production_deployment_e2e: false, mocked_requests: false };
const persist = () => fs.writeFileSync(path.join(out, 'browser-proof.json'), JSON.stringify({ ...result, page_errors: errors, observed_status_counts: observedStatusCounts }, null, 2));
try {
  await page.goto('http://127.0.0.1:3000/live', { waitUntil: 'domcontentloaded', timeout: 60000 });
  const deadline = Date.now() + timeout;
  let first = null;
  let second = null;
  let iteration = 0;
  while (Date.now() < deadline) {
    const state = await page.evaluate(() => {
      const el = document.querySelector('[data-testid="arena-snapshot"]');
      const imgs = [...document.querySelectorAll('[data-testid$="-image"]')];
      return { status: document.querySelector('[data-testid="arena-status"]')?.textContent || 'no status',
        snapshot: el && imgs.length === 3 && imgs.every(img => img.complete && img.naturalWidth > 0)
          ? { ...el.dataset, dimensions: imgs.map(img => [img.naturalWidth, img.naturalHeight]) } : null };
    });
    observedStatusCounts[state.status] = (observedStatusCounts[state.status] || 0) + 1;
    if (++iteration % 10 === 0) persist();
    const current = state.snapshot;
    if (current) {
      assert.deepEqual(current.dimensions, [[480, 320], [320, 240], [320, 240]]);
      if (!first || first.session !== current.session) {
        first = current;
        result.first = first;
        persist();
        await page.screenshot({ path: path.join(out, 'browser-first.png'), fullPage: true });
      } else if (Number(current.p1Decision) > Number(first.p1Decision)
                 && Number(current.p2Decision) > Number(first.p2Decision)
                 && current.p1Hash !== first.p1Hash && current.p2Hash !== first.p2Hash) {
        second = current;
        await page.screenshot({ path: path.join(out, 'browser-second.png'), fullPage: true });
        break;
      }
    }
    await page.waitForTimeout(100);
  }
  assert(first && second, 'two decoded, progressing viewer samples required');
  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({ path: path.join(out, 'browser-mobile.png'), fullPage: true });
  assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), 'mobile overflow');
  for (const endpoint of ['/state', '/activity.json', '/flybody.json', '/screen.png', '/flybody-p1.png', '/flybody-p2.png']) {
    assert(runtimeRequests.has(endpoint), `real runtime request missing: ${endpoint}`);
  }
  assert.deepEqual(errors, [], 'browser execution errors');
  result = { ...result, status: 'PASS', first, second, runtime_requests: [...runtimeRequests], browser: browser.version() };
} catch (error) {
  result.error = String(error);
  throw error;
} finally {
  persist();
  await context.tracing.stop({ path: path.join(out, 'browser-trace.zip') }).catch(() => {});
  await browser.close().catch(() => {});
}
