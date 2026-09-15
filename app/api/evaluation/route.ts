import { NextResponse } from "next/server";
import { isPairedView } from "../../../lib/paired-view";

export const dynamic = "force-dynamic";
const RAW_BASE = "https://raw.githubusercontent.com/Unjuno/connectome-fighter/main/site/data";
const headers = { "Cache-Control": "no-store, max-age=0" };

async function request(name: string) {
  return fetch(`${RAW_BASE}/${name}?t=${Date.now()}`, {
    cache: "no-store", headers: { "User-Agent": "connectome-fighter-model-evaluation/2" },
    signal: AbortSignal.timeout(8000),
  });
}
async function historical(name: string) {
  try { const response = await request(name); return response.ok ? await response.json() : null; }
  catch { return null; }
}
export async function GET() {
  try {
    const response = await request("paired-latest.json");
    if (response.ok) {
      const view: unknown = await response.json();
      if (!isPairedView(view)) throw new Error("paired-envelope-contract-failed");
      return NextResponse.json(view, { headers });
    }
    if (response.status !== 404) throw new Error("paired-source-unavailable");
    // Only genuine absence before first publication may show historical R2e.
    const [latest, previous, training] = await Promise.all([
      historical("evaluation-status.json"), historical("evaluation-previous.json"), historical("training-status.json"),
    ]);
    return NextResponse.json({ ready: Boolean(latest), status: latest ? "evaluation-ready" : "awaiting-first-post-update-round",
      latest, previous, training, paired_status: "not-yet-published" }, { headers });
  } catch {
    return NextResponse.json({ ready: false, status: "paired-evidence-unavailable", latest: null, previous: null, training: null },
      { status: 503, headers });
  }
}
