import { NextRequest, NextResponse } from "next/server";
import { advanceRuntimeBase } from "@/lib/runtime-base";
import { runtimeDescriptor } from "@/lib/runtime-release";
import { vercelAuthToken, vercelProjectId } from "@/lib/vercel-sandbox";

export const dynamic = "force-dynamic";
export const revalidate = 0;
export const maxDuration = 60;

export async function GET(request: NextRequest) {
  const runtime = await runtimeDescriptor();
  const token = vercelAuthToken(request.headers);
  if (!vercelProjectId()) {
    return NextResponse.json({ ready: false, status: "project-unavailable", reason: "VERCEL_PROJECT_ID is unavailable", runtime_archive_sha256: runtime.archiveSha256 }, { status: 503, headers: { "Cache-Control": "no-store" } });
  }
  if (!token) {
    return NextResponse.json({ ready: false, status: "auth-unavailable", reason: "Vercel OIDC token is unavailable", runtime_archive_sha256: runtime.archiveSha256 }, { status: 503, headers: { "Cache-Control": "no-store" } });
  }
  const base = await advanceRuntimeBase(token, runtime);
  const capacityBlocked = base.status === "capacity-blocked";
  return NextResponse.json(
    {
      ...base,
      capacity_blocked: capacityBlocked,
      runtime_archive_sha256: runtime.archiveSha256,
      learning_enabled: false,
      policy_pixel_access: false,
      renderer: "fontconfig+OSMesa baked into SHA-addressed runtime base",
      retention: "persistent-immutable-runtime-base-only",
    },
    {
      status: base.ready ? 200 : capacityBlocked ? 503 : 202,
      headers: { "Cache-Control": "no-store", ...(base.ready ? {} : { "Retry-After": capacityBlocked ? "3600" : "6" }) },
    },
  );
}
