import { NextRequest, NextResponse } from "next/server";
import { inspectBroadcast, maintainBroadcast } from "@/lib/connectome-broadcast";
import { advanceRuntimeBase } from "@/lib/runtime-base";
import { FLYBODY_ADAPTER_ID, FLYBODY_COMMIT, runtimeDescriptor } from "@/lib/runtime-release";
import { vercelAuthToken, vercelProjectId } from "@/lib/vercel-sandbox";

export const dynamic = "force-dynamic";
export const revalidate = 0;
export const maxDuration = 60;

function mediaUrls(telemetryUrl: unknown) {
  if (typeof telemetryUrl !== "string" || !telemetryUrl) return { screen_url: null, activity_url: null, flybody_p1_url: null, flybody_p2_url: null, flybody_state_url: null };
  try {
    const url = new URL(telemetryUrl);
    url.pathname = "";
    url.search = "";
    url.hash = "";
    const base = url.toString().replace(/\/$/, "");
    return { screen_url: `${base}/screen.png`, activity_url: `${base}/activity.json`, flybody_p1_url: `${base}/flybody-p1.png`, flybody_p2_url: `${base}/flybody-p2.png`, flybody_state_url: `${base}/flybody.json` };
  } catch {
    return { screen_url: null, activity_url: null, flybody_p1_url: null, flybody_p2_url: null, flybody_state_url: null };
  }
}

function publicBody(body: any, runtimeSha: string | null, extra: Record<string, unknown> = {}) {
  return {
    ...body,
    ...mediaUrls(body?.telemetry_url),
    ...extra,
    runtime_archive_sha256: body?.runtime_archive_sha256 ?? runtimeSha,
    media_source: "official-fightingice-screendata",
    flybody_source: "TuragaLab/flybody MuJoCo physics",
    flybody_upstream_commit: FLYBODY_COMMIT,
    flybody_neural_adapter: FLYBODY_ADAPTER_ID,
    flybody_neural_drive: "MaleCNS annotated motor output through project-defined adapter",
    flybody_policy_access: false,
    flybody_game_telemetry_position_used: false,
    learning_enabled: false,
    policy_pixel_access: false,
    served_lineage: { p1: "GARNET generation-2 approved inference", p2: "ZEN canonical baseline", candidate_auto_promotion: false },
  };
}

export async function GET(request: NextRequest) {
  const runtime = await runtimeDescriptor();
  const token = vercelAuthToken(request.headers);
  if (!vercelProjectId()) return NextResponse.json(publicBody({ ready: false, status: "project-unavailable", telemetry_url: null, stream_url: null, reason: "VERCEL_PROJECT_ID is unavailable" }, runtime.archiveSha256), { status: 503, headers: { "Cache-Control": "no-store" } });
  if (!token) return NextResponse.json(publicBody({ ready: false, status: "auth-unavailable", telemetry_url: null, stream_url: null, reason: "Vercel OIDC token is unavailable" }, runtime.archiveSha256), { status: 503, headers: { "Cache-Control": "no-store" } });

  const base = await advanceRuntimeBase(token, runtime);
  if (base.status === "capacity-blocked") {
    return NextResponse.json(publicBody({ ready: false, status: "capacity-blocked", telemetry_url: null, stream_url: null, capacity_blocked: true, provider_error_code: base.provider_error_code, reason: base.reason, blocked_until: base.blocked_until, source_runtime_base: base.name }, runtime.archiveSha256), { status: 503, headers: { "Cache-Control": "no-store", "Retry-After": "3600" } });
  }
  if (!base.ready) {
    return NextResponse.json(publicBody({ ready: false, status: "warming-runtime-base", telemetry_url: null, stream_url: null, source_runtime_base: base.name, maintenance_action: base.status, reason: base.reason ?? null }, runtime.archiveSha256), { status: 202, headers: { "Cache-Control": "no-store", "Retry-After": "5" } });
  }

  const maintenance = await maintainBroadcast(token, runtime);
  if (maintenance.status === "capacity-blocked" || maintenance.action === "capacity-blocked") {
    return NextResponse.json(publicBody({ ready: false, status: "capacity-blocked", telemetry_url: null, stream_url: null, capacity_blocked: true, provider_error_code: maintenance.provider_error_code ?? null, reason: maintenance.reason ?? "Vercel Sandbox capacity unavailable", blocked_until: maintenance.blocked_until ?? null, source_runtime_base: base.name, maintenance_action: maintenance.action }, runtime.archiveSha256), { status: 503, headers: { "Cache-Control": "no-store", "Retry-After": "3600" } });
  }
  const body = await inspectBroadcast(token, runtime);
  return NextResponse.json(publicBody(body, runtime.archiveSha256, { maintenance_action: maintenance.action ?? null }), {
    status: body.ready ? 200 : 202,
    headers: { "Cache-Control": "no-store", "Retry-After": body.ready ? "1" : "4" },
  });
}
