#!/usr/bin/env bash
set -euo pipefail

P1="GARNET"
P2="ZEN"
MANIFEST_URL="https://github.com/Unjuno/connectome-fighter/releases/download/arena-inference-latest/manifest.json"
LISTEN=8080
UPSTREAM_PORT=18080
SESSION_ID=""
FIGHTINGICE_MODE="${CONNECTOME_FIGHTINGICE_MODE:-}"

# One-shot diagnostics intentionally remain observable for 30 seconds and keep
# the lightweight FightingICE path. The public broadcast needs the official
# headless renderer because that is the v7.1 path that emits ScreenData.
if [[ "${CONNECTOME_PUBLIC_BROADCAST:-false}" == "true" ]]; then
  POST_FIGHT_SECONDS="${CONNECTOME_POST_FIGHT_SECONDS:-1}"
  POST_SESSION_SECONDS="${CONNECTOME_POST_SESSION_SECONDS:-1}"
  if [[ -z "$FIGHTINGICE_MODE" ]]; then FIGHTINGICE_MODE="headless"; fi
else
  POST_FIGHT_SECONDS="${CONNECTOME_POST_FIGHT_SECONDS:-30}"
  POST_SESSION_SECONDS="${CONNECTOME_POST_SESSION_SECONDS:-30}"
  if [[ -z "$FIGHTINGICE_MODE" ]]; then FIGHTINGICE_MODE="lightweight"; fi
fi

while (($#)); do
  case "$1" in
    --p1) P1="$2"; shift 2 ;;
    --p2) P2="$2"; shift 2 ;;
    --manifest-url) MANIFEST_URL="$2"; shift 2 ;;
    --listen) LISTEN="$2"; shift 2 ;;
    --session-id) SESSION_ID="$2"; shift 2 ;;
    --fightingice-mode) FIGHTINGICE_MODE="$2"; shift 2 ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done

case "$P1" in GARNET|ZEN|LUD|NEZ) ;; *) echo "invalid P1" >&2; exit 2;; esac
case "$P2" in GARNET|ZEN|LUD|NEZ) ;; *) echo "invalid P2" >&2; exit 2;; esac
case "$FIGHTINGICE_MODE" in lightweight|headless) ;; *) echo "invalid FightingICE mode" >&2; exit 2;; esac
for duration in "$POST_FIGHT_SECONDS" "$POST_SESSION_SECONDS"; do
  [[ "$duration" =~ ^[0-9]+([.][0-9]+)?$ ]] || { echo "invalid hold duration: $duration" >&2; exit 2; }
done
if [[ "$P1" == "$P2" ]]; then echo "fighters must differ" >&2; exit 2; fi

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK="${CONNECTOME_SESSION_ROOT:-/tmp/connectome-arena-session}"
mkdir -p "$WORK"

if [[ -z "$SESSION_ID" ]]; then
  SESSION_ID="arena-$(date +%s)-$RANDOM"
fi

STATUS_FILE="$WORK/bootstrap-status.json"
SCREEN_FILE="$WORK/latest-screen.png"
ACTIVITY_FILE="$WORK/live-activity.json"
SCREEN_PID=""
ACTIVITY_PID=""
write_status() {
  local phase="$1"
  local tmp="$STATUS_FILE.tmp"
  printf '{"phase":"%s"}\n' "$phase" > "$tmp"
  mv "$tmp" "$STATUS_FILE"
}
write_error() {
  local rc="$1"
  local line="$2"
  local tmp="$STATUS_FILE.tmp"
  printf '{"phase":"error","exit_code":%d,"line":%d,"error":"arena bootstrap failed"}\n' "$rc" "$line" > "$tmp"
  mv "$tmp" "$STATUS_FILE"
}

write_status "starting-proxy"
node "$ROOT/bin/bootstrap-proxy.mjs" \
  --listen "$LISTEN" \
  --upstream "$UPSTREAM_PORT" \
  --status-file "$STATUS_FILE" \
  --screen-file "$SCREEN_FILE" \
  --activity-file "$ACTIVITY_FILE" \
  --session-id "$SESSION_ID" \
  --p1 "$P1" \
  --p2 "$P2" &
PROXY_PID=$!

cleanup_children() {
  if [[ -n "$SCREEN_PID" ]]; then
    kill "$SCREEN_PID" >/dev/null 2>&1 || true
    wait "$SCREEN_PID" >/dev/null 2>&1 || true
  fi
  if [[ -n "$ACTIVITY_PID" ]]; then
    kill "$ACTIVITY_PID" >/dev/null 2>&1 || true
    wait "$ACTIVITY_PID" >/dev/null 2>&1 || true
  fi
  kill "$PROXY_PID" >/dev/null 2>&1 || true
  wait "$PROXY_PID" >/dev/null 2>&1 || true
}
on_error() {
  local rc=$?
  local line=${BASH_LINENO[0]:-0}
  trap - ERR
  write_error "$rc" "$line"
  # Keep the public bootstrap endpoint alive briefly so the viewer can surface the error.
  sleep 30
  cleanup_children
  exit "$rc"
}
trap on_error ERR
trap cleanup_children EXIT INT TERM

