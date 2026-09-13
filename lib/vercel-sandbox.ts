export type ProviderFailure = {
  code: string | null;
  message: string | null;
  capacityBlocked: boolean;
  blockedUntil: string | null;
};

export function vercelProjectId() {
  return process.env.VERCEL_PROJECT_ID?.trim() || null;
}

export function vercelAuthToken(headers?: Headers) {
  return (
    process.env.VERCEL_OIDC_TOKEN?.trim() ||
    headers?.get("x-vercel-oidc-token")?.trim() ||
    process.env.VERCEL_TOKEN?.trim() ||
    null
  );
}

export function apiUrl(path: string) {
  const url = new URL(`https://api.vercel.com${path}`);
  const teamId = process.env.VERCEL_TEAM_ID?.trim();
  if (teamId) url.searchParams.set("teamId", teamId);
  return url;
}

export function namedSandboxUrl(name: string) {
  const projectId = vercelProjectId();
  if (!projectId) throw new Error("VERCEL_PROJECT_ID is unavailable");
  const url = apiUrl(`/v2/sandboxes/${encodeURIComponent(name)}`);
  url.searchParams.set("projectId", projectId);
  return url;
}

export function apiHeaders(token: string) {
  return { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };
}

export function providerFailure(body: any): ProviderFailure {
  const code = typeof body?.error?.code === "string" ? body.error.code : null;
  const message =
    typeof body?.error?.message === "string"
      ? body.error.message
      : typeof body?.message === "string"
        ? body.message
        : null;
  const capacityBlocked =
    code === "payment_required" || /usage limit exceeded|upgrade to a Pro plan/i.test(message ?? "");
  const blockedUntil = message?.match(/reset on ([0-9T:.+-]+Z?)/i)?.[1] ?? null;
  return { code, message, capacityBlocked, blockedUntil };
}

export function shellQuote(value: string) {
  return `'${value.replaceAll("'", `'"'"'`)}'`;
}

export function parseTimeMs(value: unknown) {
  if (typeof value === "number" && Number.isFinite(value)) {
    return value < 10_000_000_000 ? value * 1000 : value;
  }
  if (typeof value === "string" && value.trim()) {
    const numeric = Number(value);
    if (Number.isFinite(numeric)) return numeric < 10_000_000_000 ? numeric * 1000 : numeric;
    const parsed = Date.parse(value);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}

export function commandExitCode(command: any) {
  const raw = command?.exitCode;
  if (raw === null || raw === undefined || raw === "") return null;
  const parsed = Number(raw);
  return Number.isFinite(parsed) ? parsed : null;
}

export function commandAgeSeconds(command: any) {
  for (const value of [command?.startedAt, command?.createdAt, command?.requestedAt]) {
    const at = parseTimeMs(value);
    if (at !== null) return Math.max(0, Math.floor((Date.now() - at) / 1000));
  }
  return null;
}
