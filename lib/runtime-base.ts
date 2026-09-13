import { RuntimeDescriptor, runtimeBaseName } from "@/lib/runtime-release";
import {
  apiHeaders,
  apiUrl,
  commandAgeSeconds,
  commandExitCode,
  namedSandboxUrl,
  providerFailure,
  shellQuote,
  vercelProjectId,
} from "@/lib/vercel-sandbox";

const SNAPSHOT_TTL_MS = 7 * 24 * 60 * 60 * 1000;
const STAGE_VERSION = "dedicated-renderer-v1";
const STAGE_STALE_SECONDS = 15 * 60;

export type RuntimeBaseState = {
  ready: boolean;
  status: string;
  name: string | null;
  snapshot_id?: string | null;
  session_id?: string | null;
  command_id?: string | null;
  stage_age_seconds?: number | null;
  provider_error_code?: string | null;
  reason?: string | null;
  blocked_until?: string | null;
};

function capacityState(name: string | null, body: any): RuntimeBaseState | null {
  const failure = providerFailure(body);
  if (!failure.capacityBlocked) return null;
  return {
    ready: false,
    status: "capacity-blocked",
    name,
    provider_error_code: failure.code,
    reason: failure.message ?? "Vercel Sandbox capacity unavailable",
    blocked_until: failure.blockedUntil,
  };
}

function stageMarker(runtime: RuntimeDescriptor) {
  return `connectome-runtime-stage:${STAGE_VERSION}:${runtime.archiveSha256}`;
}

function streamingDownload(url: string, target: string) {
  const script = [
    "const fs=require('node:fs')",
    "const {Readable}=require('node:stream')",
    "const {pipeline}=require('node:stream/promises')",
    "const [u,p]=process.argv.slice(1)",
    ";(async()=>{",
    "const r=await fetch(u,{redirect:'follow'})",
    "if(!r.ok)throw new Error('HTTP '+r.status+' '+u)",
    "if(!r.body)throw new Error('response body missing')",
    "await pipeline(Readable.fromWeb(r.body),fs.createWriteStream(p))",
    "})().catch(e=>{console.error(e.stack);process.exit(1)})",
  ].join(";");
  return `node -e ${shellQuote(script)} ${shellQuote(url)} ${shellQuote(target)}`;
}

function stageCommand(runtime: RuntimeDescriptor) {
  const sha = runtime.archiveSha256!;
  return [
    `: ${shellQuote(stageMarker(runtime))}`,
    "set -euo pipefail",
    'ROOT="/home/vercel-sandbox/connectome-runtime"',
    'rm -rf "$ROOT"',
    'mkdir -p "$ROOT"',
    'cd "$ROOT"',
    streamingDownload(runtime.archiveUrl, "arena-runtime.tar.gz"),
    streamingDownload(runtime.archiveShaUrl, "arena-runtime.tar.gz.sha256"),
    'expected="$(awk \'{print $1}\' arena-runtime.tar.gz.sha256)"',
    `test "$expected" = ${shellQuote(sha)}`,
    'printf "%s  %s\\n" "$expected" arena-runtime.tar.gz | sha256sum -c -',
    "tar -xzf arena-runtime.tar.gz",
    "test -x arena-runtime/bin/start-session",
    "test -s arena-runtime/manifest.json",
    "timeout 120 apt-get update -qq -o Acquire::Retries=2 -o Acquire::http::Timeout=15",
    "timeout 240 env DEBIAN_FRONTEND=noninteractive apt-get install -y -qq -o Acquire::Retries=2 -o Acquire::http::Timeout=15 -o DPkg::Lock::Timeout=30 fontconfig fonts-dejavu-core libosmesa6 libgl1-mesa-dri",
    "command -v fc-list >/dev/null",
    "fc-list 2>/dev/null | grep -q .",
    "ldconfig -p 2>/dev/null | grep -q 'libOSMesa.so'",
    `printf "%s\\n" ${shellQuote(sha)} > .runtime-archive-sha256`,
    `printf "%s\\n" ${shellQuote(STAGE_VERSION)} > .renderer-stage-version`,
    "rm -f arena-runtime.tar.gz arena-runtime.tar.gz.sha256",
  ].join("; ");
}

