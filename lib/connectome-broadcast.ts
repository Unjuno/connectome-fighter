import { RuntimeDescriptor, runtimeBaseName } from "@/lib/runtime-release";
import {
  apiHeaders,
  apiUrl,
  commandAgeSeconds,
  commandExitCode,
  namedSandboxUrl,
  providerFailure,
  shellQuote,
} from "@/lib/vercel-sandbox";

const PORT = 8080;
const LIVE_TIMEOUT_MS = 1_200_000;
const EXTEND_THRESHOLD_MS = 300_000;
const EXTEND_DURATION_MS = 900_000;
const SUPERVISOR_STALE_SECONDS = 10 * 60;
const INFERENCE_MANIFEST =
  process.env.CONNECTOME_INFERENCE_MANIFEST_URL?.trim() ||
  "https://github.com/Unjuno/connectome-fighter/releases/download/arena-inference-latest/manifest.json";

export const LIVE_SANDBOX_NAME = process.env.CONNECTOME_LIVE_SANDBOX_NAME?.trim() || "connectome-fighter-live-broadcast";
export const LIVE_P1 = "GARNET";
export const LIVE_P2 = "ZEN";
const LIVE_MARKER = "connectome-dedicated-shared-live-v1";

type NamedSandbox = {
  exists: boolean;
  status: string;
  sessionId: string | null;
  snapshotId: string | null;
  domain: string | null;
  expiresAt: number | null;
  tags: Record<string, string>;
};

function normalizeDomain(value: unknown) {
  if (typeof value !== "string" || !value.trim()) return null;
  return value.startsWith("http://") || value.startsWith("https://") ? value : `https://${value}`;
}

function pickDomain(payload: any) {
  const values = [
    payload?.domain,
    payload?.session?.domain,
    payload?.routes?.find?.((row: any) => Number(row?.port) === PORT)?.url,
    payload?.session?.routes?.find?.((row: any) => Number(row?.port) === PORT)?.url,
    payload?.domains?.[String(PORT)],
    payload?.session?.domains?.[String(PORT)],
    payload?.ports?.find?.((row: any) => Number(row?.port) === PORT)?.domain,
    payload?.session?.ports?.find?.((row: any) => Number(row?.port) === PORT)?.domain,
  ];
  for (const value of values) {
    const domain = normalizeDomain(value);
    if (domain) return domain;
  }
  return null;
}

function numberMs(value: unknown) {
  const parsed = Number(value);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : null;
}

function expiresAt(payload: any, sandbox: any) {
  const direct = numberMs(sandbox?.expiresAt ?? payload?.session?.expiresAt);
  if (direct) return direct;
  const started = numberMs(payload?.session?.startedAt ?? payload?.session?.requestedAt);
  const timeout = Number(payload?.session?.timeout ?? sandbox?.timeout);
  return started && Number.isFinite(timeout) && timeout > 0 ? started + timeout : null;
}

async function inspectNamedSandbox(token: string, name: string): Promise<NamedSandbox> {
  const response = await fetch(namedSandboxUrl(name), { cache: "no-store", headers: apiHeaders(token), signal: AbortSignal.timeout(8000) });
  if (response.status === 404) return { exists: false, status: "missing", sessionId: null, snapshotId: null, domain: null, expiresAt: null, tags: {} };
  const body = await response.json().catch(() => ({}));
  if (!response.ok) return { exists: true, status: `inspect-http-${response.status}`, sessionId: null, snapshotId: null, domain: null, expiresAt: null, tags: {} };
  const sandbox = body?.sandbox ?? body;
  return {
    exists: true,
    status: String(sandbox?.status ?? body?.session?.status ?? "unknown"),
    sessionId: body?.session?.id ?? sandbox?.currentSessionId ?? null,
    snapshotId: sandbox?.currentSnapshotId ?? null,
    domain: pickDomain(body),
    expiresAt: expiresAt(body, sandbox),
    tags: (sandbox?.tags ?? body?.tags ?? {}) as Record<string, string>,
  };
}

async function probeState(domain: string | null) {
  if (!domain) return null;
  try {
    const response = await fetch(`${domain.replace(/\/$/, "")}/state`, { cache: "no-store", signal: AbortSignal.timeout(2500) });
    if (!response.ok) return null;
    const body = await response.json().catch(() => null);
    return body && typeof body === "object" ? body : null;
  } catch {
    return null;
  }
}

async function listCommands(token: string, sessionId: string): Promise<any[]> {
  const response = await fetch(apiUrl(`/v2/sandboxes/sessions/${encodeURIComponent(sessionId)}/cmd`), { cache: "no-store", headers: apiHeaders(token), signal: AbortSignal.timeout(7000) });
  if (!response.ok) return [];
  const body = await response.json().catch(() => ({}));
  return Array.isArray(body?.commands) ? body.commands : [];
}

