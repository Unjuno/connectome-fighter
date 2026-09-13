import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

const RAW_BASE = "https://raw.githubusercontent.com/Unjuno/connectome-fighter/main/site/data";

type JsonRecord = Record<string, unknown>;

async function fetchJson(name: string): Promise<JsonRecord | null> {
  try {
    const response = await fetch(`${RAW_BASE}/${name}?t=${Date.now()}`, {
      cache: "no-store",
      headers: { "User-Agent": "connectome-fighter-model-evaluation/1" },
      signal: AbortSignal.timeout(8000),
    });
    if (!response.ok) return null;
    return (await response.json()) as JsonRecord;
  } catch {
    return null;
  }
}

export async function GET() {
  const [latest, previous, training] = await Promise.all([
    fetchJson("evaluation-status.json"),
    fetchJson("evaluation-previous.json"),
    fetchJson("training-status.json"),
  ]);

  return NextResponse.json(
    {
      ready: Boolean(latest),
      status: latest ? "evaluation-ready" : "awaiting-first-post-update-round",
      latest,
      previous,
      training,
    },
    {
      headers: {
        "Cache-Control": "no-store, max-age=0",
      },
    },
  );
}