async function listCommands(token: string, sessionId: string): Promise<any[]> {
  const response = await fetch(apiUrl(`/v2/sandboxes/sessions/${encodeURIComponent(sessionId)}/cmd`), {
    cache: "no-store",
    headers: apiHeaders(token),
    signal: AbortSignal.timeout(7000),
  });
  if (!response.ok) return [];
  const body = await response.json().catch(() => ({}));
  return Array.isArray(body?.commands) ? body.commands : [];
}

async function probeStageReady(token: string, sessionId: string, runtime: RuntimeDescriptor) {
  const sha = runtime.archiveSha256!;
  const probe = [
    "set +e",
    'ROOT="/home/vercel-sandbox/connectome-runtime"',
    `test "$(cat \"$ROOT/.runtime-archive-sha256\" 2>/dev/null)" = ${shellQuote(sha)} || exit 1`,
    `test "$(cat \"$ROOT/.renderer-stage-version\" 2>/dev/null)" = ${shellQuote(STAGE_VERSION)} || exit 1`,
    'test -x "$ROOT/arena-runtime/bin/start-session" || exit 1',
    "command -v fc-list >/dev/null 2>&1 || exit 1",
    "fc-list 2>/dev/null | grep -q . || exit 1",
    "ldconfig -p 2>/dev/null | grep -q 'libOSMesa.so' || exit 1",
    "echo renderer-stage-ready",
  ].join("; ");
  try {
    const response = await fetch(apiUrl(`/v2/sandboxes/sessions/${encodeURIComponent(sessionId)}/cmd`), {
      method: "POST",
      headers: apiHeaders(token),
      body: JSON.stringify({ command: "bash", args: ["-lc", probe], cwd: "/home/vercel-sandbox", wait: true, logs: true, timeout: 8000 }),
      signal: AbortSignal.timeout(10_000),
    });
    return response.ok && (await response.text()).includes("renderer-stage-ready");
  } catch {
    return false;
  }
}

async function startStage(token: string, sessionId: string, runtime: RuntimeDescriptor) {
  const response = await fetch(apiUrl(`/v2/sandboxes/sessions/${encodeURIComponent(sessionId)}/cmd`), {
    method: "POST",
    headers: apiHeaders(token),
    body: JSON.stringify({
      command: "bash",
      args: ["-lc", stageCommand(runtime)],
      cwd: "/home/vercel-sandbox",
      wait: false,
      logs: false,
      sudo: true,
      timeout: 1_200_000,
    }),
    signal: AbortSignal.timeout(10_000),
  });
  const body = await response.json().catch(() => ({}));
  return { response, body, commandId: body?.command?.id ?? body?.id ?? null };
}

