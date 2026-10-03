import { NextRequest } from "next/server";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

const RAW_BASE = "https://raw.githubusercontent.com/Unjuno/connectome-fighter/main/site/data";
const RELEASE_PATH = /^\/Unjuno\/connectome-fighter\/releases\/download\/combat-evaluation-\d+\/(?:before|after)\.mp4$/;
const MAX_VIDEO_BYTES = 16 * 1024 * 1024;

type JsonRecord = Record<string, any>;
type ByteRange = { start: number; end: number } | null | "invalid";

async function fetchJson(name: string): Promise<JsonRecord | null> {
  try {
    const response = await fetch(`${RAW_BASE}/${name}?t=${Date.now()}`, {
      cache: "no-store",
      headers: { "User-Agent": "connectome-fighter-evaluation-video/2" },
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

function parseSingleRange(raw: string | null, total: number): ByteRange {
  if (!raw) return null;
  const match = /^bytes=(\d*)-(\d*)$/.exec(raw.trim());
  if (!match || (!match[1] && !match[2]) || total <= 0) return "invalid";

  if (!match[1]) {
    const suffix = Number(match[2]);
    if (!Number.isSafeInteger(suffix) || suffix <= 0) return "invalid";
    return { start: Math.max(total - suffix, 0), end: total - 1 };
  }

  const start = Number(match[1]);
  if (!Number.isSafeInteger(start) || start < 0 || start >= total) return "invalid";

  if (!match[2]) return { start, end: total - 1 };
  const requestedEnd = Number(match[2]);
  if (!Number.isSafeInteger(requestedEnd) || requestedEnd < start) return "invalid";
  return { start, end: Math.min(requestedEnd, total - 1) };
}

function videoHeaders(total: number, upstream: Response) {
  const headers = new Headers({
    "Accept-Ranges": "bytes",
    "Content-Type": "video/mp4",
    "Content-Disposition": "inline",
    "Cache-Control": "private, no-store, max-age=0",
    "X-Content-Type-Options": "nosniff",
  });
  for (const name of ["etag", "last-modified"]) {
    const value = upstream.headers.get(name);
    if (value) headers.set(name, value);
  }
  headers.set("Content-Length", String(total));
  return headers;
}

async function loadVideo(source: URL) {
  const upstream = await fetch(source, {
    cache: "force-cache",
    headers: {
      Accept: "video/mp4,application/octet-stream;q=0.9,*/*;q=0.8",
      "User-Agent": "connectome-fighter-evaluation-video/2",
    },
    redirect: "follow",
    signal: AbortSignal.timeout(20_000),
  });
  if (!upstream.ok) return { upstream, buffer: null as ArrayBuffer | null };
  const buffer = await upstream.arrayBuffer();
  if (buffer.byteLength <= 0 || buffer.byteLength > MAX_VIDEO_BYTES) {
    return { upstream, buffer: null as ArrayBuffer | null };
  }
  return { upstream, buffer };
}

async function serve(request: NextRequest, headOnly = false) {
  const phase = request.nextUrl.searchParams.get("phase") === "previous" ? "previous" : "latest";
  const evaluation = await fetchJson(phase === "previous" ? "evaluation-previous.json" : "evaluation-status.json");
  const source = publishedVideoUrl(evaluation);

  if (!source) {
    return Response.json({ ready: false, status: "evaluation-video-unavailable", phase }, { status: 404 });
  }

  let loaded: Awaited<ReturnType<typeof loadVideo>>;
  try {
    loaded = await loadVideo(source);
  } catch {
    return Response.json({ ready: false, status: "evaluation-video-upstream-unreachable", phase }, { status: 502 });
  }

  if (!loaded.upstream.ok || !loaded.buffer) {
    return Response.json(
      {
        ready: false,
        status: loaded.upstream.ok ? "evaluation-video-invalid-size" : "evaluation-video-upstream-error",
        phase,
        upstream_status: loaded.upstream.status,
      },
      { status: 502 },
    );
  }

  const total = loaded.buffer.byteLength;
  const range = parseSingleRange(request.headers.get("range"), total);
  const headers = videoHeaders(total, loaded.upstream);

  if (range === "invalid") {
    headers.set("Content-Range", `bytes */${total}`);
    headers.set("Content-Length", "0");
    return new Response(null, { status: 416, headers });
  }

  if (!range) {
    return new Response(headOnly ? null : loaded.buffer, { status: 200, headers });
  }

  const length = range.end - range.start + 1;
  headers.set("Content-Range", `bytes ${range.start}-${range.end}/${total}`);
  headers.set("Content-Length", String(length));
  const body = headOnly ? null : loaded.buffer.slice(range.start, range.end + 1);
  return new Response(body, { status: 206, headers });
}

export async function GET(request: NextRequest) {
  return serve(request);
}

export async function HEAD(request: NextRequest) {
  return serve(request, true);
}
