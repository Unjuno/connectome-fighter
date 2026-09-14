// Engineering UI fixtures only. These tests do not prove real game/neural/physics execution.
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import { createHash } from 'node:crypto';
import { deflateSync } from 'node:zlib';
import { chromium } from 'playwright';

const base = 'http://127.0.0.1:3000';
const out = 'runs/observatory-design';
await fs.mkdir(out, { recursive: true });
const browser = await chromium.launch({ headless: true });
const results = [];
const adapter = 'malecns-annotated-motor-to-flybody-tripod-v2';
const upstream = 'd015e9bfe441bd90ae431bac24c55cb74bdbce26';
const sha = bytes => createHash('sha256').update(bytes).digest('hex');
function crc(bytes) { let n = 0xffffffff; for (const value of bytes) { n ^= value; for (let i = 0; i < 8; i++) n = (n >>> 1) ^ ((n & 1) ? 0xedb88320 : 0); } return (n ^ 0xffffffff) >>> 0; }
function chunk(type, bytes) { const body = Buffer.concat([Buffer.from(type), bytes]); const size = Buffer.alloc(4); size.writeUInt32BE(bytes.length); const checksum = Buffer.alloc(4); checksum.writeUInt32BE(crc(body)); return Buffer.concat([size, body, checksum]); }
function png(phase = 1) {
  const width = 480, height = 320, header = Buffer.alloc(13), pixels = Buffer.alloc(height * (width * 3 + 1));
  header.writeUInt32BE(width); header.writeUInt32BE(height, 4); header[8] = 8; header[9] = 2;
  for (let y = 0; y < height; y++) for (let x = 0; x < width; x++) { const k = y * (width * 3 + 1) + 1 + x * 3; pixels[k] = 20 + x % 50; pixels[k + 1] = 40 + (y + phase * 17) % 80; pixels[k + 2] = 50 + x % 90; }
  return Buffer.concat([Buffer.from('89504e470d0a1a0a', 'hex'), chunk('IHDR', header), chunk('IDAT', deflateSync(pixels)), chunk('IEND', Buffer.alloc(0))]);
}
const videos = await fs.readFile(path.join(out, 'engineering-fixture.mp4'));
function evaluation(generation) { return { status: 'COMPLETED', candidate_only: true, auto_promotion: false, policy_pixel_access: false, character: 'GARNET', opponent: 'ZEN', generation, matches: generation, state_sha256: String(generation).repeat(64), evaluated_at: '2026-09-14T05:35:00Z', model: 'engineering-fixture', reward_id: 'fixture-not-a-reward-change', evaluation: { rounds: 1, protocol: 'fixed-full-round-v2', round_frame_limit: 3600, configured_round_limit_seconds: 60, seed_p1: 800101, seed_p2: 20202, decision_interval_frames: 60 }, result: { winner: 'DRAW', p1_hp: 400, p2_hp: 400, ended_by: 'TIME_LIMIT', elapsed_seconds: 60 }, video: { asset_url: `https://fixtures.invalid/round-${generation}.mp4`, duration_seconds: 1 } }; }
function envelope() { return { ready: true, latest: evaluation(9), previous: evaluation(8), training: { generation: 9, matches: 9, update_summary: { changed_edges: 8819 }, updated_at: '2026-09-14T05:32:00Z' } }; }
function runtime(phase, mode) {
  const frame = phase * 60, bytes = png(phase);
  const id = { round: 1, frame, decision_index: phase };
  const rows = [{ body_id: 101, type: 'Motor fixture A', spikes: 24, superclass: 'vnc_motor' }, { body_id: 102, type: 'Motor fixture B', spikes: 14, superclass: 'vnc_motor' }, { body_id: 103, type: 'Descending fixture', spikes: 9, superclass: 'descending_neuron' }];
  const brain = { decision_index: phase, total_spikes: 4320, unique_bodies: 389 };
  const live = { session_id: 'engineering-ui-fixture', status: 'running', round: 1, frame, learning_enabled: mode === 'policy', policy_pixel_access: false, brain: { p1: brain, p2: brain }, p1: { character: 'GARNET', hp: 400, action: phase === 1 ? 'FORWARD' : 'A' }, p2: { character: 'ZEN', hp: 398, action: 'BACKWARD' } };
  const activity = { kind: 'male-cns-live-anatomy-activity', policy_access: false, sides: { p1: { ...id, top_bodies: rows, motor_contributors: rows }, p2: { ...id, top_bodies: rows, motor_contributors: rows } } };
  const item = { decision: id, input_status: mode === 'stale' ? 'stale' : 'fresh', input_age_seconds: 0.1, input_epoch: 0, png_sha256: mode === 'hash' ? '0'.repeat(64) : sha(bytes), neural_command: { adapter, drive: .7, t1_drive: .8, t2_drive: .5, t3_drive: .3, source_body_ids: [101, 102] }, physics: { sim_steps: 40 * phase, action_dimension: 59, sim_time_seconds: .08 * phase, dropped_time_seconds: .1 } };
  const fly = { schema_version: 2, publisher: 'malecns-flybody-publisher-v2', adapter, upstream: { repository: 'TuragaLab/flybody', commit: upstream }, mujoco_gl: 'osmesa', policy_access: false, game_telemetry_position_used: false, stale_after_seconds: 30, sides: { p1: item, p2: item } };
  const selected = { kind: 'observed-decision-snapshot', session_id: mode === 'identity' ? 'wrong-session' : live.session_id, selection_mode: 'observed-decision-history-v1', policy_access: false, telemetry: live, activity, source_age_seconds: { p1: .2, p2: .2 } };
  return { live, activity, fly, selected, bytes };
}
async function setup(viewport = { width: 1440, height: 1000 }) {
  const context = await browser.newContext({ viewport });
  const page = await context.newPage();
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  const state = { evaluation: envelope(), evalStatus: 200, mode: 'valid', phase: 1, controlCalls: 0, runtimeCalls: 0, evaluationCalls: 0 };
  await page.route('**/*', async route => {
    const url = new URL(route.request().url());
    if (url.origin === base && url.pathname === '/api/evaluation') { state.evaluationCalls++; return route.fulfill({ status: state.evalStatus, json: state.evaluation }); }
    if (url.origin === base && url.pathname === '/api/live') {
      state.controlCalls++;
      if (state.mode === 'capacity') return route.fulfill({ status: 503, headers: { 'Retry-After': '3600' }, json: { ready: false, status: 'capacity-blocked', capacity_blocked: true } });
      return route.fulfill({ json: { ready: true, status: 'running', telemetry_url: 'https://runtime.invalid/state', learning_enabled: false, policy_pixel_access: false } });
    }
    if (url.hostname === 'runtime.invalid') {
      state.runtimeCalls++;
      const sample = runtime(state.phase, state.mode);
      const json = { '/state': sample.live, '/activity.json': sample.activity, '/flybody.json': sample.fly, '/decision-snapshot': sample.selected }[url.pathname];
      if (json) return route.fulfill({ json, headers: { 'Access-Control-Allow-Origin': '*' } });
      if (url.pathname.endsWith('.png')) return route.fulfill({ contentType: 'image/png', body: sample.bytes, headers: { 'Access-Control-Allow-Origin': '*' } });
      return route.abort();
    }
    if (url.hostname === 'fixtures.invalid') return route.fulfill({ contentType: 'video/mp4', body: videos });
    if (url.origin !== base) return route.abort();
    return route.continue();
  });
  return { context, page, state, errors };
}
async function screenshot(page, name) {
  // Visible disclosure lives in test screenshots only, never production source.
  await page.evaluate(() => { let badge = document.getElementById('fixture-label'); if (!badge) { badge = document.createElement('div'); badge.id = 'fixture-label'; badge.textContent = 'DESIGN TEST / ENGINEERING FIXTURE / NOT LIVE EVIDENCE'; badge.style.cssText = 'background:#fff2c6;color:#3c3016;padding:8px;text-align:center;font:11px sans-serif;'; document.body.prepend(badge); } });
  await page.screenshot({ path: `${out}/${name}.png`, fullPage: true, animations: 'disabled' });
}
async function noOverflow(page) {
  assert(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1), 'horizontal page overflow');
}
async function test(name, fn, viewport) {
  const fixture = await setup(viewport);
  try { await fn(fixture); assert.deepEqual(fixture.errors, [], 'uncaught browser errors'); results.push({ name, status: 'PASS' }); }
  catch (error) { results.push({ name, status: 'FAIL', error: String(error) }); await screenshot(fixture.page, `failure-${results.length}`).catch(() => {}); }
  finally { await fixture.context.close(); }
}

