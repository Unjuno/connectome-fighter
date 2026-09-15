// Isolated engineering fixtures; not actual training or deployment evidence.
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import { chromium } from 'playwright';
const base = 'http://127.0.0.1:3000';
const out = 'runs/observatory-design';
const video = await fs.readFile(`${out}/engineering-fixture.mp4`);
const source = 'https://github.com/Unjuno/connectome-fighter/actions/runs/123';
const protocol = { protocol: 'paired-rollout-combat-v1', round_frame_limit: 3600, decision_interval_frames: 60, seed_p1: 800101, seed_p2: 20202 };
function fixture() {
  const evaluation = phase => ({ status: 'COMPLETED', candidate_only: true, auto_promotion: false, policy_pixel_access: false, served_by_vercel: false,
    comparison_phase: phase, source_training_run_url: source, state_sha256: 'a'.repeat(64), generation: 11,
    reward_id: 'outcome-hp-epsilon002-v1', evaluation: { ...protocol },
    video: { asset_url: `https://github.com/Unjuno/connectome-fighter/releases/download/paired-cycle-123-1/${phase}.mp4`, sha256: 'c'.repeat(64), duration_seconds: 1 },
    result: { p1_hp: 400, p2_hp: 400, combat_score: 0, winner: 'DRAW', damage_dealt_hp: 0, damage_taken_hp: 0, elapsed_seconds: 60 } });
  return { schema_version: 1, rollout: 'paired-neural-rollout-v1', ready: true, status: 'paired-evaluation-ready', protocol_sha256: 'b'.repeat(64),
    cycle_index: 1, accepted_update_count: 0, source_run_url: source, previous: evaluation('before'), latest: evaluation('after'),
    updated_at: '2026-09-15T00:00:00Z', training: { cycle_index: 1, accepted_update_count: 0, source_run_url: source,
      auto_promotion: false, served_by_vercel: false, state_sha256: 'a'.repeat(64), accepted_update: false,
      phase: 'curriculum', next_phase: 'curriculum', strength_claim: false, matches_this_cycle: 12, update_reason: 'zero paired signal' } };
}
const browser = await chromium.launch();
const results = [];
try {
  for (const name of ['desktop', 'mobile', 'unavailable', 'wrong-reward', 'phantom-update', 'mixed-run']) {
    const context = await browser.newContext({ viewport: name === 'mobile' ? { width: 375, height: 812 } : { width: 1440, height: 1000 } });
    const page = await context.newPage();
    const errors = []; let liveCalls = 0; let evaluationCalls = 0;
    page.on('pageerror', e => errors.push(e.message));
    const data = fixture();
    if (name === 'wrong-reward') data.latest.reward_id = 'R2e-combat-v1';
    if (name === 'phantom-update') data.training.accepted_update = true;
    if (name === 'mixed-run') data.latest.source_training_run_url += '4';
    await page.route('**/*', async route => {
      const u = new URL(route.request().url());
      if (u.origin === base && u.pathname === '/api/evaluation') { evaluationCalls++; return route.fulfill({ status: name === 'unavailable' ? 503 : 200, json: data }); }
      if (u.origin === base && u.pathname === '/api/live') { liveCalls++; return route.abort(); }
      if (u.origin === base) return route.continue();
      if (u.hostname === 'github.com' && u.pathname.endsWith('.mp4')) return route.fulfill({ contentType: 'video/mp4', body: video });
      return route.abort();
    });
    await page.goto(base + '/training');
    const valid = name === 'desktop' || name === 'mobile';
    if (valid) {
      await page.waitForSelector('video');
      await page.waitForFunction(() => [...document.querySelectorAll('video')].every(v => v.readyState >= 1));
      assert.equal(await page.locator('video').count(), 2);
      assert.match(await page.locator('main').innerText(), /NO UPDATE/);
      const pause = page.getByRole('button', { name: 'Pause viewer updates' });
      await pause.click();
      assert.equal(await page.getByRole('button', { name: 'Resume viewer updates' }).getAttribute('aria-pressed'), 'true');
      const calls = evaluationCalls;
      await page.getByRole('button', { name: 'Resume viewer updates' }).click();
      await page.waitForFunction(() => document.querySelector('button[aria-pressed="false"]'));
      for (let i = 0; i < 30 && evaluationCalls <= calls; i++) await page.waitForTimeout(50);
      assert.ok(evaluationCalls > calls, 'resume fetches a fresh record');
      await page.getByText('Inspect reward, schedule and provenance', { exact: true }).click();
      assert.match(await page.locator('main').innerText(), /Combat: win \+1, draw 0, loss -1/);
      assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), 'no horizontal overflow');
      await page.evaluate(() => { const label = document.createElement('p'); label.textContent = 'ENGINEERING UI FIXTURE — NOT ACTUAL TRAINING'; label.style.cssText = 'position:fixed;top:0;left:0;z-index:9999;background:#fff;color:#000;padding:8px'; document.body.append(label); });
      await page.screenshot({ path: `${out}/training-${name}-fixture.png`, fullPage: true });
    } else {
      await page.waitForFunction(() => { const p = document.querySelector('[role="status"]'); return p && !p.textContent.includes('Connecting'); });
      assert.equal(await page.locator('video').count(), 0);
      assert.match(await page.locator('main').innerText(), /Awaiting published paired evidence/);
    }
    assert.equal(await page.locator('html').getAttribute('lang'), 'en');
    assert.equal(liveCalls, 0, 'training viewer must not allocate LIVE');
    assert.deepEqual(errors, []);
    results.push({ name, status: 'PASS' });
    await context.close();
  }
} finally {
  await browser.close();
  await fs.writeFile(`${out}/training-console-results.json`, JSON.stringify({ kind: 'engineering-ui-fixtures', results }, null, 2));
}
console.log(JSON.stringify({ kind: 'engineering-ui-fixtures', passed: results.length }));
