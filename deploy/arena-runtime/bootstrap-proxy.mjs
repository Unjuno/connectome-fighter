#!/usr/bin/env node
import fs from 'node:fs';
import http from 'node:http';
import { URL } from 'node:url';

function arg(name, fallback = null) {
  const i = process.argv.indexOf(name);
  return i >= 0 && i + 1 < process.argv.length ? process.argv[i + 1] : fallback;
}
const listen = Number(arg('--listen', '8080'));
const upstreamPort = Number(arg('--upstream', '18080'));
const statusFile = arg('--status-file');
const screenFile = arg('--screen-file');
const activityFile = arg('--activity-file');
const flybodyP1File = arg('--flybody-p1-file');
const flybodyP2File = arg('--flybody-p2-file');
const flybodyStateFile = arg('--flybody-state-file');
const sessionId = arg('--session-id', 'unknown');
const p1 = arg('--p1', 'GARNET');
const p2 = arg('--p2', 'ZEN');
if (!Number.isInteger(listen) || listen <= 0 || !Number.isInteger(upstreamPort) || upstreamPort <= 0 || !statusFile) {
  console.error('invalid bootstrap proxy arguments'); process.exit(2);
}
function readStatus() {
  try { const raw = JSON.parse(fs.readFileSync(statusFile, 'utf8')); return raw && typeof raw === 'object' ? raw : { phase: 'booting' }; }
  catch { return { phase: 'booting' }; }
}
function brainSample() {
  return { decision_index: 0, t_seconds: 0, total_spikes: 0, unique_bodies: 0, neuromeres: [], superclasses: [], types: [], top_bodies: [] };
}
function bootPayload() {
  const boot = readStatus(); const failed = boot.phase === 'error';
  return {
    schema_version: 1, session_id: sessionId, status: failed ? 'error' : boot.phase === 'ended' ? 'ended' : 'booting',
    round: 0, frame: 0, t_seconds: 0,
    p1: { character: p1, hp: 400, max_hp: 400, x: 0, y: 0, action: 'NEUTRAL', facing: 'right', energy: 0 },
    p2: { character: p2, hp: 400, max_hp: 400, x: 0, y: 0, action: 'NEUTRAL', facing: 'left', energy: 0 },
    brain: { p1: brainSample(), p2: brainSample() }, learning_enabled: false, policy_pixel_access: false,
    official_screen: { available: Boolean(screenFile && fs.existsSync(screenFile)), path: '/screen.png', source: 'FightingICE ScreenData', policy_pixel_access: false },
    anatomy_activity: { available: Boolean(activityFile && fs.existsSync(activityFile)), path: '/activity.json', policy_access: false },
    flybody_embodiment: {
      available: Boolean(flybodyStateFile && fs.existsSync(flybodyStateFile) && flybodyP1File && fs.existsSync(flybodyP1File) && flybodyP2File && fs.existsSync(flybodyP2File)),
      p1_path: '/flybody-p1.png', p2_path: '/flybody-p2.png', state_path: '/flybody.json',
      source: 'TuragaLab/flybody MuJoCo physics', neural_drive: 'MaleCNS annotated motor output',
      policy_access: false, game_telemetry_position_used: false,
    },
    bootstrap: { phase: String(boot.phase ?? 'booting'), exit_code: Number.isInteger(boot.exit_code) ? boot.exit_code : null, line: Number.isInteger(boot.line) ? boot.line : null },
    error: failed ? String(boot.error ?? 'arena bootstrap failed') : null,
  };
}
function commonHeaders(res, contentType) {
  res.setHeader('content-type', contentType); res.setHeader('cache-control', 'no-store, no-cache, must-revalidate');
  res.setHeader('access-control-allow-origin', '*'); res.setHeader('x-content-type-options', 'nosniff');
}
function writeJson(res, status, body) { res.statusCode = status; commonHeaders(res, 'application/json; charset=utf-8'); res.end(JSON.stringify(body)); }
function writePng(res, path, notConfigured, notReady) {
  if (!path) { writeJson(res, 404, { error: notConfigured }); return; }
  try {
    const frame = fs.readFileSync(path);
    if (frame.length < 32 || frame.subarray(0, 8).toString('hex') !== '89504e470d0a1a0a') { writeJson(res, 503, { error: notReady }); return; }
    res.statusCode = 200; commonHeaders(res, 'image/png'); res.setHeader('content-length', String(frame.length)); res.end(frame);
  } catch { writeJson(res, 503, { error: notReady }); }
}
function writeJsonFile(res, path, notConfigured, notReady) {
  if (!path) { writeJson(res, 404, { error: notConfigured }); return; }
  try { writeJson(res, 200, JSON.parse(fs.readFileSync(path, 'utf8'))); }
  catch { writeJson(res, 503, { error: notReady }); }
}
function proxy(req, res, requestPath) {
  const pathname = requestPath.split('?')[0];
  const upstream = http.request({ host: '127.0.0.1', port: upstreamPort, path: requestPath, method: 'GET', headers: { accept: req.headers.accept ?? '*/*' } }, up => {
    res.statusCode = up.statusCode ?? 502;
    for (const [key, value] of Object.entries(up.headers)) {
      if (value !== undefined && !['connection', 'transfer-encoding'].includes(key.toLowerCase())) res.setHeader(key, value);
    }
    res.setHeader('access-control-allow-origin', '*'); res.setHeader('cache-control', 'no-store, no-cache, must-revalidate'); up.pipe(res);
  });
  upstream.on('error', () => {
    if (res.headersSent) { res.end(); return; }
    if (pathname === '/decision-snapshot') {
      writeJson(res, 503, { ready: false, status: 'snapshot-unavailable', reason: 'arena upstream not ready' });
    } else if (pathname === '/events') {
      res.statusCode = 200; commonHeaders(res, 'text/event-stream; charset=utf-8'); res.write(`data: ${JSON.stringify(bootPayload())}\n\n`); res.end();
    } else if (pathname === '/health') {
      writeJson(res, 200, { ok: true, status: bootPayload().status, bootstrap: bootPayload().bootstrap });
    } else { writeJson(res, 200, bootPayload()); }
  });
  upstream.end();
}
const server = http.createServer((req, res) => {
  if (req.method === 'OPTIONS') {
    res.statusCode = 204; res.setHeader('access-control-allow-origin', '*'); res.setHeader('access-control-allow-methods', 'GET, OPTIONS'); res.setHeader('access-control-allow-headers', 'content-type'); res.end(); return;
  }
  if (req.method !== 'GET') { writeJson(res, 405, { error: 'method_not_allowed' }); return; }
  const url = new URL(req.url ?? '/', 'http://127.0.0.1');
  if (url.pathname === '/screen.png') { writePng(res, screenFile, 'screen_not_configured', 'screen_not_ready'); return; }
  if (url.pathname === '/activity.json') { writeJsonFile(res, activityFile, 'activity_not_configured', 'activity_not_ready'); return; }
  if (url.pathname === '/flybody-p1.png') { writePng(res, flybodyP1File, 'flybody_not_configured', 'flybody_not_ready'); return; }
  if (url.pathname === '/flybody-p2.png') { writePng(res, flybodyP2File, 'flybody_not_configured', 'flybody_not_ready'); return; }
  if (url.pathname === '/flybody.json') { writeJsonFile(res, flybodyStateFile, 'flybody_not_configured', 'flybody_not_ready'); return; }
  if (url.pathname === '/decision-snapshot') {
    if (url.search.length > 512) { writeJson(res, 400, { error: 'snapshot_query_too_long' }); return; }
    proxy(req, res, url.pathname + url.search); return;
  }
  if (url.pathname === '/state' || url.pathname === '/health' || url.pathname === '/events') { proxy(req, res, url.pathname); return; }
  writeJson(res, 404, { error: 'not_found' });
});
server.listen(listen, '0.0.0.0', () => {
  console.log(JSON.stringify({ kind: 'arena-bootstrap-proxy-ready', listen, upstreamPort, sessionId, screenFile, activityFile, flybodyP1File, flybodyP2File, flybodyStateFile }));
});
