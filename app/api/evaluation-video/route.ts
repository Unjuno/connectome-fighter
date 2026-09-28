import { NextRequest } from "next/server";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

const RAW_BASE = "https://raw.githubusercontent.com/Unjuno/connectome-fighter/main/site/data";
const RELEASE_PATH = /^\/Unjuno\/connectome-fighter\/releases\/download\/combat-evaluation-\d+\/(?:before|after)\.mp4$/;

type JsonRecord = Record<string, any>;

async function fetchJson(name: string): Promise<JsonRecord | null> {
  try {
    const response = await fetch(`${RAW_BASE}/${name}?t=${Date.now()}`, {
      cache: "no-store",
      headers: { "User-Agent": "connectome-fighter-evaluation-video/1" },
      signal: AbortSignal.timeout(8_000),
    });
    if (!response.ok) return null;
    return (await response.json()) as JsonRecord;
  } catch {
    return null;
  }
}

function publishedVideoUrl(evaluation: JsonRecord | null) {
  const raw = evaluation?.video?.asset_url;
  if (typeof raw !== "string") return null;
  try {
    const url = new URL(raw);
    if (url.protocol !== "https:" || url.hostname !== "github.com") return null;
    if (!RELEASE_PATH.test(url.pathname)) return null;
    return url;
  } catch {
    return null;
  }
}

export async function GET(request: NextRequest) {
  const phase = request.nextUrl.searchParams.get("phase") === "previous" ? "previous" : "latest";
  const evaluation = await fetchJson(phase === "previous" ? "evaluation-previous.json" : "evaluation-status.json");
  const source = publishedVideoUrl(evaluation);

  if (!source) {
    return Response.json({ ready: false, status: "evaluation-video-unavailable", phase }, { status: 404 });
  }

  const upstreamHeaders = new Headers({
    Accept: "video/mp4",
    "User-Agent": "connectome-fighter-evaluation-video/1",
  });
  const range = request.headers.get("range");
  if (range) upstreamHeaders.set("Range", range);

  let upstream: Response;
  try {
    upstream = await fetch(source, {
      cache: "no-store",
      headers: upstreamHeaders,
      redirect: "follow",
      signal: AbortSignal.timeout(15_000),
    });
  } catch {
    return Response.json({ ready: false, status: "evaluation-video-upstream-unreachable", phase }, { status: 502 });
  }

  if (!upstream.ok && upstream.status !== 206) {
    return Response.json(
      { ready: false, status: "evaluation-video-upstream-error", phase, upstream_status: upstream.status },
      { status: 502 },
    );
  }

  const headers = new Headers();
  for (const name of ["content-type", "content-length", "content-range", "accept-ranges", "etag", "last-modified"]) {
    const value = upstream.headers.get(name);
    if (value) headers.set(name, value);
  }
  headers.set("Content-Type", upstream.headers.get("content-type") || "video/mp4");
  headers.set("Content-Disposition", "inline");
  headers.set("Cache-Control", "private, no-store, max-age=0");
  headers.set("X-Content-Type-Options", "nosniff");

  return new Response(upstream.body, { status: upstream.status, headers });
}