await test('replay desktop: honest mode, playable fixture, generation switch, no live compute', async ({ page, state }) => {
  await page.goto(base);
  await page.getByTestId('evaluation-video').waitFor();
  await page.waitForFunction(() => document.querySelector('video')?.readyState >= 2);
  assert.equal(await page.getByTestId('p1-image').count(), 0);
  assert.equal(await page.getByTestId('arena-snapshot').count(), 0);
  assert.equal(state.controlCalls, 0);
  assert(await page.getByText('RECORDED EVALUATION', { exact: true }).isVisible());
  await screenshot(page, 'replay-desktop');
  await page.getByRole('button', { name: 'Previous Gen 8', exact: true }).click();
  assert((await page.getByTestId('evaluation-video').getAttribute('src')).includes('round-8'));
  await page.getByRole('button', { name: 'Latest completed Gen 9', exact: true }).click();
  assert((await page.getByTestId('evaluation-video').getAttribute('src')).includes('round-9'));
  await page.getByRole('button', { name: 'Pause history updates', exact: true }).click();
  assert(await page.getByRole('button', { name: 'Resume history updates', exact: true }).isVisible());
  await noOverflow(page);
});
await test('replay mobile: 375px layout and video before neural panels', async ({ page }) => {
  await page.goto(base); await page.getByTestId('evaluation-video').waitFor();
  await noOverflow(page);
  const game = await page.locator('.ob-arena').boundingBox(), brain = await page.getByTestId('p1-brain').boundingBox();
  assert(game.y < brain.y);
  await screenshot(page, 'replay-mobile');
}, { width: 375, height: 812 });
await test('no evaluations: no fabricated video, spikes, or zero-valued metrics', async ({ page, state }) => {
  state.evaluation = { ready: false, latest: null, previous: null, training: null };
  await page.goto(base); await page.getByText('Awaiting an evaluation video', { exact: true }).waitFor();
  assert.equal(await page.locator('video').count(), 0);
  assert.equal(await page.getByRole('button', { name: 'Previous Gen —', exact: true }).isDisabled(), true);
  assert((await page.locator('.ob-result').innerText()).includes('HP —'));
});
await test('evaluation failure: explicit error state', async ({ page, state }) => {
  state.evalStatus = 503;
  await page.goto(base); await page.getByText(/Evaluation API unavailable/).waitFor();
  assert.equal(await page.locator('video').count(), 0);
});
await test('newer candidate does not relabel completed evaluation', async ({ page, state }) => {
  state.evaluation.training.generation = 10;
  await page.goto(base); await page.getByTestId('evaluation-video').waitFor();
  assert((await page.getByTestId('evaluation-video').getAttribute('src')).includes('round-9'));
  assert(await page.getByText(/Candidate is now Gen 10/).isVisible());
});
await test('non-candidate or unsafe evaluation is not presented', async ({ page, state }) => {
  state.evaluation.latest.candidate_only = false;
  state.evaluation.previous = null;
  await page.goto(base); await page.getByText('Awaiting an evaluation video', { exact: true }).waitFor();
  assert.equal(await page.locator('video').count(), 0);
});
await test('capacity state: no automatic replay or fake physical pose', async ({ page, state }) => {
  state.mode = 'capacity'; await page.goto(base + '/live');
  await page.getByTestId('arena-status').filter({ hasText: 'capacity-blocked' }).waitFor();
  assert.equal(await page.locator('video').count(), 0);
  assert.equal(await page.getByTestId('game-image').count(), 0);
  assert.equal(await page.getByTestId('p1-image').count(), 0);
  assert.equal(state.runtimeCalls, 0);
  await noOverflow(page); await screenshot(page, 'live-capacity');
});
await test('verified live layout, progression, pause, and resume', async ({ page, state }) => {
  await page.goto(base + '/live'); await page.getByTestId('arena-snapshot').waitFor();
  await page.waitForFunction(() => [...document.querySelectorAll('img')].length === 3 && [...document.querySelectorAll('img')].every(image => image.naturalWidth > 0));
  const left = await page.getByTestId('p1-brain').boundingBox(), game = await page.locator('.ob-arena').boundingBox(), right = await page.getByTestId('p2-brain').boundingBox();
  assert(left.x < game.x && game.x < right.x);
  await screenshot(page, 'live-fixture-desktop');
  state.phase = 2;
  await page.waitForFunction(() => document.querySelector('[data-testid="arena-snapshot"]')?.getAttribute('data-p1-decision') === '2');
  assert.equal(await page.locator('.ob-timeline li').count(), 2);
  await page.getByRole('button', { name: 'Pause display updates', exact: true }).click();
  await page.getByTestId('arena-status').filter({ hasText: 'paused' }).waitFor();
  assert.equal(await page.getByTestId('arena-snapshot').count(), 0);
  const calls = state.runtimeCalls; await page.waitForTimeout(650); assert.equal(state.runtimeCalls, calls);
  await page.getByRole('button', { name: 'Resume LIVE display', exact: true }).click();
  await page.getByTestId('arena-snapshot').waitFor();
  await noOverflow(page);
});
for (const mode of ['hash', 'stale', 'identity', 'policy']) await test(`live fail-closed: ${mode}`, async ({ page, state }) => {
  state.mode = mode; await page.goto(base + '/live');
  await page.waitForFunction(() => { const text = document.querySelector('[data-testid="arena-status"]')?.textContent; return text && text !== 'connecting'; });
  assert.equal(await page.getByTestId('arena-snapshot').count(), 0);
  assert.equal(await page.getByTestId('p1-image').count(), 0);
});
await test('reduced motion, keyboard provenance, and live mobile', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' }); await page.goto(base + '/live');
  await page.getByTestId('arena-snapshot').waitFor();
  assert(await page.locator('.ob-action').first().evaluate(node => getComputedStyle(node).animationName === 'none'));
  await noOverflow(page);
  await page.locator('.ob-protocol summary').first().focus(); await page.keyboard.press('Enter');
  assert.equal(await page.locator('.ob-protocol details').first().getAttribute('open'), '');
  await screenshot(page, 'live-fixture-mobile');
}, { width: 375, height: 812 });

await browser.close();
await fs.writeFile(`${out}/results.json`, JSON.stringify({ kind: 'engineering-fixture-ui-tests', production_live_evidence: false, actual_neural_inputs: false, browser: 'Chromium / Playwright 1.57.0', results }, null, 2));
console.log(JSON.stringify(results, null, 2));
if (results.some(result => result.status !== 'PASS')) process.exitCode = 1;