function terminal(status: string) {
  return new Set(["stopped", "ended", "error", "failed", "canceled", "cancelled", "terminated"]).has(status.trim().toLowerCase());
}

async function removeLive(token: string) {
  await fetch(namedSandboxUrl(LIVE_SANDBOX_NAME), { method: "DELETE", headers: apiHeaders(token), signal: AbortSignal.timeout(8000) }).catch(() => null);
}

async function extend(token: string, sessionId: string) {
  const response = await fetch(apiUrl(`/v2/sandboxes/sessions/${encodeURIComponent(sessionId)}/extend-timeout`), {
    method: "POST",
    headers: apiHeaders(token),
    body: JSON.stringify({ duration: EXTEND_DURATION_MS }),
    signal: AbortSignal.timeout(8000),
  });
  return response.ok;
}

function liveCommand(runtime: RuntimeDescriptor) {
  const sha = runtime.archiveSha256!;
  const start = [
    'bash "$ROOT/arena-runtime/bin/start-session"',
    "--listen", String(PORT),
    '--session-id "$LIVE_SESSION_ID"',
    "--p1", shellQuote(LIVE_P1),
    "--p2", shellQuote(LIVE_P2),
    "--manifest-url", shellQuote(INFERENCE_MANIFEST),
  ].join(" ");
  return [
    `: ${shellQuote(LIVE_MARKER)}`,
    "set -euo pipefail",
    'ROOT="/home/vercel-sandbox/connectome-runtime"',
    `test "$(cat \"$ROOT/.runtime-archive-sha256\")" = ${shellQuote(sha)}`,
    `while true; do rm -rf /tmp/connectome-arena-session; LIVE_SESSION_ID="public-live-$(date +%s)"; ${start} || true; sleep 2; done`,
  ].join("; ");
}

async function startSupervisor(token: string, sessionId: string, runtime: RuntimeDescriptor) {
  const response = await fetch(apiUrl(`/v2/sandboxes/sessions/${encodeURIComponent(sessionId)}/cmd`), {
    method: "POST",
    headers: apiHeaders(token),
    body: JSON.stringify({ command: "bash", args: ["-lc", liveCommand(runtime)], cwd: "/home/vercel-sandbox", wait: false, logs: false, timeout: 18_000_000 }),
    signal: AbortSignal.timeout(9000),
  });
  const body = await response.json().catch(() => ({}));
  return { ok: response.ok, status: response.status, body, commandId: body?.command?.id ?? body?.id ?? null };
}

async function forkLive(token: string, runtime: RuntimeDescriptor, baseName: string) {
  const url = apiUrl(`/v2/sandboxes/${encodeURIComponent(baseName)}/fork`);
  const projectId = process.env.VERCEL_PROJECT_ID?.trim();
  if (projectId) url.searchParams.set("projectId", projectId);
  const response = await fetch(url, {
    method: "POST",
    headers: apiHeaders(token),
    body: JSON.stringify({
      name: LIVE_SANDBOX_NAME,
      persistent: false,
      ports: [PORT],
      timeout: LIVE_TIMEOUT_MS,
      resources: { vcpus: 4, memory: 8192 },
      env: {
        CONNECTOME_LEARNING_ENABLED: "false",
        CONNECTOME_POLICY_PIXEL_ACCESS: "false",
        CONNECTOME_PUBLIC_BROADCAST: "true",
        CONNECTOME_MUJOCO_GL: "osmesa",
      },
      tags: { app: "connectome-fighter", role: "single-shared-live-broadcast", runtime: runtime.archiveSha256!.slice(0, 16) },
    }),
    signal: AbortSignal.timeout(12_000),
  });
  const body = await response.json().catch(() => ({}));
  return { response, body };
}

function payload(runtime: RuntimeDescriptor, live: NamedSandbox, arena: any) {
  const running = arena?.status === "running";
  const base = live.domain?.replace(/\/$/, "") ?? null;
  return {
    mode: "single-shared-live-broadcast",
    audience_scope: "shared-global",
    broadcast_target: LIVE_SANDBOX_NAME,
    ready: Boolean(running && base),
    status: arena?.status ?? (live.exists ? "warming" : live.status),
    p1: arena?.p1?.character ?? LIVE_P1,
    p2: arena?.p2?.character ?? LIVE_P2,
    stream_url: running && base ? `${base}/events` : null,
    telemetry_url: base ? `${base}/state` : null,
    session_id: arena?.session_id ?? live.sessionId,
    source_runtime_base: runtimeBaseName(runtime),
    runtime_archive_sha256: runtime.archiveSha256,
    learning_enabled: false,
    policy_pixel_access: false,
  };
}

