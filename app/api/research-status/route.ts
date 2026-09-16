import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

function sourceUrl() {
  const ref = process.env.VERCEL_GIT_COMMIT_SHA || "main";
  return `https://raw.githubusercontent.com/Unjuno/connectome-fighter/${encodeURIComponent(ref)}/site/data/research-status.json`;
}

export async function GET() {
  try {
    const response = await fetch(`${sourceUrl()}?t=${Date.now()}`, {
      cache: "no-store",
      headers: { "User-Agent": "connectome-fighter-research-status/1" },
      signal: AbortSignal.timeout(8000),
    });
    if (!response.ok) {
      return NextResponse.json(
        { ready: false, status: "research-status-unavailable", source_status: response.status },
        { status: 503, headers: { "Cache-Control": "no-store, max-age=0" } },
      );
    }
    const research = await response.json();
    return NextResponse.json(
      { ready: true, status: "research-status-ready", research },
      { headers: { "Cache-Control": "no-store, max-age=0" } },
    );
  } catch {
    return NextResponse.json(
      { ready: false, status: "research-status-unavailable" },
      { status: 503, headers: { "Cache-Control": "no-store, max-age=0" } },
    );
  }
}