async function createBase(token: string, runtime: RuntimeDescriptor, name: string): Promise<RuntimeBaseState> {
  const projectId = vercelProjectId();
  if (!projectId) return { ready: false, status: "project-unavailable", name, reason: "VERCEL_PROJECT_ID is unavailable" };
  const response = await fetch(apiUrl("/v2/sandboxes"), {
    method: "POST",
    headers: apiHeaders(token),
    body: JSON.stringify({
      projectId,
      name,
      runtime: "node24",
      timeout: 1_200_000,
      persistent: true,
      snapshotExpiration: SNAPSHOT_TTL_MS,
      keepLastSnapshots: { count: 1, expiration: SNAPSHOT_TTL_MS, deleteEvicted: true },
      resources: { vcpus: 4, memory: 8192 },
      tags: { app: "connectome-fighter", role: "runtime-base", stage: STAGE_VERSION, runtime: runtime.archiveSha256!.slice(0, 16) },
    }),
    signal: AbortSignal.timeout(12_000),
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    const capacity = capacityState(name, body);
    if (capacity) return capacity;
    return { ready: false, status: response.status === 409 ? "create-conflict" : "create-error", name, reason: JSON.stringify(body).slice(0, 1200) };
  }
  const sessionId = body?.session?.id ?? body?.sandbox?.currentSessionId ?? body?.id ?? null;
  if (!sessionId) return { ready: false, status: "create-missing-session", name };
  const started = await startStage(token, String(sessionId), runtime);
  if (!started.response.ok) {
    const capacity = capacityState(name, started.body);
    if (capacity) return { ...capacity, session_id: String(sessionId) };
    return { ready: false, status: "stage-start-error", name, session_id: String(sessionId), reason: JSON.stringify(started.body).slice(0, 1200) };
  }
  return { ready: false, status: "stage-running", name, session_id: String(sessionId), command_id: started.commandId, stage_age_seconds: 0 };
}

async function resetBase(token: string, runtime: RuntimeDescriptor, name: string) {
  await fetch(namedSandboxUrl(name), { method: "DELETE", headers: apiHeaders(token), signal: AbortSignal.timeout(8000) }).catch(() => null);
  return createBase(token, runtime, name);
}

export async function advanceRuntimeBase(token: string, runtime: RuntimeDescriptor): Promise<RuntimeBaseState> {
  const name = runtimeBaseName(runtime);
  if (!runtime.ready || !name) return { ready: false, status: "runtime-release-unavailable", name, reason: runtime.reason };
  let response: Response;
  try {
    response = await fetch(namedSandboxUrl(name), { cache: "no-store", headers: apiHeaders(token), signal: AbortSignal.timeout(8000) });
  } catch (error) {
    return { ready: false, status: "inspect-error", name, reason: error instanceof Error ? error.message : "sandbox inspect failed" };
  }
  const body = await response.json().catch(() => ({}));
  if (response.status === 404) return createBase(token, runtime, name);
  if (!response.ok) {
    const capacity = capacityState(name, body);
    if (capacity) return capacity;
    return { ready: false, status: "inspect-error", name, reason: `named sandbox HTTP ${response.status}` };
  }
  const sandbox = body?.sandbox ?? body;
  const snapshotId = sandbox?.currentSnapshotId ?? null;
  const session = body?.session ?? null;
  const sessionId = session?.id ?? sandbox?.currentSessionId ?? null;
  if (snapshotId) return { ready: true, status: "ready", name, snapshot_id: snapshotId, session_id: sessionId ? String(sessionId) : null };
  if (!sessionId) return { ready: false, status: "warming-no-session", name };

  if (await probeStageReady(token, String(sessionId), runtime)) {
    const stop = await fetch(apiUrl(`/v2/sandboxes/sessions/${encodeURIComponent(String(sessionId))}/stop`), {
      method: "POST",
      headers: apiHeaders(token),
      signal: AbortSignal.timeout(10_000),
    });
    if (!stop.ok && ![409, 410, 422].includes(stop.status)) {
      const stopBody = await stop.json().catch(() => ({}));
      const capacity = capacityState(name, stopBody);
      if (capacity) return { ...capacity, session_id: String(sessionId) };
      return { ready: false, status: "snapshot-stop-error", name, session_id: String(sessionId), reason: `stop HTTP ${stop.status}` };
    }
    return { ready: false, status: "snapshotting", name, session_id: String(sessionId) };
  }

  const commands = await listCommands(token, String(sessionId));
  const marker = stageMarker(runtime);
  const stage = commands.find((row) => JSON.stringify(row).includes(marker));
  if (!stage) {
    const started = await startStage(token, String(sessionId), runtime);
    if (!started.response.ok) {
      const capacity = capacityState(name, started.body);
      if (capacity) return { ...capacity, session_id: String(sessionId) };
      return { ready: false, status: "stage-start-error", name, session_id: String(sessionId), reason: JSON.stringify(started.body).slice(0, 1200) };
    }
    return { ready: false, status: "stage-running", name, session_id: String(sessionId), command_id: started.commandId, stage_age_seconds: 0 };
  }
  const exitCode = commandExitCode(stage);
  const age = commandAgeSeconds(stage);
  if (exitCode !== null && exitCode !== 0) return resetBase(token, runtime, name);
  if (age !== null && age > STAGE_STALE_SECONDS) return resetBase(token, runtime, name);
  return { ready: false, status: "stage-running", name, session_id: String(sessionId), command_id: stage?.id ?? null, stage_age_seconds: age };
}
