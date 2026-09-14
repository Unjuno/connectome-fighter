import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

const RAW_BASE = "https://raw.githubusercontent.com/Unjuno/connectome-fighter/main/site/data";
const COLOSSEUM_STATUS = "https://github.com/Unjuno/connectome-fighter/releases/download/colosseum-latest/status.json";
type JsonRecord = Record<string, any>;

async function fetchJson(url: string): Promise<JsonRecord | null> {
  try {
    const response = await fetch(`${url}?t=${Date.now()}`, {
      cache: "no-store",
      headers: { "User-Agent": "connectome-fighter-colosseum/1" },
      signal: AbortSignal.timeout(8000),
    });
    if (!response.ok) return null;
    const body = await response.json();
    return body && typeof body === 'object' && !Array.isArray(body) ? body : null;
  } catch { return null; }
}

export async function GET() {
  const [season, latest, previous, training] = await Promise.all([
    fetchJson(COLOSSEUM_STATUS),
    fetchJson(`${RAW_BASE}/evaluation-status.json`),
    fetchJson(`${RAW_BASE}/evaluation-previous.json`),
    fetchJson(`${RAW_BASE}/training-status.json`),
  ]);
  const validSeason = season?.kind === 'colosseum-season-status'
    && season.lineage === 'colosseum-r3-v1' && season.status === 'evaluation-ready'
    && season.production_learning_enabled === false
    && season.latest?.candidate_only === true && season.latest?.auto_promotion === false
    && season.latest?.policy_pixel_access === false && season.latest?.status === 'COMPLETED'
    && season.latest?.state_sha256 === season.training?.state_sha256;
  return NextResponse.json(
    validSeason ? { ...season, colosseum: season, source: 'colosseum-completed-cycle' } : {
      ready: Boolean(latest),
      status: latest ? "evaluation-ready" : "awaiting-first-post-update-round",
      latest, previous, training,
      colosseum: { status: 'unavailable-or-awaiting-first-cycle', requested_interval_minutes: 10 },
      source: 'legacy-completed-evaluation',
    },
    { headers: { "Cache-Control": "no-store, max-age=0" } },
  );
}
