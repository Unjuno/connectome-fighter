const RELEASE_BASE =
  process.env.CONNECTOME_RUNTIME_RELEASE_BASE?.trim() ||
  "https://github.com/Unjuno/connectome-fighter/releases/download/arena-runtime-latest";
const MANIFEST_URL = `${RELEASE_BASE}/manifest.json`;
const ARCHIVE_URL = `${RELEASE_BASE}/arena-runtime.tar.gz`;
const ARCHIVE_SHA_URL = `${RELEASE_BASE}/arena-runtime.tar.gz.sha256`;

export const FLYBODY_COMMIT = "d015e9bfe441bd90ae431bac24c55cb74bdbce26";
export const FLYBODY_ADAPTER_ID = "malecns-annotated-motor-to-flybody-tripod-v2";

export type RuntimeDescriptor = {
  ready: boolean;
  reason: string | null;
  archiveSha256: string | null;
  manifest: any;
  archiveUrl: string;
  archiveShaUrl: string;
};

export async function runtimeDescriptor(): Promise<RuntimeDescriptor> {
  try {
    const [manifestResponse, shaResponse] = await Promise.all([
      fetch(MANIFEST_URL, {
        cache: "no-store",
        headers: { "User-Agent": "connectome-fighter-dedicated-live/1" },
        signal: AbortSignal.timeout(8000),
      }),
      fetch(ARCHIVE_SHA_URL, {
        cache: "no-store",
        headers: { "User-Agent": "connectome-fighter-dedicated-live/1" },
        signal: AbortSignal.timeout(8000),
      }),
    ]);
    if (!manifestResponse.ok || !shaResponse.ok) {
      return {
        ready: false,
        reason: `runtime release unavailable (${manifestResponse.status}/${shaResponse.status})`,
        archiveSha256: null,
        manifest: null,
        archiveUrl: ARCHIVE_URL,
        archiveShaUrl: ARCHIVE_SHA_URL,
      };
    }
    const manifest = await manifestResponse.json().catch(() => null);
    const shaText = await shaResponse.text();
    const archiveSha256 = shaText.match(/\b[a-f0-9]{64}\b/i)?.[0]?.toLowerCase() ?? null;
    const valid =
      Number(manifest?.schema_version ?? 0) >= 4 &&
      manifest?.kind === "connectome-fighter-arena-runtime-bundle" &&
      manifest?.canonical_model === "MaleCNS v1.0 + pinned Shiu LIF" &&
      manifest?.learning_enabled === false &&
      manifest?.policy_pixel_access === false &&
      manifest?.runtime_prebuilt === true &&
      manifest?.flybody_physics_spectator === true &&
      manifest?.flybody_upstream_repository === "TuragaLab/flybody" &&
      manifest?.flybody_upstream_commit === FLYBODY_COMMIT &&
      manifest?.flybody_neural_adapter === FLYBODY_ADAPTER_ID &&
      manifest?.flybody_policy_access === false &&
      manifest?.flybody_game_telemetry_position_used === false &&
      manifest?.flybody_mujoco_gl === "osmesa" &&
      Boolean(archiveSha256);
    return {
      ready: Boolean(valid),
      reason: valid ? null : "rolling runtime does not satisfy the neural FlyBody publication contract",
      archiveSha256,
      manifest,
      archiveUrl: ARCHIVE_URL,
      archiveShaUrl: ARCHIVE_SHA_URL,
    };
  } catch (error) {
    return {
      ready: false,
      reason: error instanceof Error ? error.message : "runtime release lookup failed",
      archiveSha256: null,
      manifest: null,
      archiveUrl: ARCHIVE_URL,
      archiveShaUrl: ARCHIVE_SHA_URL,
    };
  }
}

export function runtimeBaseName(runtime: RuntimeDescriptor) {
  return runtime.archiveSha256 ? `connectome-runtime-${runtime.archiveSha256.slice(0, 16)}` : null;
}