sleep 0.2
kill -0 "$PROXY_PID"
write_status "verifying-prebuilt-runtime"

REF_REL="$(cat "$ROOT/runtime/python310.path")"
BRIDGE_REL="$(cat "$ROOT/runtime/python311.path")"
REF_PY="$ROOT/$REF_REL"
BRIDGE_PY="$ROOT/$BRIDGE_REL"
SITE310="$ROOT/runtime/site310"
SITE311="$ROOT/runtime/site311"

for required in \
  "$REF_PY" \
  "$BRIDGE_PY" \
  "$SITE310/brian2" \
  "$SITE311/pyftg" \
  "$ROOT/data/malecns-shiu-strict-v1/connectivity.parquet" \
  "$ROOT/data/malecns-valence-v1/kc_mbon_valence_candidates.parquet" \
  "$ROOT/fightingice/FightingICE.jar" \
  "$ROOT/shiu/model.py"; do
  test -e "$required"
done

test -x "$REF_PY"
test -x "$BRIDGE_PY"

if [[ -x "$ROOT/runtime/jre21/bin/java" ]]; then
  export PATH="$ROOT/runtime/jre21/bin:$PATH"
elif ! command -v java >/dev/null 2>&1; then
  write_status "installing-java-fallback"
  if command -v sudo >/dev/null 2>&1; then
    sudo apt-get update -qq
    sudo env DEBIAN_FRONTEND=noninteractive apt-get install -y -qq openjdk-21-jre-headless ca-certificates curl
  else
    apt-get update -qq
    env DEBIAN_FRONTEND=noninteractive apt-get install -y -qq openjdk-21-jre-headless ca-certificates curl
  fi
fi
command -v java >/dev/null
command -v curl >/dev/null

ensure_font_runtime() {
  if command -v fc-list >/dev/null 2>&1 && fc-list 2>/dev/null | grep -q .; then
    return 0
  fi
  write_status "installing-font-runtime"
  if command -v sudo >/dev/null 2>&1; then
    sudo apt-get update -qq
    sudo env DEBIAN_FRONTEND=noninteractive apt-get install -y -qq fontconfig fonts-dejavu-core
  else
    apt-get update -qq
    env DEBIAN_FRONTEND=noninteractive apt-get install -y -qq fontconfig fonts-dejavu-core
  fi
  command -v fc-list >/dev/null
  fc-cache -f >/dev/null 2>&1 || true
  fc-list 2>/dev/null | grep -q .
}

# FightingICE v7.1 initializes the AWT LetterImage font in HEADLESS_MODE. Public
# ScreenData therefore requires a working font runtime; lightweight diagnostics
# skip this branch. The runtime-base prewarm may satisfy this before session boot.
if [[ "$FIGHTINGICE_MODE" == "headless" ]]; then
  ensure_font_runtime
else
  write_status "font-runtime-not-required-lightweight"
fi

REF_WRAPPER="$WORK/reference-python"
cat > "$REF_WRAPPER" <<EOF
#!/usr/bin/env bash
set -euo pipefail
export PYTHONPATH="$SITE310"
exec "$REF_PY" "\$@"
EOF
chmod +x "$REF_WRAPPER"

bridge_python() {
  PYTHONPATH="$ROOT/repo/src:$SITE311" "$BRIDGE_PY" "$@"
}

write_status "verifying-inference-snapshot"
SNAPSHOT_DIR="$WORK/snapshot"
mkdir -p "$SNAPSHOT_DIR"
curl -fL --retry 4 --retry-all-errors -o "$SNAPSHOT_DIR/manifest.json" "$MANIFEST_URL"
BASE_URL="${MANIFEST_URL%/manifest.json}"

bridge_python - "$SNAPSHOT_DIR/manifest.json" "$BASE_URL" "$SNAPSHOT_DIR" <<'PY'
import hashlib, json, pathlib, subprocess, sys
manifest_path, base_url, out_dir = sys.argv[1:]
m = json.load(open(manifest_path, encoding='utf-8'))
assert m.get('kind') == 'connectome-fighter-arena-inference-snapshot'
assert m.get('canonical_model') == 'MaleCNS v1.0 + pinned Shiu LIF'
assert m.get('mutability') == 'read-only-inference'
assert m.get('research_metadata_embedded') is False
root = pathlib.Path(out_dir)
verified = []
for character, entry in (m.get('characters') or {}).items():
    name = str(entry['state_file'])
    target = root / name
    subprocess.run(['curl','-fL','--retry','4','--retry-all-errors','-o',str(target),f'{base_url}/{name}'], check=True)
    sha = hashlib.sha256(target.read_bytes()).hexdigest()
    if sha != str(entry['state_sha256']):
        raise RuntimeError(f'{character} state sha256 mismatch')

    meta_name = str(entry.get('runtime_state_meta_file') or '')
    meta_expected_sha = str(entry.get('runtime_state_meta_sha256') or '')
    if not meta_name or not meta_expected_sha:
        raise RuntimeError(f'{character} runtime state metadata missing from inference manifest')
    meta_target = root / meta_name
    subprocess.run(['curl','-fL','--retry','4','--retry-all-errors','-o',str(meta_target),f'{base_url}/{meta_name}'], check=True)
    meta_sha = hashlib.sha256(meta_target.read_bytes()).hexdigest()
    if meta_sha != meta_expected_sha:
        raise RuntimeError(f'{character} runtime state metadata sha256 mismatch')
    meta = json.load(open(meta_target, encoding='utf-8'))
    if meta.get('state_sha256') != sha:
        raise RuntimeError(f'{character} runtime metadata does not bind the downloaded state')
    if meta.get('character') != character:
        raise RuntimeError(f'{character} runtime metadata character mismatch')
    if int(meta.get('generation', -1)) != int(entry.get('generation', -2)):
        raise RuntimeError(f'{character} runtime metadata generation mismatch')
    verified.append(character)