export async function inspectBroadcast(token: string, runtime: RuntimeDescriptor) {
  if (!runtime.ready || !runtime.archiveSha256) return { ...payload(runtime, { exists: false, status: "runtime-unavailable", sessionId: null, snapshotId: null, domain: null, expiresAt: null, tags: {} }, null), reason: runtime.reason };
  const live = await inspectNamedSandbox(token, LIVE_SANDBOX_NAME);
  const expected = runtime.archiveSha256.slice(0, 16);
  if (live.exists && live.tags.runtime && live.tags.runtime !== expected) return { ...payload(runtime, live, null), ready: false, status: "runtime-refresh-pending" };
  return payload(runtime, live, await probeState(live.domain));
}

export async function maintainBroadcast(token: string, runtime: RuntimeDescriptor) {
  if (!runtime.ready || !runtime.archiveSha256) return { ok: false, action: "wait-runtime", status: "runtime-unavailable", reason: runtime.reason };
  const baseName = runtimeBaseName(runtime)!;
  const base = await inspectNamedSandbox(token, baseName);
  if (!base.exists || !base.snapshotId) return { ok: false, action: "wait-runtime-base", status: base.status, base_name: baseName };

  let live = await inspectNamedSandbox(token, LIVE_SANDBOX_NAME);
  const expected = runtime.archiveSha256.slice(0, 16);
  if (live.exists && live.tags.runtime && live.tags.runtime !== expected) {
    await removeLive(token);
    live = { exists: false, status: "runtime-refresh", sessionId: null, snapshotId: null, domain: null, expiresAt: null, tags: {} };
  }
  if (live.exists && terminal(live.status)) {
    await removeLive(token);
    live = { exists: false, status: "recycle-terminal", sessionId: null, snapshotId: null, domain: null, expiresAt: null, tags: {} };
  }

  if (live.exists && live.sessionId && live.expiresAt && live.expiresAt - Date.now() <= EXTEND_THRESHOLD_MS) await extend(token, live.sessionId);
  if (live.exists) {
    const arena = await probeState(live.domain);
    if (arena?.status === "running" || arena?.status === "booting") return { ok: true, action: "keep", ...payload(runtime, live, arena) };
    const commands = live.sessionId ? await listCommands(token, live.sessionId) : [];
    const active = commands.find((row) => JSON.stringify(row).includes(LIVE_MARKER) && commandExitCode(row) === null);
    if (active) {
      const age = commandAgeSeconds(active);
      if (!arena && age !== null && age > SUPERVISOR_STALE_SECONDS) {
        await removeLive(token);
        live = { exists: false, status: "recycle-stalled", sessionId: null, snapshotId: null, domain: null, expiresAt: null, tags: {} };
      } else {
        return { ok: true, action: "keep-warming", supervisor_age_seconds: age, ...payload(runtime, live, arena) };
      }
    } else if (live.sessionId) {
      const started = await startSupervisor(token, live.sessionId, runtime);
      if (!started.ok) {
        const failure = providerFailure(started.body);
        return { ok: false, action: failure.capacityBlocked ? "capacity-blocked" : "restart-failed", status: failure.capacityBlocked ? "capacity-blocked" : started.status, provider_error_code: failure.code, reason: failure.message, blocked_until: failure.blockedUntil };
      }
      return { ok: true, action: "restart-supervisor", command_id: started.commandId, ...payload(runtime, live, arena) };
    }
  }

  if (!live.exists) {
    const forked = await forkLive(token, runtime, baseName);
    if (!forked.response.ok) {
      const failure = providerFailure(forked.body);
      if (forked.response.status === 409) return { ok: true, action: "fork-race", status: "warming" };
      return { ok: false, action: failure.capacityBlocked ? "capacity-blocked" : "fork-failed", status: failure.capacityBlocked ? "capacity-blocked" : forked.response.status, provider_error_code: failure.code, reason: failure.message, blocked_until: failure.blockedUntil };
    }
    const sessionId = forked.body?.session?.id ?? forked.body?.sandbox?.currentSessionId ?? null;
    if (!sessionId) return { ok: false, action: "fork-missing-session", status: "warming" };
    const started = await startSupervisor(token, String(sessionId), runtime);
    if (!started.ok) {
      const failure = providerFailure(started.body);
      return { ok: false, action: failure.capacityBlocked ? "capacity-blocked" : "start-failed", status: failure.capacityBlocked ? "capacity-blocked" : started.status, provider_error_code: failure.code, reason: failure.message, blocked_until: failure.blockedUntil };
    }
    return { ok: true, action: "fork-and-start", command_id: started.commandId, status: "warming" };
  }
  return { ok: false, action: "unexpected", status: "warming" };
}