print(json.dumps({'verified_characters': sorted(verified)}))
PY

BASE_ADAPTER="$ROOT/data/malecns-shiu-strict-v1"
CANDIDATES="$ROOT/data/malecns-valence-v1/kc_mbon_valence_candidates.parquet"
P1_ADAPTER=""
P2_ADAPTER=""

materialize_if_available() {
  local character="$1"
  local out="$2"
  local state_file
  state_file="$(bridge_python - "$SNAPSHOT_DIR/manifest.json" "$character" <<'PY'
import json, sys
m=json.load(open(sys.argv[1],encoding='utf-8'))
e=(m.get('characters') or {}).get(sys.argv[2])
print(e.get('state_file','') if e else '')
PY
)"
  if [[ -z "$state_file" ]]; then
    return 1
  fi
  bridge_python "$ROOT/repo/scripts/materialize_malecns_valence_adapter.py" \
    --base-adapter "$BASE_ADAPTER" \
    --candidates "$CANDIDATES" \
    --state "$SNAPSHOT_DIR/$state_file" \
    --character "$character" \
    --plasticity-config "$ROOT/repo/configs/plasticity_valence_v0.json" \
    --out "$out"
}

write_status "materializing-approved-checkpoints"
if materialize_if_available "$P1" "$WORK/p1-adapter"; then P1_ADAPTER="$WORK/p1-adapter"; fi
if materialize_if_available "$P2" "$WORK/p2-adapter"; then P2_ADAPTER="$WORK/p2-adapter"; fi

CMD=(
  "$ROOT/repo/scripts/run_live_arena_server.py"
  --listen "$UPSTREAM_PORT"
  --session-id "$SESSION_ID"
  --p1 "$P1" --p2 "$P2"
  --reference-python "$REF_WRAPPER"
  --reference-model "$ROOT/shiu/model.py"
  --adapter-dir "$BASE_ADAPTER"
  --interface "$ROOT/data/interface.json"
  --game-jar "$ROOT/fightingice/FightingICE.jar"
  --fightingice-mode "$FIGHTINGICE_MODE"
  --decision-interval 60
  --post-fight-seconds "$POST_FIGHT_SECONDS"
  --out "$WORK/live"
)
if [[ -n "$P1_ADAPTER" ]]; then CMD+=(--adapter-dir-p1 "$P1_ADAPTER"); fi
if [[ -n "$P2_ADAPTER" ]]; then CMD+=(--adapter-dir-p2 "$P2_ADAPTER"); fi

if [[ "${CONNECTOME_PUBLIC_BROADCAST:-false}" == "true" ]]; then
  rm -f "$SCREEN_FILE" "$ACTIVITY_FILE"
  PYTHONPATH="$ROOT/repo/src:$SITE311" "$BRIDGE_PY" \
    "$ROOT/repo/scripts/run_live_screen_publisher.py" \
    --host 127.0.0.1 --port 31415 \
    --output "$SCREEN_FILE" \
    --fps "${CONNECTOME_SCREEN_FPS:-10}" \
    --downsample "${CONNECTOME_SCREEN_DOWNSAMPLE:-2}" \
    > "$WORK/live-screen-publisher.log" 2>&1 &
  SCREEN_PID=$!
  PYTHONPATH="$ROOT/repo/src:$SITE311" "$BRIDGE_PY" \
    "$ROOT/repo/scripts/run_live_activity_publisher.py" \
    --jsonl "$WORK/live/live-decisions.jsonl" \
    --output "$ACTIVITY_FILE" \
    > "$WORK/live-activity-publisher.log" 2>&1 &
  ACTIVITY_PID=$!
fi

write_status "starting-fightingice-malecns"
set +e
bridge_python "${CMD[@]}"
RC=$?
set -e
if [[ "$RC" -eq 0 ]]; then
  write_status "ended"
else
  write_error "$RC" 0
fi
sleep "$POST_SESSION_SECONDS"
cleanup_children
trap - EXIT INT TERM ERR
exit "$RC"
